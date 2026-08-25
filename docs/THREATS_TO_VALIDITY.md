# Threats to Validity

This document records every known limitation, correction, and protocol deviation
in GenIaC-SecBench. It is written to be read by a reviewer.

Items marked **[CORRECTED]** were defects in the pre-remediation pipeline that
have been fixed; the original behaviour and its measured impact are recorded so
that results published from the earlier snapshot remain interpretable. The
pre-remediation artifacts are preserved verbatim in `data/_archive_v1/` with
their own `PROVENANCE.md`.

Items marked **[LIMITATION]** are live constraints on what the study can claim.

---

## 1. Construct validity

### 1.1 Reasoning mode was not what the label said **[CORRECTED]**

The pre-remediation pipeline implemented `-thinking` differently per vendor:

| Arm | What was actually manipulated |
|---|---|
| `gpt-5-thinking` | `reasoning_effort="high"` — a genuine vendor reasoning mode |
| `claude-opus-4-6-thinking` | **a system-prompt suffix** ("Think step-by-step…") |

No `thinking` / `budget_tokens` parameter appeared anywhere in the codebase. The
published headline — *"extended thinking reduces vulnerability density by up to
95%"* — rested principally on the Anthropic arm (−83% to −95%), which was not
extended thinking at all. The genuine OpenAI arm showed a much smaller effect
(−14% to −57%).

**Correction.** The design is now three explicit arms, and the label names the
manipulation:

- `claude-opus-4-6` — standard call
- `claude-opus-4-6-cot` — prompt-engineered chain-of-thought (the *old* "thinking" arm, retained)
- `claude-opus-4-6-thinking` — Anthropic extended thinking (`budget_tokens=16000`)

Retaining the CoT arm converts the defect into a contribution: the study can now
answer whether prompting a model to "think step by step" buys the same security
benefit as paying for vendor reasoning tokens.

**Verification that extended thinking is genuinely active:** responses carry
`thinking_blocks` with a cryptographic `signature` field and non-empty
`reasoning_content`, both of which only appear with real extended thinking.

### 1.2 Thinking budget is a ceiling the model underspends **[LIMITATION]**

With `budget_tokens=16000`, Claude Opus 4.6 spontaneously used only **~19–151
reasoning tokens** per IaC generation (median ≈56 across the measured sample).
`budget_tokens` caps thinking; it does not request it. Consequently the
extended-thinking arm may differ only marginally from the standard arm on this
task class, and a null or small result must **not** be read as "extended thinking
does not help in general" — only that the model elects to spend little of it
here. Per-generation reasoning-token counts are logged to
`data/generation_usage.jsonl` and reported rather than assumed.

`budget_tokens` is a free parameter that materially affects the outcome. It was
fixed at 16000 a priori and never tuned. A sensitivity analysis across budgets is
future work.

### 1.3 The two reasoning mechanisms are not the same construct **[LIMITATION]**

OpenAI's `reasoning_effort` and Anthropic's `budget_tokens` are different
mechanisms with different semantics. The paper frames the construct as *"the
vendor's reasoning mode enabled"*, not as a single quantity called "thinking
tokens", and does not pool the two arms.

### 1.4 A model was labelled as a previous-generation baseline but was not **[CORRECTED]**

The registry mapped the label `claude-3-5-sonnet` to the API identifier
`anthropic/claude-sonnet-4-6` — a **current**-generation model — from the initial
commit onward. The model was described throughout the documentation as an older
baseline for measuring "generation-over-generation improvement", and it served as
the **reference category for every reported IRR**.

**Correction.** The arm is renamed `claude-sonnet-4-6` throughout, matching what
was actually called. The study therefore contains **no** previous-generation
baseline, and the generation-over-generation claim is withdrawn. The GLMM
reference category has moved to a model with complete coverage in both strata
(§3.2).

### 1.5 Scenario authorship overlaps the evaluated set **[LIMITATION]**

The 100 scenarios were authored by `claude-opus-4-6`, which is itself under
evaluation (in three arms). A model may be advantaged on prompts written in its
own idiom. Mitigations: scenarios specify *requirements*, never implementation;
no model saw the scenario file; the independent LLM judge (Grok 4.6) and the
three human experts both assess scenario quality without reference to any model
output. This remains an unquantified residual risk and is disclosed as such.

