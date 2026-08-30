# Human Baseline Methodology (Phase 4 Extension)

## Overview
To provide a statistically sound anchor for our structural metrics (AST Depth, Resource Count, Resource Diversity), we processed three massive, human-authored infrastructure repositories. The goal was to establish a mathematical "Human Baseline" and compare it against the output of our 12 model configurations using a Two-Sample Kolmogorov-Smirnov (KS-Test).

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
2. **Comparison:** We executed src/geniac_secbench/phase4_structural/ks_test_human.py, which ran a Two-Sample KS-Test comparing the distributions of the human dataset against each of the 12 model configurations found in structural_metrics.csv.
3. **Results:** The resulting p-values and KS statistics were saved to data/summary_reports/ks_test_human_baseline.csv and .json.

## Output Files
- data/summary_reports/human_reference_metrics.csv: The raw structural metrics of the 634 human files.
- data/summary_reports/ks_test_human_baseline.csv: The statistical KS-Test results comparing each model's output to the human baseline.
- src/geniac_secbench/phase4_structural/extract_human_metrics.py: The data sanitization and AST extraction script.
- src/geniac_secbench/phase4_structural/ks_test_human.py: The mathematical comparison script.

---

## Security scanning of the human corpus

The structural comparison above was the original purpose of this corpus. It was
later extended to the study's central contribution: the same 634 templates are
**security scanned with the identical toolchain** used on model output —
Checkov, Trivy, and KICS — by
`geniac_secbench.phase3_scanning.scan_human_baseline`.

This closes the gap that motivates the paper. Without it, every vulnerability
density in the study is model-versus-model with no reference point, and the
question a practitioner actually asks — *are these models worse than the
engineers they assist?* — is unanswerable. With it, the comparison is direct.

Outputs: `human_baseline_findings.csv` (one row per finding) and
`human_baseline_density.csv` (per-file counts joined to the AST-derived resource
counts from `human_reference_metrics.csv`, giving a density directly comparable
to `master_results.csv`).

### Size matching is mandatory

Density is strongly inverse to artifact size (Spearman ρ = −0.546, p < 10⁻⁷⁷),
and the human corpus averages 5.31 declared resources against roughly 3 for
simple-stratum generations and ~50 for complex ones. Comparing raw group means
across that range measures artifact size, not security.

All published comparisons therefore bin by `resource_count` and compare within
bins. The unmatched comparison and the matched one disagree, and only the matched
one is reported: unmatched, models appear indistinguishable from humans on the
complex stratum; matched, every configuration sits at 3.21×–3.87× the human rate.

### What this baseline is not

The corpus is **not a matched control**. These files were not written against the
100 benchmark scenarios, and many are curated *examples* published for
instructional purposes rather than production infrastructure. Example templates
may be deliberately minimal, or unusually careful — the direction of any bias is
unknown and is not claimed to favour either side. A properly matched control
would require human engineers to implement the same 100 scenarios under the same
constraints; that is identified as future work.

Scanner rule coverage also varies by format, and the corpus format mix differs
from the generated mix, so cross-format density values are not comparable. See
`../THREATS_TO_VALIDITY.md`.
