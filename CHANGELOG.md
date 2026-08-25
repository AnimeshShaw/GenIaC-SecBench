# Changelog

All notable changes to GenIaC-SecBench are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] -- 2026-08-25 remediation

A comprehensive audit-and-fix pass triggered by a pre-submission review.
Full findings are in `docs/THREATS_TO_VALIDITY.md`; summary below.

### Fixed -- correctness (affects reported numbers)
- **Scanner coverage.** Trivy and KICS previously ran on a minority of
  scenarios per model (e.g. llama3: 1/100 for both); Checkov ran on 100%.
  All cross-scanner comparisons and severity breakdowns were confounded by
  coverage, not by genuine scanner disagreement. Rewrote `run_scanners.py`
  to batch-scan per (dataset, model) directory and re-ran to full coverage.
- **GLMM misspecification.** `nb_glmm.py` fit a Poisson GEE (not negative
  binomial, despite being labeled as one throughout the docs), with no
  `offset=log(resource_count)` despite Claim 1 explicitly describing the
  model as accounting for resource-count exposure, and dropped all
  zero-vulnerability rows before fitting (selection on the outcome).
  Reported Incidence Rate Ratios (48-55x) were materially inflated.
- **GLMM reference category near-empty.** `claude-3-5-sonnet`, the model
  regression baseline, had only 3/35 generations scanned. Full re-scan
  resolved this.
- **Friedman test on N=8.** The "simple" stratum's repeated-measures test
  ran on only 8 complete scenario blocks (out of 60) because
  `claude-opus-4-6-thinking` had 52/60 simple generations missing, and
  `pivot.dropna()` requires a fully complete block. Backfilled the missing
  generations; the two complexity strata now compare the same model set.
- **`build_master_table.py` silently dropped ~61 rows** for
  `gpt-5-thinking`'s complex scenarios (100 files and 2,507 raw findings
  existed on disk; 0 made it into `master_results.csv`) due to a left-join
  starting from `schema_validity.csv` rather than the union of all sources.
- **Reported schema pass rates were wrong** in `docs/findings/*.md` (e.g.
  llama3 documented as ~15%, actual 1.0%; mistral documented as ~20%,
  actual 10.0%) -- transcription drift from an earlier data snapshot.
- **Divergent duplicate `findings_raw.csv`.** Two copies existed
  (`data/findings_raw.csv`: Checkov-only, complete; `data/summary_reports/
  findings_raw.csv`: tri-scanner but missing 932 Checkov findings vs. the
  raw JSON on disk). See `data/_archive_v1/PROVENANCE.md`.
- **Human-judge consensus tie-break.** `human_vs_grok.py` used
  `ratings.mode(axis=1)[0]`, which returns the *lowest* value on a 3-way
  split among 3 raters rather than a defined majority rule.

### Fixed -- reproducibility
- **Path resolution.** Every Phase 4/6 script computed the repo root via
  `Path(__file__).resolve().parent.parent.parent`, which broke silently
  after a `src/` reorganization moved scripts one directory deeper (it
  resolved into a nonexistent `src/data/`). Replaced with a single resolver
  in `geniac_secbench/config.py` that walks up to find the real root
  regardless of nesting depth or invocation cwd.
- **Missing scripts.** `visualize_final.py` (all 5 published figures) and
  the Phase 7 stratified sampler existed only as pre-rendered output /
  under a different name with no clear provenance. Restored / relocated.
- **`reproduce.py` never ran the full pipeline** -- it called two scripts
  that didn't exist (`validate_all.py`, `glmm_analysis.py`) and never
  invoked `build_master_table.py`, `parse_results.py`, Phase 7, or Phase 8.
  Replaced with `geniac_secbench.cli`, which runs every phase.
- **Checkov/hcl2 dependency conflict.** Checkov depends on
  `bc-python-hcl2`; the structural-metrics scripts need vanilla
  `python-hcl2` to parse modern Terraform syntax. Both claim the `hcl2`
  import name -- installing both in one environment (including inside the
  original `Dockerfile`, which installed both into the same image) causes
  one to silently shadow the other, breaking Checkov's Terraform/
  CloudFormation runners at import time. Checkov now installs into an
  isolated venv both locally (`scripts/setup_checkov_env.py`) and in Docker
  (`/opt/venv_checkov`).
- **Hardcoded Windows-only tool paths** (WinGet package paths, a specific
  machine's miniconda install) in `validate_iac.py` and `run_scanners.py`
  meant the Docker image's Linux binaries were never actually reachable.
  Replaced with env-var-override > PATH > OS-specific-fallback discovery.
- **32 GB of vendored Terraform provider/module caches** (`.terraform/`,
  nested `.git/` repos) had accumulated inside `data/generated/` from
  `terraform init` runs during Phase 2 validation. Purged (verified
  byte-identical on the 983 genuine model-output files before/after) and
  added a shared provider plugin cache + post-validation cleanup to
  prevent recurrence.
- **`tools/arm-ttk` was a broken git submodule reference** (gitlink with no
  `.gitmodules` entry) that would leave an empty directory on fresh clone.
  Relocated to `third_party/` as a plain gitignored directory.

### Changed -- organization
- Restructured `src/` into an installable package (`geniac_secbench`,
  `pip install -e .`) with one directory per pipeline phase, replacing the
  ad hoc `src/pipeline/`, `src/analysis/`, `src/utilities/` split.
- `tools/*.ps1` (hardcoded, per-model manual run scripts) and other
  one-off/superseded scripts moved to `archive/legacy_scratch/`, kept
  under version control for transparency rather than deleted.
- `docs/` split into `methodology/`, `findings/`, and `appendix/`.
- Anonymized human reviewer PII (name, email, LinkedIn) in
  `data/human_reviews/*.csv` to reviewer IDs (R1/R2/R3); the identity
  mapping is kept in a local-only, gitignored key file.
- Unified the project name to **GenIaC-SecBench** throughout (previously
  inconsistent across `InfraSecBench` / `GenIaC-SecBench` /
  `CloudSec-LLMBench-Code`).

## [1.0.0] -- Initial pipeline (pre-remediation baseline)
- Generation, validation, scanning, structural-metrics, LLM-judge, and
  statistics pipeline for 100 scenarios x 11 models.
- Human baseline (634 files, 3 public repos) and KS-test comparison.
- 3-reviewer human validation of the LLM judge (Fleiss' kappa, QWK).