---

## 2. Internal validity — measurement

### 2.1 Three scanner defects silently zeroed findings **[CORRECTED]**

All three produced valid-looking JSON on disk, raised no error, and simply
omitted findings. They were found by reconciling parsed counts against the raw
scanner output rather than trusting either.

| # | Defect | Mechanism | Impact |
|---|---|---|---|
| 1 | Checkov aborted per model directory | checkov reads `.tf` with the platform codec; on Windows that is cp1252. Five generated files contain bytes valid in UTF-8 but undefined in cp1252 (e.g. `0x9d`), raising `UnicodeDecodeError` and killing the **whole batch** | **829 findings** missing for one model |
| 2 | KICS report never read | `--output-name` was passed `Path().stem`, which strips `.1-pro` from `…gemini-3.1-pro`; KICS then applies its *own* extension handling and wrote a file with no `.json` suffix. Only the two models with a dot in their name were affected — and they collided with each other | 135 scans lost |
| 3 | KICS findings parsed as zero | the batch splitter wrote each finding under a singular `"file"` key while the parser iterates `query["files"]` | **10 of 11 models** parsed as zero KICS findings |

### 2.2 Scanner coverage was radically incomplete **[CORRECTED]**

The published results were computed from a corpus in which only Checkov had
broad coverage. Trivy and KICS had run on a minority of scenarios, yet
cross-scanner disagreement (Finding 5) was reported as a substantive result —
much of the apparent "disagreement" was simply absence of data.

| Scanner | Pre-remediation | Post-remediation |
|---|---|---|
| Checkov | 983 / 983 | 983 / 983 |
| Trivy | 324 / 983 | **983 / 983** |
| KICS | 259 / 983 | **983 / 983** |

Findings corpus: **14,791 → 31,443 (+113%)**. A machine-readable coverage
manifest is now emitted at `data/summary_reports/scan_coverage.csv` on every run,
so any future coverage gap is visible rather than inferred.

### 2.3 Two divergent `findings_raw.csv` files existed **[CORRECTED]**

Neither was authoritative: the repo-root copy had complete Checkov (10,918 rows,
matching a direct recount of the raw JSON) but **no** Trivy/KICS; the
`summary_reports/` copy had all three scanners but was **932 Checkov findings
short**. The published results derive from the latter. Both are archived; a
single regenerated file now supersedes them.

### 2.4 Checkov reports no severity **[LIMITATION]**

The open-source Checkov CLI does not assign severity tiers without a commercial
API key, so all Checkov findings carry `severity=UNKNOWN`. Severity-stratified
analyses therefore reflect Trivy and KICS only. This is a property of the tool,
not a defect, but it means the "Other/UNKNOWN" category in CIS breakdowns is an
artifact of tooling and must not be read as a vulnerability class.

### 2.5 Vendored Terraform modules — assessed, not present **[NO IMPACT]**

`terraform init` during validation left 157 `.terraform/` caches containing
third-party `.tf` files inside scenario directories, which could have been
misattributed to the models. Empirically **0 of 10,918** pre-remediation Checkov
findings originated from such a path — Checkov excludes vendored modules by
default. The caches have since been removed, and `.terraform` is now explicitly
excluded for all three scanners since Trivy and KICS do not share that default.

---

## 3. Statistical conclusion validity

### 3.1 The regression was Poisson, not negative binomial **[CORRECTED]**

The script named `nb_glmm.py`, its output `nb_glmm_results.json`, and every
document describing it stated "Negative Binomial". The code fit
`families.Poisson()`. Poisson assumes variance = mean; the measured
overdispersion on this corpus is **variance/mean = 60.4**. The project's own
methodology document had explicitly warned that Poisson would understate standard
errors and overstate significance here.

*Nuance retained for honesty:* GEE reports robust sandwich standard errors by
default, which stay consistent under a misspecified variance function, so the old
fit was not worthless — but it was labelled as a model that had never been fit.
The corrected script fits NB2 and **also emits the old Poisson-without-offset
specification** so the delta is auditable rather than asserted.

