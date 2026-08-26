# GenIaC-SecBench — Comprehensive Findings

**Paper:** *Three Times Less Secure: A Human-Anchored Benchmark of LLM-Generated
Infrastructure-as-Code*

> Interpretive companion to `RESULTS.md`, which is generated directly from
> `data/summary_reports/` and is the authoritative source for every number.
> Regenerate it with
> `python -m geniac_secbench.phase8_reporting.findings_report`.
>
> **This document supersedes the pre-remediation findings.** Two claims in the
> earlier version did not survive re-analysis; both are reported below as
> findings rather than removed. The pre-remediation artifacts are preserved in
> `data/_archive_v1/` with a provenance record. See `docs/THREATS_TO_VALIDITY.md`
> for the full correction log.

---

## Benchmark at a glance

| Parameter | Value |
|---|---|
| Scenarios | 100 (60 simple + 40 complex) |
| Model configurations | 12 (9 models, 4 vendors, 3 reasoning modes on one base) |
| Artifacts generated | **1,196 of 1,200** (99.7%) |
| Scanners | Checkov, Trivy, KICS — **100% coverage, all three** |
| Findings | **38,803** (Checkov 14,017 · KICS 14,033 · Trivy 10,753) |
| Human reference corpus | **634 hand-written files, 5,473 findings** |
| Independent judge | Grok 4.6 (outside every vendor under test) |
| Human reviewers | 3 cloud-security practitioners |

---

## Finding 1 — LLM-generated IaC is ~3.5× less secure than human-authored IaC

**The central result, and the one the study was structurally built to produce but
had never actually computed** — the human corpus had only ever been compared
*structurally*, never security-scanned.

### Comparison must be size-matched

Vulnerability density is strongly inverse to artifact size:

- Human corpus: 4.51 findings/resource at 1 resource → **1.10** at 20+
- LLM corpus: Spearman **ρ = −0.55, p = 1.7e-78**

The corpora differ in scale (human mean 5.31 resources; simple generations ≈3;
complex ≈50), so an unmatched comparison measures *artifact size*, not security.
An early unmatched analysis suggested LLMs were indistinguishable from humans on
complex scenarios — that was an artifact of exactly this confound.

### Matched result

| resources | human | LLM | ratio | p (Mann–Whitney) |
|---|---:|---:|---:|---:|
| 1 | 4.51 | 22.12 | **4.9×** | 2.9e-29 |
| 2 | 2.72 | 6.46 | 2.4× | 9.7e-04 |
| 3–5 | 1.70 | 3.84 | 2.3× | 2.4e-15 |
| 6–10 | 1.65 | 2.89 | 1.8× | 3.0e-05 |
| 11–20 | 1.28 | 2.99 | 2.3× | 1.0e-03 |
| 20+ | 1.10 | 1.48 | 1.4× | 0.058 (n.s.) |

Aggregated per configuration over shared strata, **every arm falls between
3.21× and 3.87×** the human baseline — four vendors, open and closed weights,
three reasoning modes, all inside a 0.66× band. That consistency is itself the
finding: this is a property of current LLM-generated IaC, not of any one model.

**The gap is largest where the task is simplest.** Where a human writes a minimal
single-resource template, models emit substantially more flagged configuration.

*Figures:* `human_vs_llm_density`, `llm_human_ratio`, `density_vs_resources`

---

## Finding 2 — Vendor reasoning beats prompted chain-of-thought

Three arms on one base model, one variable toggled. Simple stratum (largest n):

| contrast | n | Δ density | p |
|---|---:|---:|---:|
| standard → **extended thinking** | 60 | **−13.2%** | **0.012** ✅ |
| **prompted CoT → extended thinking** | 60 | **−12.0%** | **0.0013** ✅ |
| standard → prompted CoT | 60 | −1.3% | 0.238 |
| gpt-5 → `reasoning_effort=high` | 58 | −10.2% | 0.153 |

"Think step by step" buys **no measurable security benefit**. Paying for
reasoning tokens does — modestly, but significantly, and significantly *more*
than the prompt trick.

This contrast exists only because the arms were separated. The pre-remediation
pipeline implemented Anthropic "thinking" as a system-prompt suffix while
labelling it extended thinking, which is how the confound was discovered.

*Figure:* `reasoning_mode_contrasts`

---

## Finding 3 — Reasoning barely engages on IaC

| stratum | reasoning tokens (median) | completion tokens (median) | share |
|---|---:|---:|---:|
| simple | 29 | 886 | ~3% |
| complex | 151 | 18,533 | **~0.8%** |

Against a generous configured allowance, the model spends **under 1% of its
output budget on reasoning** for complex IaC. The budget is a ceiling the model
may underspend, not a target.

This bounds Finding 2 mechanistically: a modest measured effect must **not** be
read as "reasoning does not help" — on this task class the mechanism is barely
exercised. It also reframes the research question from *"does thinking improve
security?"* to *"does the model think at all here?"*

*Figure:* `reasoning_token_share`

---

## Finding 4 — Models differ, but the classical test cannot show it

| stratum | Skillings–Mack | df | p | blocks used | complete-case Friedman |
|---|---:|---:|---:|---:|---|
| simple | χ² = 69.3 | 10 | 6.0e-11 | **60** | **0 blocks** |
| complex | χ² = 81.2 | 11 | 8.7e-13 | **40** | **0 blocks** |

With 12 configurations and realistic coverage gaps, **no scenario has every
configuration present** — complete-case Friedman retains zero blocks. The
standard test in this literature (Demšar 2006) is not merely underpowered here;
it is **uncomputable**.

Transferable methods point: multi-model benchmarks routinely lose cells to
refusals, quotas, and truncation, and should default to incomplete-block
statistics.

---

## Finding 5 — Rate model, and survivorship inverted

