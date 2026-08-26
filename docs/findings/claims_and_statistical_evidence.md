# Claims and Statistical Evidence

Every claim the paper makes, mapped to the test that supports it, the artifact it
comes from, and the script that regenerates it. Numbers are authoritative in
`RESULTS.md`, generated from `data/summary_reports/`.

**Status key:** ✅ supported · ⚠️ supported with caveats · ❌ not supported
(reported as a negative result)

---

## ✅ Claim 1 — LLM-generated IaC is ~3.5× less secure than human-authored IaC

**Statement.** Matched on declared-resource count, every model configuration
produces 3.21×–3.87× the vulnerability density of human-authored IaC.

**Why it was needed.** Prior work reports model-only counts. "Eight findings per
resource" has no referent without a human anchor measured through the same
toolchain.

**Test.** Mann–Whitney *U* within resource-count strata, plus a per-configuration
weighted ratio over shared strata.

**Why this test.** Density is non-normal and zero-inflated, so a rank test is
appropriate. Stratification is *mandatory*, not stylistic: density is strongly
inverse to artifact size (LLM ρ = −0.55, p = 1.7e-78; human 4.51 → 1.10 across
bins) and the corpora differ in scale (5.31 vs ≈3 vs ≈50 resources). An
unmatched test measures artifact size, not security — an early unmatched analysis
wrongly suggested parity on complex scenarios.

**Result.** Significant in every stratum except 20+ resources (p = 0.058).
Ratios 4.9× / 2.4× / 2.3× / 1.8× / 2.3× / 1.4×. Per-configuration band
3.21×–3.87× across 11 arms.

**Interpretation.** A property of current LLM-generated IaC rather than of any
one vendor. The gap is largest where the task is simplest.

**Artifacts.** `human_baseline_density.csv`, `master_results.csv`
**Regenerate.** `phase3_scanning.scan_human_baseline`, `phase8_reporting.visualize_human_baseline`

---

## ✅ Claim 2 — Vendor reasoning modes outperform prompted chain-of-thought

**Statement.** Extended thinking reduces density 12.0% relative to prompted CoT
(p = 0.0013); prompted CoT alone is indistinguishable from standard generation.

**Why it was needed.** Prompted CoT is widely treated as a free substitute for
paid reasoning. No prior security evaluation separates them.

**Test.** Wilcoxon signed-rank on paired scenarios — same model, same scenarios,
one variable toggled.

**Why this test.** The design is paired and the outcome non-normal, making
Wilcoxon the correct non-parametric analogue of a paired *t*-test.

**Result (simple stratum, n = 60).**

| contrast | Δ | p |
|---|---:|---:|
| standard → extended thinking | −13.2% | **0.012** |
| prompted CoT → extended thinking | −12.0% | **0.0013** |
| standard → prompted CoT | −1.3% | 0.238 |

**Interpretation.** Telling a model to "think step by step" confers no measurable
security benefit; allocating reasoning tokens does.

**Caveat.** Significance is simple-stratum only; complex-stratum contrasts point
the same direction but are underpowered (n ≈ 31).

**Artifacts.** `statistical_results.json` → `reasoning_contrasts`
**Regenerate.** `phase6_statistics.friedman_test`

---

## ✅ Claim 3 — Reasoning barely engages on IaC generation

**Statement.** Under extended thinking, the model spends <1% of its output budget
on reasoning for complex IaC (median 151 of 18,533 tokens).

**Why it was needed.** Without it, the modest effect in Claim 2 is
uninterpretable — is reasoning ineffective, or barely used?

**Test.** Direct instrumentation of `completion_tokens_details.reasoning_tokens`
per generation.

**Result.** Median 29 tokens (simple) and 151 (complex); max 1,988. `budget_tokens`
is a ceiling the model may underspend, not a target.

**Interpretation.** Bounds Claim 2 mechanistically. A small effect must **not** be
read as "reasoning does not help" in general.

**Artifacts.** `data/generation_usage.jsonl`
**Regenerate.** `phase8_reporting.visualize_human_baseline`

---

## ✅ Claim 4 — Models differ in security posture

**Statement.** Configurations differ significantly within both strata.

**Test.** **Skillings–Mack**, the generalization of Friedman to incomplete block
designs.

**Why this test.** Friedman requires complete blocks. With 12 configurations and
realistic coverage gaps, **no scenario has every configuration present** —
complete-case analysis retains **zero** blocks in both strata. The standard test
(Demšar 2006) is uncomputable here, not merely weaker. Skillings–Mack uses every
scenario with ≥2 configurations present.

**Validation.** Our implementation matches Friedman to ~1e-14 on complete data
and reproduces the worked example in
`docs/methodology/iac_benchmark_methodology.md` exactly (χ² = 8.400).

**Result.** simple χ² = 69.3, df = 10, p = 6.0e-11 (60 blocks); complex
χ² = 81.2, df = 11, p = 8.7e-13 (40 blocks).

**Artifacts.** `statistical_results.json`
**Regenerate.** `phase6_statistics.friedman_test`