### 3.2 IRRs were not per-resource despite being reported as such **[CORRECTED]**

`docs/claims_and_statistical_evidence.md` (Claim 1) stated the model "accounts
for the exposure (Resource Count) … allowing us to calculate the true Incidence
Rate Ratio (IRR) of vulnerabilities per resource." The fitted formula contained
**no offset term**. The reported IRRs were ratios of *raw counts*, so a model
emitting 60 resources per file was credited with a far higher "rate" than one
emitting 5 purely for producing more code — the single largest driver of the
published 48–55× IRRs. `offset=log(resource_count)` is now included, making the
coefficients genuine per-resource rates.

The same passage described "nested random effects (Scenario ID)". GEE is a
marginal model with an exchangeable working correlation; it has no random
effects. The description is corrected.

### 3.3 Observations were filtered on the outcome **[CORRECTED]**

The old script dropped every model and every scenario whose **total vulnerability
count was zero** before fitting. That is selection on the dependent variable: it
discards exactly the observations carrying the "this model produced no findings"
signal and biases every estimated rate upward. All observations are now retained.

Rows with `resource_count == 0` (7 of 983, 0.7%) are excluded from the *rate*
model only, because a per-resource rate is undefined without exposure. This is
selection on exposure, not outcome, and is reported explicitly.

### 3.4 The reference category could not support the interaction **[CORRECTED]**

The baseline was `claude-3-5-sonnet`, which had **zero** simple-stratum
observations. Every `model × complexity` interaction term — including the
headline "GPT-4o complexity relaxation" effect (IRR 14.36) — was estimated
against an empty reference cell. The reference is now auto-selected from models
with coverage in both strata.

### 3.5 The omnibus test discarded 87% of the simple stratum **[CORRECTED]**

Friedman requires complete blocks, and the code called `pivot.dropna()`. With one
model absent from the simple stratum entirely and another present in 8 of 60
scenarios, **the simple-stratum test ran on N=8 of 60 scenarios**, reported
without qualification alongside an N=40 complex-stratum result.

Worse, listwise deletion left the two strata comparing **different model sets**,
after which Kendall's *W* was compared across them (0.640 vs 0.440) and
interpreted as "model spread widens on complexity". *W* is a function of *k*;
that comparison was not licensed.

**Correction.** The primary omnibus test is now **Skillings–Mack**, the
generalization of Friedman to incomplete block designs, which uses every scenario
containing at least two models. Complete-case Friedman is still reported
alongside, with the number of discarded blocks stated, so the cost of missingness
is visible. A single explicit model set is enforced across both strata.

*Implementation is validated against Friedman on complete data (agreement to
~1e-14) and reproduces the worked example in
`docs/methodology/iac_benchmark_methodology.md` exactly (χ² = 8.400).*

### 3.6 The omnibus metric was single-scanner **[CORRECTED]**

The tests ran on `checkov_vulns_norm` — one scanner — while the paper argues that
single-scanner results are biased (Finding 5). With full tri-scanner coverage now
available, the default metric is total vulnerability density across all three.
The old metric remains selectable for comparability.

### 3.7 Underpowered paired contrasts **[LIMITATION]**

The reasoning-mode contrasts are paired Wilcoxon tests over at most 60 (simple)
or 40 (complex) scenarios, with heavily zero-inflated outcomes. Large observed
effect sizes may still fail to reach α=0.05. Effect sizes and confidence
intervals are reported alongside p-values, and non-significant results are
described as such rather than as evidence of absence.

### 3.8 Models with no findings are not estimable **[LIMITATION]**

`phi3` produces essentially no parseable infrastructure and consequently almost
no findings. In a log-link count model this approaches separation and its
coefficient diverges. It is reported as *not estimable (no findings)* rather than
as a numeric IRR.

---

## 4. Human evaluation

### 4.1 Protocol drift from the written plan **[LIMITATION]**

| Planned (`human_review_protocol.md`) | Executed |
|---|---|
| 2 reviewers | **3** reviewers |
| Cohen's κ | **Fleiss' κ** (correct for 3 raters) |
| 20 sampled scenarios | 20 distributed; **18** scored by all three |
| Judge = GPT-5 | **Grok 4.6** |

