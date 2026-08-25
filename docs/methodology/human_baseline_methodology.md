# Human Baseline Methodology (Phase 4 Extension)

## Overview
To provide a statistically sound anchor for our structural metrics (AST Depth, Resource Count, Resource Diversity), we processed three massive, human-authored infrastructure repositories. The goal was to establish a mathematical "Human Baseline" and compare it against the output of our 11 frontier LLMs using a Two-Sample Kolmogorov-Smirnov (KS-Test).

## Datasets Processed
The human baseline consists of code drawn from three validated, publicly available GitHub repositories:
1. utoiac-project/iac-eval (Terraform & CloudFormation)
2. ws-cloudformation/iac-model-evaluation (CloudFormation, Terraform)
3. ws-cloudformation/aws-cloudformation-templates (Massive repository of official AWS examples)

These repositories were chosen because they reflect standard, production-ready coding practices implemented by human engineers.

## Data Sanitization and Filtering
GitHub repositories contain many files that are *not* Infrastructure as Code (e.g., README.md, Python deployment scripts, GitHub Actions workflows, JSON config files). If parsed as IaC, these files would skew our AST metrics.

To solve this, our extraction script (src/geniac_secbench/phase4_structural/extract_human_metrics.py) employed strict heuristics:
- **Terraform (.tf):** Naturally parsed via the hcl2 library.
- **CloudFormation/Kubernetes (.yaml, .yml, .json):** Only parsed if the first 2KB of the file contained root structural keys such as AWSTemplateFormatVersion, Resources:, or piVersion:.
- **Custom Parsing:** We implemented a custom yaml.SafeLoader constructor to prevent crashes when encountering AWS intrinsic functions like !Ref or !Sub.

**Yield:** The script successfully filtered, parsed, and extracted AST metrics from **634 valid human-authored IaC templates**.

## Execution and the KS-Test
1. **Extraction:** The 634 templates were processed, and their metrics were logged into data/summary_reports/human_reference_metrics.csv.
2. **Comparison:** We executed src/geniac_secbench/phase4_structural/ks_test_human.py, which ran a Two-Sample KS-Test comparing the distributions of the human dataset against each of the 11 LLM outputs found in structural_metrics.csv.
3. **Results:** The resulting p-values and KS statistics were saved to data/summary_reports/ks_test_human_baseline.csv and .json.

## Output Files
- data/summary_reports/human_reference_metrics.csv: The raw structural metrics of the 634 human files.
- data/summary_reports/ks_test_human_baseline.csv: The statistical KS-Test results comparing each model's output to the human baseline.
- src/geniac_secbench/phase4_structural/extract_human_metrics.py: The data sanitization and AST extraction script.
- src/geniac_secbench/phase4_structural/ks_test_human.py: The mathematical comparison script.
