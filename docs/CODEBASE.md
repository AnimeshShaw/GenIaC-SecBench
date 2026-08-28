# Codebase Guide

How the GenIaC-SecBench pipeline is put together, what each module does, and the
non-obvious constraints that shaped it. Read this before modifying a phase.

For column-level definitions see [`appendix/data_dictionary.md`](appendix/data_dictionary.md).
For known limitations see [`THREATS_TO_VALIDITY.md`](THREATS_TO_VALIDITY.md).

---

## 1. Layout

```
src/geniac_secbench/
  config.py                  single source of truth for every path
  cli.py                     pipeline entry point
  phase1_generation/         LLM API calls -> raw IaC
  phase2_validation/         terraform validate / cfn-lint / ARM-TTK / kubeconform
  phase3_scanning/           Checkov + Trivy + KICS, over models AND humans
  phase4_structural/         AST metrics + KS tests
  phase5_llm_judge/          independent scenario review by an LLM judge
  phase6_statistics/         master table, omnibus tests, rate model
  phase7_human_review/       sampling, inter-rater and human-vs-judge agreement
  phase8_reporting/          figures and the generated results document

scripts/                     standalone utilities (dataset up/download, setup)
tests/                       smoke tests, run in CI before any push
third_party/                 scanner binaries (gitignored, install script provided)
```

### `config.py` — read this first

Every module imports `PATHS` from here. Nothing anywhere else computes a path
from `__file__`.

This is not stylistic. The pre-restructure code resolved paths with
`Path(__file__).resolve().parent.parent.parent`, which silently resolved to
`src/data` after the files were moved into phase directories. Three analysis
scripts pointed at a directory that did not exist. They did not crash — they
wrote results nobody read. A single resolver makes that class of bug impossible.

---

## 2. Running it

```bash
pip install -e .

python -m geniac_secbench.cli --phase analyze   # no API keys or scanners needed
python -m geniac_secbench.cli --phase all       # full pipeline
python -m geniac_secbench.cli --phase scan      # one phase
```

| Phase | Needs | Produces |
|---|---|---|
| `generate` | API keys | `data/generated/` |
| `validate` | terraform, cfn-lint, kubeconform, ARM-TTK | `schema_validity.csv` |
| `scan` | checkov, trivy, kics | `scan_results/`, `findings_raw.csv`, `scan_coverage.csv` |
| `structural` | — | `structural_metrics.csv`, KS results |
| `judge` | API key | `llm_judge_scores.csv` |
| `statistics` | — | `master_results.csv`, `statistical_results.json`, `nb_glmm_results.json` |
| `human_review` | — | `human_agreement_metrics.json` |
| `report` | — | figures, `docs/findings/RESULTS.md` |

`analyze` = `structural` + `statistics` + `human_review` + `report`. It is the
path a third party takes after downloading the dataset, and it regenerates every
number in the paper.

---

## 3. Phases

### Phase 1 — Generation

`generate_iac.py` (synchronous) and `batch_generate.py` (Message Batches API,
50% cost).

Every request is stateless: no history, no few-shot examples, no retrieval. No
prompt mentions security, so what is measured is the model's *default* posture.

**Reasoning arms.** The model registry encodes three conditions:

| Suffix | Condition |
|---|---|
| *(none)* | standard generation, `temperature=0.2` |
| `-cot` | a system-prompt instruction to reason step by step |
| `-thinking` | the vendor's extended-thinking API |

These are different treatments. Pooling `-cot` with `-thinking` (as an earlier
revision did) makes the reasoning comparison meaningless.

**Truncation is discarded, never written.** If a response hits the output
ceiling, the artifact is dropped. A truncated template still parses, so writing
it would deflate both validity and finding counts in a way nothing downstream
could detect. Four of 1,200 generations are missing for this reason, and that is
the correct outcome.

**Batch results are keyed by `custom_id`, never by position.** Batch responses
arrive in arbitrary order; indexing by order would attribute code to the wrong
scenario and corrupt every per-scenario join invisibly.

### Phase 2 — Validation

`validate_iac.py` runs the real toolchain per format: `terraform validate`,
`cfn-lint`, `kubeconform`, ARM-TTK.

**The output file is append-mode, then deduplicated.** Results stream to disk so
an interrupted run keeps its work, but a second run would otherwise append a
second full copy. This happened: `schema_validity.csv` reached 2,115 rows for
1,132 artifacts — 937 duplicates — and the master table silently doubled every
count. `_dedupe_and_prune()` collapses on `(dataset, model, scenario_id)` keeping
the newest row, and drops rows for models no longer on disk so a renamed arm does
not linger as a phantom model.

Concurrent runs of this phase will still interleave writes. Run it once at a time.

### Phase 3 — Scanning

`run_scanners.py` (models) and `scan_human_baseline.py` (human corpus). Both use
the identical three engines — that is what makes the central comparison valid.

**Scanning is batched per `model × dataset` directory, not per scenario.** KICS
loads ~2,000 Rego queries per invocation: 97 s for one scenario, but 10 s for a
directory of 40. Per-scenario invocation would take ~19 hours; batching takes
minutes. Findings are attributed back to scenarios by the file path in each
report.