The deviations are defensible — Fleiss' κ is the right statistic for three
raters, and Grok is arguably a *better* judge choice since it is outside every
lab in the evaluated set (the protocol required exactly this property; GPT-5 was
named before OpenAI models entered the set). They were simply never written down.
Reported reliability uses the **18 scenarios scored by all three reviewers**,
since κ requires complete blocks.

### 4.2 Low inter-rater agreement on subjective criteria **[LIMITATION]**

Fleiss' κ: plausibility 0.391, hallucination 0.266, coherence 0.209, security
relevance 0.058. Agreement on the most subjective criterion is barely above
chance. This is itself a reported finding — it is the argument for multi-rater
consensus over any single reviewer — but it means the human baseline for
*security-test relevance* is weak, and the LLM-judge-vs-human agreement on that
criterion should be read with corresponding caution.

### 4.3 Reviewers were recruited as coauthors **[LIMITATION]**

Reviewers had an incentive toward convergence. The protocol required independent
scoring before any discussion, and κ is computed on the independent scores. This
is a procedural safeguard, not a guarantee.

### 4.4 Human review is unaffected by the regeneration **[NO IMPACT]**

Human and LLM-judge evaluations are keyed on `scenario_id` and contain no model
column: reviewers assessed the **scenarios**, never any model's output. The 100
scenarios are unchanged by the regeneration, so the stratified sample, all three
reviewers' scores, Fleiss' κ, and the human-vs-judge agreement carry over intact.

---

## 5. External validity

### 5.1 Scanners detect misconfiguration, not exploitability **[LIMITATION]**

Checkov, Trivy, and KICS flag deviations from policy. A finding is not a proven
vulnerability, and their union is not a complete account of insecurity. "Zero
findings" means "nothing these three rulesets flag", not "secure".

### 5.2 Static templates, never deployed **[LIMITATION]**

No generated infrastructure was provisioned. Runtime posture, drift, and
misconfiguration arising from composition with existing infrastructure are out of
scope.

### 5.3 Point-in-time model snapshot **[LIMITATION]**

Hosted models change without notice. Results describe the models as accessed in
the stated collection window, not stable properties. Exact API identifiers and
generation parameters are recorded in `docs/methodology/` for this reason.

### 5.4 Scenario-format coverage is uneven **[LIMITATION]**

Terraform dominates the corpus; CloudFormation, ARM, and Kubernetes are less
represented, and the three scanners' rule coverage differs by format. Pooled
cross-format results may reflect differential rule density rather than
differential model behaviour. Format-stratified results are reported where the
per-cell sample size supports it.

### 5.5 Human baseline is not a matched control **[LIMITATION]**

The 634 human-authored files come from three public repositories, many of which
are curated examples rather than production infrastructure, and they were not
written against these 100 scenarios. The KS tests establish that the
distributions differ; they do not establish that human engineers would have
written differently *for these tasks*.

---

## 6. Reproducibility

### 6.1 Path resolution was broken **[CORRECTED]**

Statistics scripts resolved the repo root as
`Path(__file__).resolve().parent.parent.parent`, which after the package
reorganization pointed at `src/`, not the repository root. Every affected script
would fail with `FileNotFoundError` for a third party. Root resolution is now
centralized in `geniac_secbench/config.py`.

### 6.2 Scanner discovery was machine-specific **[CORRECTED]**

Scanner paths were hardcoded to one developer's Windows install locations,
so the documented Docker workflow could not have worked. Discovery is now
env var → `PATH` → `third_party/`.

### 6.3 Checkov requires an isolated environment **[LIMITATION]**

Checkov depends on `bc-python-hcl2`, which claims the same `hcl2` import name as
the `python-hcl2` package the structural-metrics code needs for modern Terraform
syntax. They cannot coexist. Checkov runs from `.venv_checkov/` and must be
invoked as `<venv_python> -m checkov.main` — the Windows `.cmd` shim re-execs
against whatever `python` it finds on PATH, silently ignoring its own venv.

### 6.4 Reviewer identities are not distributable **[LIMITATION]**

Reviewers supplied name, email, and LinkedIn for credential verification.
Published files are pseudonymized (`R1`–`R3`); the mapping is retained locally
and is not in version control.
