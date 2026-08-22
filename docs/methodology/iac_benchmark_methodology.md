# IaC Security Benchmark — Methodology & Execution Guide

Scope: everything automatable, end to end. Human review (execution, not the sampling that feeds it) is intentionally excluded — that's a separate track you're running yourself.

---

## Study Recap

**Question:** Do LLMs generate secure IaC by default?

**Dataset:** 100 scenarios (40 complex / 60 simple), authored once by Claude Opus 4.6. Each scenario given — stateless API call, no system prompt, no shared memory — to your full model set (Llama 3, a Mistral variant, Gemini 3.7 Flash, Gemini 3.1 Pro, Claude Opus 4.6, Claude Opus 4.6 thinking, and whichever else rounds out your six-or-seven). **Lock the exact model list and count before Phase 3 aggregation** — "six or seven" can't survive into the results table.

**Result:** 100 × (number of models) generations. Each model faces the identical 100 scenarios → this is a repeated-measures design, scenario-matched across models. That structure is what Part C is built around.

---

## Part A — Pipeline

### Phase 1 — Dataset Generation ✅ Done
One thing to lock in writing now, while you remember it exactly: the precise generation protocol (stateless, no system prompt, temperature/params if set, exact prompt template). This goes in your methods section verbatim — reviewers will ask.

### Phase 2 — Syntactic / Schema Validation
Run before or alongside Checkov, on every generation:
- `terraform validate` (or `terraform plan -refresh=false` for deeper checks) for Terraform outputs
- `cfn-lint` if any CloudFormation is in the mix

This is your strongest, cheapest evidence against the "hallucinated scenario" objection — a fabricated resource attribute fails against the real provider schema, deterministically. Log **pass/fail + error text** per generation. The fail rate per model is itself a result worth reporting (schema-hallucination rate by model).

