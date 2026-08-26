# Data Dictionary

Every output file the GenIaC-SecBench pipeline writes to `data/summary_reports/`,
with its producing module, exact column names, and known anomalies.

Column names below were verified against the generated files. The previous
revision of this document listed several columns that do not exist (`complexity`
where the file actually uses `dataset_type` or `dataset`,
`resource_type_diversity` for `resource_diversity`, `iam_policy_complexity` for
`iam_complexity`) and omitted others entirely (`status`, `file_name`). Anyone
joining these tables from the documented names would have hit a `KeyError`.

**Naming caveat — `dataset` vs `dataset_type` vs `complexity`.** Three different
names are used for the same simple/complex distinction, depending on which phase
wrote the file. They are not yet unified because doing so would break the
archived v1 artifacts they are compared against. Join carefully:

| File | Column carrying simple/complex |
|---|---|
| `findings_raw.csv` | `dataset_type` |
| `resource_counts.csv` | `dataset_type` |
| `schema_validity.csv` | `dataset` |
| `structural_metrics.csv` | `dataset` |
| `scan_coverage.csv` | `dataset` |
| `master_results.csv` | `complexity` |

---

## 1. Raw and per-scenario data

### `findings_raw.csv`
- **Produced by:** `geniac_secbench.phase3_scanning.parse_results`
- **What it is:** one row per individual finding, across all three scanners and
  every generated file. The consolidated vulnerability record.
- **Columns:** `scanner`, `rule_id`, `severity`, `description`, `status`,
  `dataset_type`, `model`, `scenario_id`, `cis_category`
- **Scale:** ~31,000 rows at full tri-scanner coverage.
- **`status`:** filter to `FAILED` for actual findings. Downstream aggregation
  does this; ad-hoc queries that skip it will overcount.
- **Anomaly — `severity == UNKNOWN`:** exclusively Checkov. The open-source
  Checkov CLI does not assign CVSS severity tiers without a commercial API key,
  so every Checkov finding is `UNKNOWN`. Trivy and KICS report severity natively.
  Severity-stratified analysis therefore reflects Trivy + KICS only, and the
  large "Other/UNKNOWN" bucket in CIS breakdowns is a tooling artifact, **not** a
  vulnerability class.

### `schema_validity.csv`
- **Produced by:** `geniac_secbench.phase2_validation.validate_iac`
- **What it is:** syntactic/schema validation per generated file — did the model
  hallucinate resources or emit invalid IaC.
- **Columns:** `dataset`, `model`, `scenario_id`, `tool`, `is_valid`, `error_message`
- **Tools:** `terraform validate`, `cfn-lint`, `kubeconform`, strict ARM JSON parse.
- **Written in append mode**, then deduplicated on
  `(dataset, model, scenario_id)` keeping the newest row, with rows for models no
  longer present on disk pruned. Before that dedupe existed, a second pipeline run
  appended a second full copy — the file reached 2,115 rows for 1,132 generated
  files and silently doubled every count in `master_results.csv`.