---

## ✅ Claim 5 — Per-resource rate ratios, and inverted survivorship

**Statement.** Rate ratios span 0.73–4.64; `phi3` records the fewest absolute
findings yet the highest per-resource rate.

**Test.** Negative binomial GEE, exchangeable working correlation grouped by
scenario, **offset = log(resource_count)**.

**Why this test.** Repeated measures require a correlation structure. The offset
makes coefficients genuine *per-resource* rates — without it, a model emitting
60 resources is penalised simply for writing more code. Negative binomial rather
than Poisson is required empirically: **variance/mean = 130.0**.

**Result.** `claude-opus-4-6-cot` IRR 0.73 [0.54, 0.99], p = 0.041;
`phi3` IRR 4.64 [3.12, 6.89], p = 2.9e-14.

**Interpretation.** Absolute counts are misleading for cross-model comparison.

**Artifacts.** `nb_glmm_results.json` (emits Poisson-no-offset alongside, so the
correction from v1 is auditable)
**Regenerate.** `phase6_statistics.nb_glmm`

---

## ✅ Claim 6 — LLMs structurally over-generate

**Statement.** Every configuration is distributionally distinguishable from
human-authored IaC on every structural metric.

**Test.** Two-sample Kolmogorov–Smirnov against the 634-file human corpus.

**Why this test.** KS compares full distributions without normality assumptions —
the correct instrument for "do these come from the same population?"

**Result.** 36/36 tests reject at p < 0.05. Generated 13–36 resources vs 5.31
human. Closest `gpt-4o` (D = 0.160); most divergent `phi3` (D = 0.990).

**Artifacts.** `ks_test_human_baseline.csv`
**Regenerate.** `phase4_structural.ks_test_human`

---

## ⚠️ Claim 7 — IAM and networking dominate named failure categories

**Statement.** Networking (4,554) and IAM (2,849) lead the named CIS categories.

**Caveat.** The largest bucket is "Other" (27,111) — Checkov rules without a
clean CIS mapping. This is a **tooling artifact, not a vulnerability class**, and
must be stated wherever the category breakdown is shown. The earlier revision
reported IAM as the universal #1 without this qualification.

**Artifacts.** `summary_cis_category.csv`

---

## ✅ Claim 8 — LLM judges are reliable for facts, not architecture

**Test.** Fleiss' κ across three raters; Cohen's κ (binary) and quadratic-weighted
κ (ordinal) against human consensus.

**Why these tests.** Fleiss generalizes κ beyond two raters. Quadratic weighting
is required for ordinal scales — plain κ treats 1-vs-5 as equivalent to 1-vs-2.

**Result.** Judge: hallucination 94.4% / κ = 0.640; plausibility 72.2% /
QWK = 0.795; architecture 27.8% / QWK = 0.177. Inter-human: plausibility 0.391,
**security relevance 0.059**.

**Interpretation.** Automated judges are usable for factual verification, not
architectural assessment. Separately, near-chance expert agreement on security
relevance is a substantive finding about human evaluation.

**Note on method.** Consensus ties (no unique majority) are broken by **median**
for ordinals. The previous implementation used `mode()[0]`, which silently
selected the *lowest* rating on a three-way split.

**Artifacts.** `human_agreement_metrics.json`
**Regenerate.** `phase7_human_review.agreement_metrics`

---

## ❌ Claim 9 — The Validity–Security Paradox (NOT SUPPORTED)

**Original statement.** Models most capable of writing deployable IaC are the
most prone to severe vulnerabilities. *This was the previous paper's title claim.*

**Test.** Pearson and Spearman correlation between schema-validity pass rate and
mean vulnerability density, at configuration level (n = 12).

**Result.** **r = +0.158, p = 0.625**; ρ = +0.098, p = 0.761. **No correlation.**

**Interpretation.** Pass rates cluster 27–35% across all frontier configurations
with no accompanying density relationship. Only the survivorship component
survives: `phi3` passes 5% and produces almost no parseable infrastructure.

**Why the original analysis appeared to support it.** Density was computed against
a resource-count denominator that degraded to `1` for several configurations, and
scanner coverage was incomplete — both corrected here. See
`docs/THREATS_TO_VALIDITY.md`.

**Reported as a negative result.**

---

## ❌ Claim 10 — "Thinking reduces vulnerability density up to 95%" (NOT SUPPORTED)

**Original statement.** Extended thinking reduces density 83–95%.

**Result.** True effect **−13.2%** (p = 0.012).

**Why the original figure was wrong.** Two compounding errors: (a) the Anthropic
"thinking" arm was implemented as a **system-prompt suffix**, never the extended-
thinking API, so the contrast measured prompt phrasing; (b) the density
denominator degraded to `1`, at one point producing an apparent **+2528%**
(p = 4.7e-06) where the corrected value is −14%.

**What replaces it.** Claims 2 and 3 — a smaller, real, and better-explained
effect, plus the novel CoT-vs-reasoning contrast that the correction made
possible.

**Reported as a negative result.**
