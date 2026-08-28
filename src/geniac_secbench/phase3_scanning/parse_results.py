"""
InfraSecBench - Results Parser & CIS Benchmark Mapper
======================================================
Parses raw JSON output from Checkov, tfsec, and Trivy, normalises findings
into a single DataFrame, maps rule IDs to CIS Benchmark categories, and
exports aggregated metrics + visualisation-ready CSVs.

Usage:
    python src/parse_results.py
    python src/parse_results.py --format markdown   # Print tables to stdout
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CIS Benchmark Category Mapping
# ---------------------------------------------------------------------------
# Maps scanner rule-ID prefixes / keywords to high-level CIS categories.
# This is intentionally broad; a full mapping would reference the actual
# CIS Benchmark documents for AWS, Azure, and GCP.
# ---------------------------------------------------------------------------

CIS_CATEGORY_KEYWORDS = {
    "Identity and Access Management": [
        "iam", "rbac", "admin", "privilege", "role", "policy", "access",
        "service_account", "clusterrole", "identity", "authentication",
        "authorization",
    ],
    "Logging and Monitoring": [
        "logging", "monitor", "cloudtrail", "flow_log", "audit",
        "diagnostic", "activity_log", "stackdriver",
    ],
    "Networking": [
        "security_group", "firewall", "nsg", "network", "vpc", "vnet",
        "subnet", "ingress", "egress", "public_ip", "ssh", "rdp",
        "port", "cidr", "0.0.0.0",
    ],
    "Data Protection": [
        "encrypt", "kms", "tde", "ssl", "tls", "https", "s3_bucket",
        "storage_account", "secret", "key_vault", "cmk", "at_rest",
        "in_transit",
    ],
    "Compute and Container Security": [
        "privileged", "root", "host_network", "host_path", "docker.sock",
        "resource_limit", "capability", "seccomp", "apparmor",
        "escalation", "container",
    ],
    "Storage": [
        "bucket", "blob", "public_access", "versioning", "lifecycle",
        "acl",
    ],
}


def map_to_cis_category(rule_id: str, desc: str) -> str:
    text = (rule_id + " " + desc).upper()
    if "IAM" in text or "ROLE" in text or "POLICY" in text:
        return "IAM"
    if "ENCRYPT" in text or "TLS" in text or "SSL" in text or "KMS" in text:
        return "Encryption"
    if "PUBLIC" in text or "0.0.0.0" in text or "NETWORK" in text or "PORT" in text:
        return "Networking"
    if "LOGGING" in text or "MONITORING" in text or "AUDIT" in text:
        return "Logging/Monitoring"
    return "Other"

def parse_checkov(file_path: Path) -> tuple[list[dict], int]:
    findings = []
    resource_count = 1
    try:
        raw = file_path.read_text(encoding="utf-8").strip()
        if not raw: return findings, resource_count
        data = json.loads(raw)
        
        # Checkov sometimes returns a list if multiple frameworks
        if isinstance(data, list):
            for d in data:
                if d.get("summary", {}).get("resource_count", 0) > 0:
                    resource_count = max(resource_count, d["summary"]["resource_count"])
                failed = d.get("results", {}).get("failed_checks", [])
                for check in failed:
                    findings.append({
                        "scanner": "checkov", "rule_id": check.get("check_id", ""),
                        "severity": check.get("severity") or "UNKNOWN",
                        "description": check.get("check_name", ""), "status": "FAILED",
                    })
        else:
            resource_count = max(resource_count, data.get("summary", {}).get("resource_count", 1))
            failed = data.get("results", {}).get("failed_checks", [])
            for check in failed:
                findings.append({
                    "scanner": "checkov", "rule_id": check.get("check_id", ""),
                    "severity": check.get("severity") or "UNKNOWN",
                    "description": check.get("check_name", ""), "status": "FAILED",
                })
    except Exception as e:
        logger.debug(f"Checkov parse error for {file_path}: {e}")
    return findings, resource_count

def parse_kics(file_path: Path) -> tuple[list[dict], int]:
    findings = []
    try:
        raw = file_path.read_text(encoding="utf-8").strip()
        if not raw: return findings, 1
        data = json.loads(raw)
        for query in data.get("queries", []):
            for file_issue in query.get("files", []):
                findings.append({
                    "scanner": "kics", "rule_id": query.get("query_id", ""),
                    "severity": query.get("severity", "UNKNOWN").upper(),
                    "description": query.get("query_name", ""), "status": "FAILED",
                })
    except Exception as e:
        logger.debug(f"KICS parse error for {file_path}: {e}")
    return findings, 1

def parse_trivy(file_path: Path) -> tuple[list[dict], int]:
    findings = []
    try:
        raw = file_path.read_text(encoding="utf-8").strip()
        if not raw: return findings, 1
        data = json.loads(raw)
        for res in data.get("Results", []):
            for m in res.get("Misconfigurations", []):
                if m.get("Status", "FAIL") != "PASS":
                    findings.append({
                        "scanner": "trivy", "rule_id": m.get("ID", ""),
                        "severity": m.get("Severity", "UNKNOWN"),
                        "description": m.get("Title", ""), "status": "FAILED",
                    })
    except Exception as e:
        logger.debug(f"Trivy parse error for {file_path}: {e}")
    return findings, 1

PARSERS = {"checkov": parse_checkov, "kics": parse_kics, "trivy": parse_trivy}

def collect_all_findings(scan_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    resource_counts = []
    if not scan_root.exists(): return pd.DataFrame(), pd.DataFrame()

    for dataset_dir in sorted(scan_root.iterdir()):
        if not dataset_dir.is_dir(): continue
        dataset_name = dataset_dir.name
        for model_dir in sorted(dataset_dir.iterdir()):
            if not model_dir.is_dir(): continue
            model_name = model_dir.name
            for scenario_dir in sorted(model_dir.iterdir()):
                if not scenario_dir.is_dir(): continue
                sid = scenario_dir.name
                
                scenario_resource_count = 1
                for scanner_name, parser_fn in PARSERS.items():
                    result_file = scenario_dir / f"{scanner_name}.json"
                    if not result_file.exists(): continue
                    findings, rc = parser_fn(result_file)
                    if scanner_name == "checkov": scenario_resource_count = rc
                    
                    for f in findings:
                        f["dataset_type"] = dataset_name
                        f["model"] = model_name
                        f["scenario_id"] = sid
                        f["cis_category"] = map_to_cis_category(f.get("rule_id", ""), f.get("description", ""))
                        rows.append(f)
                
                resource_counts.append({
                    "dataset_type": dataset_name, "model": model_name, "scenario_id": sid,
                    "resource_count": scenario_resource_count
                })

    return pd.DataFrame(rows), pd.DataFrame(resource_counts)

def compute_summary(df: pd.DataFrame, rc_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    summaries = {}
    if df.empty: return summaries

    summaries["model_scanner"] = df.groupby(["model", "scanner"]).size().reset_index(name="fail_count")
    summaries["severity"] = df.groupby(["model", "severity"]).size().reset_index(name="count")
    
    # Calculate vulns_per_resource
    # Group total failures per scenario, model, scanner
    vuln_counts = df.groupby(["dataset_type", "model", "scenario_id", "scanner"]).size().reset_index(name="fail_count")
    merged = pd.merge(vuln_counts, rc_df, on=["dataset_type", "model", "scenario_id"], how="left")
    merged["vulns_per_resource"] = merged["fail_count"] / merged["resource_count"]
    
    # Average vulns_per_resource per model per scanner
    vpr_summary = merged.groupby(["model", "scanner"])["vulns_per_resource"].mean().reset_index()
    summaries["vulns_per_resource"] = vpr_summary

    return summaries

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-dir", type=str, default=str(PATHS.scan_results))
    # NOTE: this MUST be the single canonical output directory (summary_reports/).
    # A prior version of this script defaulted to the data/ root, which produced
    # a second, divergent copy of findings_raw.csv alongside the one in
    # summary_reports/ -- see data/_archive_v1/PROVENANCE.md for the fallout.
    parser.add_argument("--output-dir", type=str, default=str(PATHS.summary_reports))
    args = parser.parse_args()

    scan_root, output_dir = Path(args.scan_dir), Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, rc_df = collect_all_findings(scan_root)
    if df.empty:
        logger.warning("No findings collected.")
        return

    df.to_csv(output_dir / "findings_raw.csv", index=False)
    rc_df.to_csv(output_dir / "resource_counts.csv", index=False)
    
    summaries = compute_summary(df, rc_df)
    for name, summary_df in summaries.items():
        summary_df.to_csv(output_dir / f"summary_{name}.csv", index=False)

if __name__ == "__main__":
    main()