- **Contains rows for scenarios that were never generated** (recorded as "No
  recognizable IaC files found"). `build_master_table` drops these; do not treat
  them as zero-vulnerability results.

### `resource_counts.csv`
- **Produced by:** `geniac_secbench.phase3_scanning.run_scanners` (scanner-derived)
- **Columns:** `dataset_type`, `model`, `scenario_id`, `resource_count`
- **⚠️ NOT authoritative.** This count degrades silently to `1` when the scanner
  cannot parse a file. Measured on the complex stratum it reported `1.00` with
  zero variance for `claude-opus-4-6-thinking`, `claude-sonnet-4-6`, `llama3`, and
  `phi3`, against 24.76 / 34.41 from the AST parse. Use
  `structural_metrics.csv` instead; this file is retained only as a fallback
  where the AST parse yields nothing.

### `structural_metrics.csv`
- **Produced by:** `geniac_secbench.phase4_structural.extract_metrics`
- **What it is:** AST-derived structural properties of each generated file. The
  **authoritative** source of `resource_count`.
- **Columns:** `resource_count`, `resource_diversity`, `ast_depth`,
  `iam_complexity`, `dataset`, `model`, `scenario_id`, `file_name`

### `human_reference_metrics.csv`
- **Produced by:** `geniac_secbench.phase4_structural.extract_human_metrics`
- **What it is:** the same structural metrics over 634 human-authored IaC files
  from three public repositories, forming the comparison baseline.
- See `docs/methodology/human_baseline_methodology.md` for filtering heuristics.

### `scan_coverage.csv`
- **Produced by:** `geniac_secbench.phase3_scanning.run_scanners`
- **Columns:** `dataset`, `model`, `scanner`, `scenarios_total`, `scenarios_covered`
- **Why it exists:** the pre-remediation results were computed over a corpus in
  which Trivy and KICS had run on a minority of scenarios, and nothing recorded
  that fact — cross-scanner "disagreement" was partly just absence of data. This
  manifest makes coverage a first-class, checkable artifact.

---

## 2. The master table

### `master_results.csv`
- **Produced by:** `geniac_secbench.phase6_statistics.build_master_table`
- **What it is:** one row per (scenario × model). Every statistical test reads
  this file.
- **Columns:** `scenario_id`, `complexity`, `model`, `model_mode`, `iac_format`,
  `terraform_valid`, `resource_count`, `checkov_vulns`, `trivy_vulns`,
  `kics_vulns`, `checkov_vulns_norm`, `trivy_vulns_norm`, `kics_vulns_norm`,
  `severity_critical`, `severity_high`, `severity_medium`, `severity_low`
- **Row count must equal the number of generated files.** Rows without a
  `main.*` file on disk are dropped: an ungenerated scenario yields zero findings
  from every scanner and would otherwise be indistinguishable from a genuinely
  clean generation, crediting a model for security it never earned.
- **`resource_count` is the denominator** of every `*_norm` column and the
  exposure offset in the GLMM. It comes from `structural_metrics.csv`. A genuine
  zero stays zero rather than being coerced to 1; the rate model excludes
  zero-exposure rows explicitly.
- **`model_mode`:** `standard` / `cot` / `thinking`. See
  `docs/THREATS_TO_VALIDITY.md` §1.1 — `-cot` is prompt-engineered
  chain-of-thought, `-thinking` is the vendor reasoning feature. They are
  different conditions and must not be pooled.

---

## 3. Statistical results

### `statistical_results.json`
- **Produced by:** `geniac_secbench.phase6_statistics.friedman_test`
- **Primary test:** **Skillings–Mack**, the generalization of Friedman to
  incomplete block designs. Reported per stratum with `n_blocks_used`.
- **Secondary:** complete-case Friedman with Kendall's *W*, reported alongside
  with `blocks_discarded` so the cost of listwise deletion is visible. With 12
  arms and uneven coverage this frequently retains **zero** scenarios — which is
  precisely why the classical test is not used as primary.
- **`post_hoc`:** pairwise Wilcoxon signed-rank with Holm–Bonferroni adjustment,
  using pairwise deletion (`n_pairs` recorded per comparison).
- **`reasoning_contrasts`:** paired within-model contrasts (standard vs CoT vs
  vendor reasoning mode) — the design's cleanest comparisons, since only one
  variable is toggled.
- **Default metric:** `total_vulns_norm` (all three scanners per resource).
  `checkov_vulns_norm` remains selectable via `--metric` to reproduce archived v1.

### `nb_glmm_results.json`
- **Produced by:** `geniac_secbench.phase6_statistics.nb_glmm`
- **Primary model:** negative binomial (NB2) GEE, exchangeable working
  correlation grouped by `scenario_id`, with **`offset = log(resource_count)`**.
  Coefficients are incidence rate ratios **per resource**.
- **Also emits** the NB-without-offset and Poisson-without-offset fits so the
  correction from the archived v1 specification is auditable rather than asserted.
- **`overdispersion`:** measured variance/mean. Poisson requires 1; the observed
  value is two orders of magnitude larger, which is what mandates NB2.
- **`specification.rows_zero_exposure_excluded`:** rows with `resource_count == 0`,
  excluded from the rate model only. Selection on exposure, not on outcome.

### `ks_test_results.json` / `ks_test_human_baseline.csv|.json`
- **Produced by:** `geniac_secbench.phase4_structural.ks_test` and `ks_test_human`
- Two-sample Kolmogorov–Smirnov tests: model-vs-model, and each model against the
  634-file human baseline, over AST depth, resource count, and resource diversity.

### `llm_judge_scores.csv`
- **Produced by:** `geniac_secbench.phase5_llm_judge.judge`
- **Columns:** `scenario_id`, `complexity`, `model_judge`,
  `architectural_coherence`, `real_world_plausibility`, `security_test_relevance`,
  `hallucination_flag`
- One row per scenario (100). `model_judge` is the **judge** (Grok 4.6), not a
  generator. Scores the *scenario*, never any model's output.

### `human_agreement_metrics.json`
- **Produced by:** `geniac_secbench.phase7_human_review.fleiss_kappa` and
  `human_vs_grok`
- Fleiss' κ across the three human reviewers, and human-consensus vs LLM-judge
  agreement (Cohen's κ for the binary flag, quadratic-weighted κ for the 1–5
  ordinals). Computed over the 18 scenarios all three reviewers scored — κ
  requires complete blocks.

---

## 4. Aggregated summaries

Convenience aggregations produced by `parse_results` for charting. All are
derivable from `findings_raw.csv` + `master_results.csv`; prefer those two for
any new analysis.

| File | Contents |
|---|---|
| `summary_severity.csv` | finding counts by model × severity (Checkov contributes only `UNKNOWN`) |
| `summary_cis_category.csv` | findings mapped to CIS categories by model — source of the heatmap |
| `summary_model_scanner.csv` | finding counts by model × scanner |
| `summary_vulns_per_resource.csv` | vulnerability density by model and scanner |
| `summary_pass_rate.csv` | schema-validation pass rate per model |

---

## 5. Generation-side artifacts

| File | Contents |
|---|---|
| `data/generation_usage.jsonl` | per-generation token usage: `model`, `scenario_id`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `reasoning_tokens`. Reasoning tokens are read from the nested `completion_tokens_details`. Supports the reported thinking-token distribution and run cost. |
| `data/batch_jobs.json` | submitted Message Batches: id → model, dataset, request count, thinking mode, estimated cost. |
| `data/_archive_v1/` | pre-remediation artifacts, retained for comparison. See its `PROVENANCE.md`. **Do not cite numbers from this directory as results.** |