`scan_coverage.csv` is a first-class output. Earlier results were computed over a
corpus where Trivy and KICS had run on a minority of scenarios with nothing
recording that fact, so apparent "scanner disagreement" was partly just missing
data.

### Phase 4 — Structural metrics

`extract_metrics.py` (models) and `extract_human_metrics.py` (human corpus)
compute AST depth, resource count, and resource diversity.

**`structural_metrics.csv` is the authoritative resource count**, not
`resource_counts.csv`. The scanner-derived count degrades silently to 1 on parse
failure — it reported exactly 1.00 with zero variance for four configurations
whose true means were 24.76 and 34.41. Since resource count is the denominator of
every density and the exposure offset in the rate model, that error would
propagate everywhere.

### Phase 5 — LLM judge

`judge.py` scores each *scenario* (never any model's output) on four criteria.
The judge is from a vendor not under test. Treat its scores as secondary evidence
weighted by the Phase 7 calibration — it is reliable for hallucination detection
(κ = 0.640) and unreliable for architectural judgment (κ = 0.177).

### Phase 6 — Statistics

**`build_master_table.py`** joins everything into one row per (scenario × model).

Two invariants it enforces:

- Rows without a generated file on disk are **dropped**. An ungenerated scenario
  produces zero findings from every scanner and would otherwise be
  indistinguishable from a genuinely clean generation, crediting a model for
  security it never earned.
- It deduplicates defensively on `(model, complexity, scenario_id)` even though
  Phase 2 also dedupes, because this table is what every statistical test reads.

**`friedman_test.py`** uses **Skillings–Mack** as the primary omnibus test.

Complete-case Friedman requires every configuration present in every block. With
12 configurations and realistic coverage gaps, **no scenario qualifies** — the
classical test retains zero blocks and is uncomputable, not merely weaker. The
script still computes and reports it, with `blocks_discarded`, so the cost of
listwise deletion is visible rather than hidden.

Post-hoc uses pairwise Wilcoxon with Holm correction and **pairwise** deletion,
recording `n_pairs` per comparison.

**`nb_glmm.py`** fits a negative binomial GEE with `offset=log(resource_count)`.

Three properties that are easy to get wrong, and were:

- **Negative binomial, not Poisson.** Measured overdispersion is ~130×; Poisson
  standard errors would be far too small and would overstate significance.
- **The exposure offset is mandatory.** Without it the coefficients compare code
  *volume*, not vulnerability *rate* — which is the opposite of the intended
  claim. Removing it inflated one interaction term by +2528%.
- **Zero-count rows are retained.** Filtering rows whose outcome is zero is
  selection on the outcome and biases every estimate.

The script also emits the NB-without-offset and Poisson fits so the correction is
auditable rather than asserted.

### Phase 7 — Human review

`stratified_sampling.py` draws the review sample; `agreement_metrics.py` computes
Fleiss' κ across raters and human-consensus-vs-judge agreement, and **persists**
them to `human_agreement_metrics.json`.

Persistence matters: the superseded `fleiss_kappa.py` / `human_vs_grok.py` pair
printed to stdout and wrote nothing, so the file the paper's κ figures were read
from was regenerated by nothing and aged out of sync with the data. Those two are
retained in `archive/legacy_scratch/superseded_phase7/` with a note; do not
reintroduce them.

**Ordinal rater ties resolve to the median.** The old code used
`mode(axis=1)[0]`, and pandas returns modes sorted — so a full three-way
disagreement (2/4/5) has no mode, every value ties, and `[0]` silently took the
*lowest*, biasing consensus downward exactly where raters disagreed most. The tie
count is now reported.

Agreement statistics use only scenarios scored by **all** raters; κ requires
complete blocks.

### Phase 8 — Reporting

`visualize_final.py` and `visualize_human_baseline.py` produce the figures.
`findings_report.py` regenerates `docs/findings/RESULTS.md` from the result files.

Nothing in the published results is hand-transcribed. The pre-remediation
findings documents were written by hand and several headline numbers did not
match the CSVs they claimed to summarize — reported schema pass rates of 15% and
20% against actual values of 1.0% and 10.0%.

---

## 4. Rules for contributors

**Never hand-transcribe a number into a document.** Add it to
`findings_report.py`.

**Never widen an allow-list to a deny-list in `upload_dataset.py`.**
`REVIEWER_KEY_local_only.csv` is the only copy of the mapping from anonymized
rater ids to real identities. The upload is allow-listed, asserts against
forbidden patterns, and defaults to `--dry-run`.

**Assert row counts after every join.** Every silent-corruption bug in this
project's history produced plausible-looking numbers and raised no error. The
master table asserts against files on disk; do the same for anything new.

**Prefer failing loudly to filling in a default.** A resource count that
degrades to 1, a severity that defaults to `UNKNOWN`, a truncated file written as
if complete — each looked like data and was not.

**Run the tests.** `python -m pytest tests/ -q` before any push.

---

## 5. Environment

```bash
pip install -e .                       # runtime
pip install -r requirements-dev.txt    # tests, linting

python third_party/install.py          # scanner binaries (or use Docker)
cp .env.example .env                   # API keys, generation only
```

`.env` holds provider keys and is gitignored. Only Phases 1 and 5 need it;
`--phase analyze` runs offline against downloaded data.