Negative binomial GEE, exposure offset `log(resource_count)`, reference
`claude-opus-4-6`. Overdispersion **variance/mean = 130.0**, so NB2 is required
by evidence rather than assertion.

| configuration | IRR | 95% CI | p |
|---|---:|---|---:|
| `claude-opus-4-6-cot` | **0.73** | [0.54, 0.99] | 0.041 ✅ |
| `claude-opus-4-6-thinking` | 0.87 | [0.75, 1.01] | 0.070 |
| `gemini-3.1-pro` | 1.30 | [1.15, 1.47] | 2.2e-05 ✅ |
| `phi3` | **4.64** | [3.12, 6.89] | 2.9e-14 ✅ |

**`phi3` inverts the naive reading.** It records the fewest absolute findings and
looks safest by raw count, but declares almost no parseable infrastructure —
*per resource* it is the worst configuration measured. Absolute counts must not
be used for cross-model comparison.

---

## Finding 6 — LLMs structurally over-generate

Two-sample KS against the 634-file human corpus: **36/36 tests reject**, all
p < 0.05. Generated templates declare **13–36 resources** on average against
**5.31** for humans.

- Closest to human: `gpt-4o` (D = 0.160, p = 0.021)
- Most divergent: `phi3` (D = 0.990)

---

## Finding 7 — Where models fail, and where engines disagree

| CIS category | findings |
|---|---:|
| Other (unmapped) | 27,111 |
| **Networking** | 4,554 |
| **IAM** | 2,849 |
| Logging/Monitoring | 2,149 |
| Encryption | 2,140 |

Networking and IAM dominate the named categories — the same failure modes
catalogued for hand-written IaC. The large "Other" bucket is Checkov rules
without a clean CIS mapping: **a tooling artifact, not a vulnerability class**.

Engines disagree in volume (Checkov 14,017 · KICS 14,033 · Trivy 10,753), which
is the convergent-validity argument for using three vendors. A single-engine
study inherits that engine's rule coverage as ground truth.

*Figures:* `cis_category_heatmap`, `scanner_agreement`, `severity_distribution`

---

## Finding 8 — LLM judges: reliable on facts, not architecture

**Inter-rater agreement** (Fleiss' κ, 3 practitioners, 18 commonly-scored scenarios):

| criterion | κ | Landis–Koch |
|---|---:|---|
| real-world plausibility | 0.391 | fair |
| hallucination flag | 0.266 | fair |
| architectural coherence | 0.210 | fair |
| **security-test relevance** | **0.059** | **slight — near chance** |

Experienced engineers **do not agree** on whether a scenario poses a meaningful
security decision. That is a substantive result about the difficulty of human
security evaluation, not merely a limitation of this panel.

**Judge vs human consensus:**

| criterion | exact | within ±1 | κ |
|---|---:|---:|---:|
| hallucination flag | 94.4% | — | 0.640 (Cohen) |
| real-world plausibility | 72.2% | 100% | 0.795 (QWK) |
| security-test relevance | 61.1% | 88.9% | 0.489 (QWK) |
| **architectural coherence** | 27.8% | 66.7% | **0.177** |

**Actionable boundary: use automated judges for factual verification, not
architectural assessment.**

---

## Finding 9 — Two negative results

### 9a. The Validity–Security Paradox is not supported

The intuitive hypothesis — models better at deployable code produce more
vulnerable code — fails:

- Pearson **r = +0.158, p = 0.625**
- Spearman **ρ = +0.098, p = 0.761**

Pass rates cluster 27–35% across all frontier configurations with no density
relationship. Only the survivorship component holds (`phi3`: 5% pass, almost no
parseable infrastructure).

*This was the previous paper's title claim.* It is reported here as a negative
result.

### 9b. Complete-case Friedman is uncomputable

See Finding 4.

---

## Finding 10 — Silent-failure taxonomy in multi-tool benchmarks

Ten defects were found during remediation. **Every one produced valid-looking
output with no error raised:**

| defect | effect |
|---|---|
| Platform encoding mismatch (cp1252 vs UTF-8) | zeroed one configuration (+829 findings recovered) |
| Filename extension handling | zeroed KICS for both dotted-name models |
| Split-output schema mismatch | zeroed KICS for **10 of 12** configurations |
| Append-only validation CSV | 937 duplicate rows; master table doubled |
| Ungenerated scenarios scored as zero-vuln | credited the arm under test with unearned security |
| Resource count degrading to `1` | **+2528% artifact** where truth is −14% |
| Poisson fitted, labelled negative binomial | understated standard errors |
| Missing exposure offset | IRRs were raw-count ratios, not per-resource |
| Outcome-based row filtering | selection on the dependent variable |
| Consensus tie-break via `mode()[0]` | silently selected the *lowest* rating |

**Lesson: in multi-tool benchmarks, reconcile derived counts against source
artifacts. Never trust the pipeline's own output.**

---

## Summary

1. LLM-generated IaC is **3.2×–3.9×** less secure than human-authored IaC, size-matched, consistently across vendors.
2. The gap is **widest on the simplest tasks** (4.9× → 1.4×).
3. Vendor reasoning modes beat prompted CoT (**−12.0%, p=0.0013**); prompted CoT alone does nothing.
4. Reasoning **barely engages** on IaC (<1% of output), bounding the achievable effect.
5. LLMs **over-generate** infrastructure (13–36 resources vs 5.31).
6. **Networking and IAM** dominate named failure categories.
7. LLM judges are trustworthy for **facts, not architecture**; experts agree near chance on security relevance.
8. The **Validity–Security Paradox does not hold**.
9. Absolute counts mislead; `phi3` looks safest and is worst per resource.
10. Complete-case Friedman is **uncomputable** on realistic benchmark designs.