### Phase 3 — Multi-Engine Security Scanning
- **Checkov** (running) — Palo Alto ruleset, broadest coverage
- **Trivy** (`trivy config`) — replaces tfsec. tfsec is deprecated (folded into Trivy in 2024, no new rules since, won't cover Terraform resources released after mid-2025). Don't run both; Trivy already contains tfsec's rules.
- **KICS** (Checkmarx) — ~2,000 Rego-based queries, third independent vendor ruleset

Three different vendors' opinions = a real convergent-validity argument, not two tools with shared lineage pretending to be independent.

Run all three on generations that passed Phase 2 (or run on everything but flag Phase-2 failures as a separate category — don't silently fold "invalid Terraform" into your vulnerability counts). Get JSON output from every tool so it's machine-parseable.

**Normalize before comparing.** Raw vulnerability count is confounded by script size — a 40-resource complex scenario will out-count a 5-resource simple one regardless of security quality. Compute:
- `vulns_per_resource = raw_vuln_count / resource_count`
- Optionally `vulns_per_line` as a secondary check

Report both raw and normalized; the normalized figure is what actually answers your research question.

### Phase 4 — Structural Comparison vs. the Open-Source Reference Dataset
Pull the same structural metrics from both your LLM-generated scenarios and the manually-authored reference set: resource count, resource-type diversity, dependency depth, IAM policy complexity. Compare the distributions with a **Kolmogorov–Smirnov test** (Part C). If your LLM-generated complex scenarios sit in a statistically indistinguishable distribution from the human-authored ones, that's a quantitative, non-LLM answer to "are these scenarios realistic."

### Phase 5 — Independent LLM Judge
Use a model touched by neither role in your design. Claude family wrote the scenarios; Gemini and Claude families are both under test — so avoid both. **GPT-5** is untouched by either role and is your cleanest pick.

- Fixed, pre-registered rubric (architectural coherence / real-world plausibility / does it test something meaningful) — not open-ended "rate 1–10"
- Structured JSON output for reproducibility
- Run on all 100 scenarios (or at minimum the 40 complex)
- **This is a secondary/triangulating signal, not primary evidence.** Its value depends entirely on how well it agrees with your human reviewers later — flag that as a follow-up step once human scores exist; don't claim validity for it until then.

### Phase 6 — Statistical Analysis
Consolidate everything into one tidy table (schema below), then run the tests in Part C. This is where the actual "do LLMs generate secure IaC" answer comes from.

### Phase 7 — Handoff to Human Review
Run `stratified_sampling.py` (separate file) against your scenario folder. It produces the review sample, a sampling manifest, and a blank review-tracking sheet. Everything past this point — the actual review, inter-rater agreement — is your track.

---

## Part B — Master Results Table (schema)

One row per (scenario, model) pair:

| column | meaning |
|---|---|
| `scenario_id` | matches the 100-scenario source of truth |
| `complexity` | complex / simple |
| `model` | model name |
| `model_mode` | e.g. `standard` / `thinking` — keep Opus 4.6 and Opus 4.6-thinking distinguishable |
| `terraform_valid` | bool, from Phase 2 |
| `resource_count` | from the generated IaC |
| `checkov_vulns`, `trivy_vulns`, `kics_vulns` | raw counts |
| `checkov_vulns_norm`, etc. | vulns / resource_count |
| `severity_critical/high/medium/low` | per tool if you want severity-weighted analysis later |

This table is the direct input to every test in Part C.

---

## Part C — Statistical Toolkit

### 1. Kolmogorov–Smirnov test (Phase 4 — are your scenarios structurally realistic?)

**Proves:** whether two distributions (e.g. resource-count distribution of your LLM-generated scenarios vs. the manual reference dataset) differ significantly.

**Formula:**
```
D = sup_x |F1(x) - F2(x)|
```
F1, F2 are the empirical cumulative distribution functions of the two samples. Compare D against a critical value:
```
D_crit ≈ c(α) * sqrt((n1 + n2) / (n1 * n2))
```
c(0.05) ≈ 1.36. If D < D_crit, you fail to reject "same distribution" — i.e., no statistical evidence your LLM scenarios are structurally distinguishable from the human-authored ones. That's the result you want.

**Tooling:** `scipy.stats.ks_2samp`.

---

### 2. Friedman test (Phase 6 — the core "do models differ" question)

**Proves:** whether ≥3 related samples (your 7 models, each scored on the *same* 100 scenarios) differ in central tendency. This is the repeated-measures-correct alternative to running unpaired tests per model.

**How it works:** within each scenario (block), rank the models by vulnerability count (1 = fewest). Sum ranks per model across all scenarios, then:
```
χ²_F = [12 / (N·k·(k+1))] · Σ(R_j²) − 3·N·(k+1)
```
N = number of scenarios (blocks), k = number of models, R_j = summed rank for model j. Compare χ²_F against the chi-square distribution with df = k−1.

**Worked example** (5 scenarios, 3 models, vulnerability counts):

| Scenario | Model A | Model B | Model C |
|---|---|---|---|
| S1 | 4 (r2) | 2 (r1) | 7 (r3) |
| S2 | 5 (r2) | 3 (r1) | 6 (r3) |
| S3 | 3 (r2) | 1 (r1) | 8 (r3) |
| S4 | 6 (r2) | 4 (r1) | 9 (r3) |
| S5 | 2 (r1) | 5 (r2) | 10 (r3) |

Rank sums: R_A = 9, R_B = 6, R_C = 15. N=5, k=3.

```
χ²_F = [12 / (5·3·4)] · (9² + 6² + 15²) − 3·5·4
     = 0.2 · (81 + 36 + 225) − 60
     = 0.2 · 342 − 60
     = 68.4 − 60 = 8.4
```
df = 2, critical value at α=0.05 is 5.99. **8.4 > 5.99 → the models significantly differ** — this isn't just noise; Model B is consistently generating fewer vulnerabilities than A and C.

**Effect size — Kendall's W:**
```
W = χ²_F / [N·(k−1)] = 8.4 / (5·2) = 0.84
```
W ranges 0–1; 0.84 is a strong, consistent effect (not borderline significance on a huge N).

**Tooling:** `scipy.stats.friedmanchisquare`.

**Run this separately for the complex and simple strata** — you almost certainly expect the model spread to widen on complex scenarios, and pooling would mask that.

---

### 3. Post-hoc pairwise comparisons (only if Friedman is significant)

Two standard options — pick one, don't run both and cherry-pick:

**Nemenyi test:** critical difference on *average* ranks:
```
CD = q_α · sqrt(k·(k+1) / (6·N))
```
q_α from the studentized range table (k=3, α=0.05 → q≈2.343). Any pair of average ranks differing by more than CD is significant.

**Wilcoxon signed-rank + Holm-Bonferroni** (more common in ML benchmark papers, generally preferred — see Demšar 2006): for each model pair, rank the paired differences d_i = vuln_i(modelA) − vuln_i(modelB) by |d_i|, sum ranks of positive vs negative differences (W+, W−), test statistic W = min(W+, W−), normal approximation:
```
Z = (W − μ_W) / σ_W,   μ_W = N(N+1)/4,   σ_W = sqrt(N(N+1)(2N+1)/24)
```
Then correct for multiple comparisons: sort p-values ascending, compare the i-th smallest to α/(m−i+1), reject sequentially until the first failure (Holm-Bonferroni).

**Tooling:** `scikit-posthocs` (`posthoc_nemenyi_friedman`) or `scipy.stats.wilcoxon` + `statsmodels.stats.multitest.multipletests(method="holm")`.

---

### 4. Mixed-effects Negative Binomial regression (the confirmatory model)

**Proves:** the same thing as Friedman, but more powerfully — gives you per-model effect sizes, lets you test the complexity interaction directly (does a model degrade disproportionately on complex scenarios — probably your actual headline finding), and properly absorbs the scenario-level pairing as a random effect instead of needing separate tests per stratum.

**Why negative binomial and not plain Poisson:** Poisson assumes mean = variance. Vulnerability counts are almost always overdispersed (variance > mean) — check with a dispersion statistic; if overdispersion is present (it will be), Poisson standard errors are too small and you'll overstate significance.

**Model:**
```
log(μ_ij) = β0 + β1·Model_j + β2·Complexity_i + β3·(Model_j × Complexity_i) + u_i
u_i ~ N(0, σ²)          [random intercept per scenario i]
Var(Y_ij) = μ_ij + μ_ij² / θ    [NB dispersion parameter θ]
```
μ_ij = expected vulnerability count for scenario i under model j. β1 gives per-model effects (relative to a reference model), β3 is the interaction you actually care about.

**Tooling:** R's `glmmTMB` or `lme4` (best-supported route for NB-GLMM). Python-native alternative: `statsmodels.GEE` (Generalized Estimating Equations) with an exchangeable correlation structure grouped by `scenario_id` — not a true mixed model but handles the repeated-measures structure correctly and stays in Python if you want to avoid an R dependency.

---

### Bonus analysis your design already supports for free

Opus 4.6 vs. Opus 4.6-thinking is a *paired, controlled comparison of extended thinking on security output* — same model, same 100 scenarios, one variable toggled. A single Wilcoxon signed-rank test on that pair alone (ignoring the other models) is a clean, well-motivated result you'll likely want to headline separately from the cross-model comparison.

---

## What's deliberately not in this document

Human review protocol, rubric administration, and Cohen's kappa for inter-rater agreement — that's your track. When the scores come back, the kappa computation itself is a five-minute follow-up whenever you want it.
