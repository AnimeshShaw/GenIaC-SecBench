# IaC Benchmark Study — Consolidated Checklist

Companion to `iac_benchmark_methodology.md` and `human_review_protocol.md`. This is the tracking list, not the explanation — check items off as you go.

---

## Pre-flight (do these before anything else compounds)

- [ ] Lock the final model list — exact names, exact modes, exact count. Your description has drifted across this conversation (six-or-seven, then GPT-5 + GPT-5-thinking added). Write the final list once, use it everywhere from here on.
- [ ] Document the exact generation protocol verbatim for your methods section: stateless API calls, no system prompt, no shared memory, temperature/params if set.
- [ ] Confirm the format split across your 100 scenarios: how many Terraform vs. CloudFormation vs. Azure ARM, and whether that split is even across the 40 complex / 60 simple tiers or incidental.
- [ ] Confirm scenario numbering/ID scheme is consistent across every downstream artifact (sampling script, results table, review sheets) — this is what lets you join everything back together later.

## Phase 2 — Schema / Syntactic Validation

- [ ] `terraform validate` (or `terraform plan -refresh=false`) on every Terraform output
- [ ] `cfn-lint` on every CloudFormation output
- [ ] ARM template validation on every Azure output — `ARM-TTK` (PowerShell module) or `az deployment group validate` / `bicep build --stdout` if you convert to Bicep first
- [ ] Log pass/fail + raw error text per generation, tagged by format
- [ ] Report the per-model, per-format schema-validity pass rate as its own result — cheap to produce, and it's your strongest anti-hallucination evidence

## Phase 3 — Multi-Engine Security Scanning

- [ ] Confirm Checkov, Trivy, and KICS all cover your three formats (they do — Terraform, CloudFormation, and ARM are supported by all three)
- [ ] Run all three with JSON output
- [ ] Exclude or separately tag anything that failed Phase 2 — don't let invalid IaC pollute the vulnerability comparison
- [ ] Compute both raw and normalized (vulns / resource_count) counts, per tool, per severity tier

## Phase 4 — Structural Comparison vs. Reference Dataset

- [ ] Extract resource count, resource-type diversity, dependency depth, IAM complexity from both your dataset and the manual reference set
- [ ] Run the Kolmogorov–Smirnov test on the distributions

## Phase 5 — Independent LLM Judge

- [ ] Finalize judge model — needs to be outside every lab already in your test set (OpenAI, Google, Anthropic, Mistral, Meta are all spoken for)
- [ ] Pre-register the rubric before running a single scenario through it
- [ ] Structured JSON output, run on all 100 scenarios
- [ ] Treat as secondary evidence only until Phase 7's kappa check tells you whether it's trustworthy

## Phase 6 — Statistics

- [ ] Consolidate everything into the master results table (one row per scenario × model)
- [ ] Friedman test, run separately for complex and simple strata
- [ ] Kendall's W for effect size
- [ ] Post-hoc: Wilcoxon signed-rank + Holm-Bonferroni (or Nemenyi) on any significant Friedman result
- [ ] Mixed-effects negative binomial regression (or GEE in Python) with scenario random intercept, model × complexity interaction
- [ ] Bonus paired comparison: Opus 4.6 standard vs. thinking mode; same for GPT-5 vs. GPT-5-thinking if both are confirmed in the final model list

## Phase 7 — Human Review Handoff

- [ ] Run `stratified_sampling.py` against the finalized scenario folder
- [ ] Distribute samples per `human_review_protocol.md` — two reviewers, independent, no shared sheet
- [ ] Compute Cohen's kappa (plain for the hallucination flag, weighted for the 1–5 criteria)
- [ ] Reconcile flagged disagreements, produce adjudicated scores
- [ ] Compute LLM-judge-vs-human kappa on the same sample

## Reporting & Presentation

- [ ] **Table** — descriptive stats: mean/median normalized vulnerability density per model × complexity tier
- [ ] **Boxplot** — normalized vuln density per model, split by complexity — shows spread, not just the mean; this is usually the figure that carries the "models degrade under complexity" finding
- [ ] **Heatmap** — vulnerability category (IAM, encryption, logging, network exposure, etc.) × model — shows *what kind* of mistake each model tends to make, and tends to be the most-cited figure in this class of paper
- [ ] **Stacked bar** — severity breakdown (critical/high/medium/low) per model
- [ ] **Bar chart** — schema-validity pass rate per model (Phase 2 output) — cheap, striking, and directly rebuts the hallucination objection
- [ ] **Table** — Friedman + post-hoc results with significance markers
- [ ] **Table** — KS test result, structural comparison vs. reference dataset
- [ ] **Table** — kappa results: inter-rater, and LLM-judge-vs-human
- [ ] Report raw *and* normalized vulnerability counts everywhere — never raw alone
- [ ] Separate figures/tables for the three IaC formats if their vulnerability profiles turn out to differ materially — don't silently pool Terraform, CloudFormation, and ARM results if the tools' rule coverage differs by format

## Before submission

- [ ] Cite and explicitly differentiate from Vargas, Mansilha & Kreutz, "Security-First Evaluation of Text-to-Terraform" (arXiv:2608.02672, accepted SBSeg 2026) — the closest existing published work, found this week. Your scenario count, format coverage, complexity stratification, and reliability methodology (kappa, LLM-judge validation) all exceed what that paper reports — say so, with numbers, not just a citation.
- [ ] Pick target venue tier before final formatting — length, framing, and related-work depth all depend on it
