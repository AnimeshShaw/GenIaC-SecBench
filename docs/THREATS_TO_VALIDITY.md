# Threats to Validity

This document exists because a pre-submission audit of this benchmark found
real, numerically material issues in the pre-remediation results. It records
what was found, what was fixed, and what limitations remain by design. Read
this before citing a specific number from this project.

**Status:** this document is updated as each remediation phase completes.
See `CHANGELOG.md` for the itemized fix list.

---

## 1. Scanner coverage (RESOLVED as of the Phase 2 re-scan)

**What was wrong.** Checkov ran on effectively 100% of generated scenarios.
Trivy and KICS ran on a small, non-random subset per model -- e.g. llama3
had Trivy/KICS output for 1 of 100 scenarios; claude-3-5-sonnet had 3 of 35.
This confounded every cross-scanner comparison in `docs/findings/`:
Finding 5 ("scanner disagreement") was largely measuring which model
happened to get scanned by which tool, not genuine ruleset divergence. It
also meant Critical/High severity counts (which come only from Trivy/KICS,
since Checkov's open-source tier reports `UNKNOWN` severity for everything)
were systematically undercounted for under-scanned models.

**Root cause.** `run_scanners.py` was invoked ad hoc, per-model, via a set
of hand-maintained PowerShell scripts (`archive/legacy_scratch/
ps1_manual_runs/`) tracking "completed" models in a hardcoded list that
drifted out of sync with reality (one script's own comment notes a model
name typo that caused a scanner to be skipped for an entire model).

**Fix.** Rewrote `run_scanners.py` to batch-scan per (dataset, model)
directory (also ~10x faster per scenario -- KICS's ~90s cold-start cost was
being paid on every single scenario instead of once per batch), track
coverage explicitly in `scan_coverage.csv`, and re-ran to completion. See
`CHANGELOG.md` for the exact before/after coverage numbers.

## 2. GLMM model misspecification (RESOLVED as of the Phase 3 statistics fix)

**What was wrong**, in `nb_glmm.py`:
- Fit a Poisson GEE, not a negative binomial model, despite every doc
  (`docs/findings/claims_and_statistical_evidence.md`, the data dictionary)
  describing it as "Negative Binomial." Poisson assumes mean = variance;
  vulnerability counts are overdispersed, so Poisson standard errors were
  too small and significance was overstated.
- No `offset=log(resource_count)` despite Claim 1 explicitly stating the
  model "accounts for the exposure (Resource Count) ... allowing us to
  calculate the true Incidence Rate Ratio (IRR) of vulnerabilities per
  resource." The fitted model had no such offset -- reported IRRs were raw
  count ratios, not per-resource rates.
- Rows/models with zero total vulnerabilities were filtered out before
  fitting a count regression -- selection on the outcome variable.
- The regression's reference category (`claude-3-5-sonnet`) had a
  near-empty scanned sample (see #1), so every reported IRR was measured
  against statistical noise.

**Fix.** Refit as true negative binomial with `offset=log(resource_count)`,
zero counts retained, and a fully-scanned reference category. See
`docs/findings/claims_and_statistical_evidence.md` for the corrected IRRs
and `CHANGELOG.md` for what changed numerically.

## 3. Friedman test on an incomplete design (RESOLVED as of the Phase 3 statistics fix)

**What was wrong.** `friedman_test.py` used `pivot.dropna()` on a
scenario x model matrix, which requires every model to have a result for a
scenario before that scenario counts at all. Because generation was
incomplete for some models (see #5), the "simple" stratum's test ran on
just **8 of 60** scenarios, and the two complexity strata compared
different model sets entirely (not an apples-to-apples "spread widens with
complexity" comparison, as the original write-up claimed).

**Fix.** Backfilled the missing generations (see #5) so both strata run
over the same model set; switched to a rank test tolerant of the residual
imbalance (Skillings-Mack) rather than requiring complete blocks.

## 4. `build_master_table.py` row loss (RESOLVED)

**What was wrong.** The master results table was built via a left-join
starting from `schema_validity.csv`. Any (scenario, model) pair missing
from that file was silently absent from `master_results.csv` even if scan
findings existed for it -- this dropped ~61 rows for gpt-5-thinking's
complex scenarios (100 files, 2,507 raw findings on disk; 0 rows in the
master table).

**Fix.** Master table now built from the union of all four source tables,
with an explicit row-count assertion against the generated-file count so
this class of silent drop fails loudly instead.

## 5. Incomplete generation matrix

**What was wrong.** The design is advertised as fully crossed (100
scenarios x 11 models), but as of the initial audit:
- `claude-3-5-sonnet`: 0/60 simple, 35/40 complex
- `claude-opus-4-6-thinking`: 8/60 simple, 40/40 complex
- `gpt-5-thinking`: 100/100 generated but only 39 rows survived into the
  master table (see #4 -- this was a table-building bug, not a generation gap)

**Fix.** Backfilled the two genuine generation gaps once API access was
available. [Status: confirm against CHANGELOG.md for the final state --
if gaps remain, they're now documented explicitly rather than silently
absorbed into dropna() calls, and Skillings-Mack (see #3) handles the
residual imbalance correctly rather than requiring a fully complete design.]

## 6. Vendored third-party module contamination -- checked, not present

**What was checked.** `data/generated/` scenario directories accumulated
`.terraform/` module caches (from `terraform init` during Phase 2
validation) containing real, vendored third-party Terraform files (e.g.
AWS's official EKS/KMS modules). Since Checkov, Trivy, and KICS were
invoked directory-recursively with no exclusion, findings from these
vendored files could in principle have been misattributed to the model
under test.

**Result.** Verified empirically: 0 of 10,918 pre-remediation Checkov
findings originated from a `.terraform/` path (Checkov excludes vendored
modules by default). Trivy/KICS were not similarly protected by default,
so this was a live risk for the coverage gaps being filled in #1.
`run_scanners.py` now passes explicit `.terraform`/`.git` exclusions to all
three scanners as insurance, and the 32 GB of accumulated cache itself was
purged from the repository (verified byte-identical on the 983 genuine
model-output files before and after removal).

## 7. Self-authorship of scenarios

The 100 benchmark scenarios were authored by `claude-opus-4-6`, which is
also one of the 11 models under evaluation. This was not disclosed as a
limitation in the original findings documents. Whether this measurably
biases claude-opus-4-6's structural or security results relative to other
models has not been tested; Phase 5 (independent LLM judge) and Phase 7
(human review) partially mitigate this by validating the scenarios
themselves are realistic and non-trivial, but neither was designed to
detect an authorship-affinity effect specifically.

## 8. Protocol deviations from the pre-registered methodology

`docs/methodology/human_review_protocol.md` specifies 2 reviewers and plain
Cohen's kappa; `docs/methodology/iac_benchmark_methodology.md` recommends
GPT-5 as the independent judge (untouched by either the scenario-authoring
or model-under-test roles). What was actually run:
- **3 reviewers**, Fleiss' kappa (inter-rater) + per-reviewer Cohen's/QWK
  vs. the AI judge -- a strictly more rigorous design than pre-registered,
  but a deviation nonetheless and should be stated as such rather than
  silently presented as if it were the original plan.
- **Grok 4.6** as the judge, not GPT-5. Grok is untouched by the
  scenario-authoring (Claude) and model-under-test (multiple labs) roles,
  so the independence property the methodology cared about is preserved --
  but this is a different model than what was pre-registered.
- The review guide advertises "20 sampled scenarios"; one reviewer (R1)
  submitted 18.

None of these deviations are individually disqualifying, but a
pre-registered design that changes without being flagged as changed is a
credibility problem for a paper, not a technical one -- reviewers who check
the methodology section against what was actually run will notice.

## 9. Consensus tie-breaking in `human_vs_grok.py`

**What was wrong.** With 3 raters and an ordinal 1-5 scale, `pandas`'
`.mode(axis=1)[0]` returns the *lowest* value among tied modes, not a
principled majority/median. With Fleiss' kappa as low as 0.058 on one
criterion (security-test relevance), 3-way splits with no true mode are not
rare in this dataset, so this silently biased the "human consensus" used to
validate the AI judge downward on exactly the criterion where humans
already disagreed most.

**Fix.** [Status: confirm against CHANGELOG.md -- replaced with an explicit
tie-break rule (e.g. median for ordinal criteria) and the rule documented
inline in the script.]

---

## What was NOT found to be a problem

- **Vendored-module contamination** (see #6) -- checked directly, not
  present in the historical data.
- **Scenario duplication across the two `scenarios.json` copies** that
  existed pre-reorganization -- diff'd byte-for-byte on parsed content;
  identical, encoding difference only.
- The core structural-divergence finding (LLMs write code structurally
  unlike human-authored IaC, KS-test p < 0.05 across all models/metrics)
  does not depend on any of the issues above and is unaffected.
