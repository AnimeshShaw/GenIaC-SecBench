import sys
import pandas as pd
import numpy as np
import logging
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_iac_format(scenario_id):
    if scenario_id.startswith('aws-tf') or scenario_id.startswith('az-tf') or scenario_id.startswith('gcp-tf') or '-tf-' in scenario_id:
        return 'terraform'
    elif scenario_id.startswith('aws-cfn') or '-cfn-' in scenario_id:
        return 'cloudformation'
    elif scenario_id.startswith('az-arm') or '-arm-' in scenario_id:
        return 'arm'
    elif scenario_id.startswith('k8s-') or '-k8s-' in scenario_id:
        return 'kubernetes'
    else:
        return 'unknown'

def main():
    data_dir = PATHS.summary_reports

    # Load data
    try:
        findings = pd.read_csv(data_dir / 'findings_raw.csv')
        schema_validity = pd.read_csv(data_dir / 'schema_validity.csv')
        resource_counts = pd.read_csv(data_dir / 'resource_counts.csv')
        structural = pd.read_csv(data_dir / 'structural_metrics.csv')
    except Exception as e:
        logging.error(f"Error loading CSV files: {e}")
        return

    # Create a base dataframe of all (scenario_id, model) pairs from the datasets
    # Can extract from schema_validity which should have all pairs
    schema_validity['complexity'] = schema_validity['dataset'].replace({'simple': 'simple', 'complex': 'complex'})
    
    base_df = schema_validity[['scenario_id', 'model', 'dataset', 'is_valid']].copy()
    base_df = base_df.rename(columns={'dataset': 'complexity', 'is_valid': 'terraform_valid'})

    # Drop rows for (dataset, model, scenario) triples with NO generated file.
    #
    # schema_validity records a row per scenario it was asked to check, including
    # ones where generation never produced a file ("No recognizable IaC files
    # found"). Those rows carry zero findings from every scanner -- so a scenario
    # that was never generated is indistinguishable from one generated with no
    # vulnerabilities, and the model gets CREDIT for security it never earned.
    #
    # This is not hypothetical: 11 complex extended-thinking generations were
    # refused at collection time for being truncated (stop_reason=max_tokens),
    # and all 11 reappeared here as clean zero-vulnerability rows -- biasing the
    # precise arm whose vulnerability density the paper is testing. A missing
    # generation is missing data, not a secure result.
    n_before = len(base_df)
    def _has_file(row) -> bool:
        d = PATHS.generated / str(row['complexity']) / str(row['model']) / str(row['scenario_id'])
        return d.is_dir() and any(d.glob('main.*'))
    base_df = base_df[base_df.apply(_has_file, axis=1)]
    dropped = n_before - len(base_df)
    if dropped:
        logging.warning(
            "Dropped %d row(s) with no generated file on disk (ungenerated scenarios "
            "must not be scored as zero-vulnerability).", dropped)
    
    # Clean complexity
    base_df['complexity'] = base_df['complexity'].replace({'simple': 'simple', 'complex': 'complex'})

    # Model mode
    base_df['model_mode'] = base_df['model'].apply(lambda x: 'thinking' if 'thinking' in x else 'standard')
    
    # IaC format
    base_df['iac_format'] = base_df['scenario_id'].apply(get_iac_format)

    # Resource counts -- structural_metrics.csv is AUTHORITATIVE.
    #
    # Two sources report resource_count and they disagree badly:
    #   structural_metrics.csv  Phase 4, parses the IaC with hcl2/yaml and counts
    #                           declared resources. Authoritative.
    #   resource_counts.csv     Phase 3, derived from scanner output. Silently
    #                           degrades to 1 when the scanner cannot parse a file.
    #
    # The original merge took resource_counts FIRST and only backfilled from
    # structural, so the degraded value won wherever both existed. Measured
    # complex-stratum means: claude-opus-4-6-thinking 1.00 (std 0.00!) from
    # resource_counts vs 24.76 from the AST parse; claude-sonnet-4-6 1.00 vs 34.41.
    #
    # resource_count is the DENOMINATOR of vulns_per_resource, the paper's primary
    # metric and the GLMM exposure offset. A denominator pinned at 1 turns a
    # density into a raw count: it inflated the extended-thinking arm's apparent
    # density to 104.6 vulns/resource and produced a spurious "+2528% vs standard"
    # -- an artifact of the divisor, not a property of the model.
    #
    # Prefer the AST count; fall back to the scanner count only where the AST
    # parse produced nothing.
    struct_rc = structural[['scenario_id', 'model', 'resource_count']].drop_duplicates()
    base_df = base_df.merge(struct_rc, on=['scenario_id', 'model'], how='left')

    rc = resource_counts[['scenario_id', 'model', 'resource_count']].drop_duplicates()
    base_df = base_df.merge(rc, on=['scenario_id', 'model'], how='left', suffixes=('', '_scanner'))
    base_df['resource_count'] = base_df['resource_count'].fillna(base_df['resource_count_scanner'])
    base_df = base_df.drop(columns=['resource_count_scanner'])

    # Genuinely-zero resource counts are left as 0, NOT coerced to 1. A file that
    # declares no resources has no exposure; the rate model excludes it explicitly
    # (see nb_glmm.py) rather than silently inventing a denominator.
    base_df['resource_count'] = base_df['resource_count'].fillna(0.0)

    # Findings aggregation
    # Filter to FAILED status
    failed_findings = findings[findings['status'] == 'FAILED']
    
    # Scanner vulns
    scanner_counts = failed_findings.groupby(['scenario_id', 'model', 'scanner']).size().unstack(fill_value=0).reset_index()
    for col in ['checkov', 'trivy', 'kics']:
        if col not in scanner_counts.columns:
            scanner_counts[col] = 0
            
    scanner_counts = scanner_counts.rename(columns={
        'checkov': 'checkov_vulns',
        'trivy': 'trivy_vulns',
        'kics': 'kics_vulns'
    })
    
    base_df = base_df.merge(scanner_counts[['scenario_id', 'model', 'checkov_vulns', 'trivy_vulns', 'kics_vulns']], 
                            on=['scenario_id', 'model'], how='left')
    base_df['checkov_vulns'] = base_df['checkov_vulns'].fillna(0)
    base_df['trivy_vulns'] = base_df['trivy_vulns'].fillna(0)
    base_df['kics_vulns'] = base_df['kics_vulns'].fillna(0)
    
    # Severity counts
    severity_counts = failed_findings.groupby(['scenario_id', 'model', 'severity']).size().unstack(fill_value=0).reset_index()
    for col in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        if col not in severity_counts.columns:
            severity_counts[col] = 0
            
    severity_counts = severity_counts.rename(columns={
        'CRITICAL': 'severity_critical',
        'HIGH': 'severity_high',
        'MEDIUM': 'severity_medium',
        'LOW': 'severity_low'
    })
    
    base_df = base_df.merge(severity_counts[['scenario_id', 'model', 'severity_critical', 'severity_high', 'severity_medium', 'severity_low']], 
                            on=['scenario_id', 'model'], how='left')
    for col in ['severity_critical', 'severity_high', 'severity_medium', 'severity_low']:
        base_df[col] = base_df[col].fillna(0)
        
    # Normalised metrics
    base_df['checkov_vulns_norm'] = base_df['checkov_vulns'] / base_df['resource_count']
    base_df['trivy_vulns_norm'] = base_df['trivy_vulns'] / base_df['resource_count']
    base_df['kics_vulns_norm'] = base_df['kics_vulns'] / base_df['resource_count']

    # Final columns
    final_cols = ['scenario_id', 'complexity', 'model', 'model_mode', 'iac_format', 'terraform_valid', 
                  'resource_count', 'checkov_vulns', 'trivy_vulns', 'kics_vulns', 
                  'checkov_vulns_norm', 'trivy_vulns_norm', 'kics_vulns_norm', 
                  'severity_critical', 'severity_high', 'severity_medium', 'severity_low']
    
    master_df = base_df[final_cols]
    
    output_path = data_dir / 'master_results.csv'
    master_df.to_csv(output_path, index=False)
    logging.info(f"Successfully saved master table to {output_path} with {len(master_df)} rows.")

if __name__ == '__main__':
    main()
