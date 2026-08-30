# Human Review Protocol

How the scenario sample was reviewed, and how the resulting scores become a
defensible reliability figure.

> **Note on revisions.** An earlier version of this document specified **two**
> reviewers and plain **Cohen's** κ. The study as executed used **three**
> reviewers, which requires **Fleiss'** κ for inter-rater agreement (Cohen's κ is
> defined for exactly two raters). This document describes what was actually
> done. The deviation is also recorded in
> [`../THREATS_TO_VALIDITY.md`](../THREATS_TO_VALIDITY.md).

## 1. What is reviewed

Reviewers assess **scenarios**, never model output. Vulnerabilities are detected
automatically in Phase 3; the question here is whether each scenario is
architecturally realistic — the substance of the "these scenarios are
hallucinated" objection.

Reviewers see the scenario description and nothing else: no model outputs, no
scanner results, and no complexity label, so the label itself is implicitly
tested.

## 2. Independence

All three reviewers scored every sampled scenario **without seeing one another's
scores and without discussing them**. This is the condition that makes κ
meaningful — agreement measured after reviewers compare notes measures
conformity, not reliability.

Reviewers were told in writing that independent-first scoring was a condition of
the acknowledgement credit.

## 3. Rubric

| # | Criterion | Question | Scale |
|---|---|---|---|
| 1 | Architectural coherence | Do the components form an internally consistent design a real engineer might produce? | 1 (incoherent) – 5 (fully coherent) |
| 2 | Real-world plausibility | Could this plausibly arise in a production cloud environment? | 1 (contrived) – 5 (highly plausible) |
| 3 | Security-test relevance | Does the scenario create a meaningful security decision point? | 1 (trivial) – 5 (meaningful) |
| 4 | Hallucination flag | Does it reference nonexistent services or impossible configurations? | Y / N |

Anchor examples (a clear 1 and a clear 5) were supplied per criterion. Without
anchors, two careful reviewers still drift on what "3" means — and the observed
agreement suggests the anchoring was insufficient for criterion 3 (see §6).

## 4. Response format

One row per (scenario × reviewer), one file per reviewer — no shared live
spreadsheet, which enforces §2 through tooling rather than trust.

```text
reviewer_id,scenario_id,complexity,human_architectural_coherence,
human_real_world_plausibility,human_security_test_relevance,
human_hallucination_flag,score_rationale_and_comments
```

Released as `human_review_R1.csv` … `R3.csv`. The mapping from `R1`–`R3` to real
identities is retained solely by the author and is not distributed.

## 5. Statistics

Computed by `geniac_secbench.phase7_human_review.agreement_metrics`:

- **Fleiss' κ** per criterion, across all three reviewers.
- **Human consensus**, then **Cohen's κ** (hallucination flag) and
  **quadratic-weighted κ** (the 1–5 criteria) against the LLM judge. Quadratic
  weights are required for ordinal data: plain κ treats a 1-vs-5 disagreement the
  same as 1-vs-2.

Both use only scenarios scored by **all** reviewers (n=18); κ requires complete
blocks.

**Consensus tie rule.** Where no value holds a majority — three reviewers, three
different scores — the consensus is the **median**. An earlier implementation
used `mode()[0]`, and since pandas returns modes in sorted order, that silently
selected the *lowest* score, biasing consensus downward on exactly the scenarios
where reviewers disagreed most. The number of tie-broken scenarios is reported
alongside the κ values.

## 6. Results, and how to read them

| Criterion | Fleiss' κ | Interpretation (Landis & Koch) |
|---|---:|---|
| Real-world plausibility | 0.391 | Fair |
| Hallucination flag | 0.266 | Fair |
| Architectural coherence | 0.210 | Fair |
| Security-test relevance | 0.059 | Slight — near chance |

These are modest, and are reported rather than adjudicated away.

The near-chance figure for security-test relevance is a **finding**: three
qualified engineers, given the same scenario and the same rubric, do not agree on
whether it poses a meaningful security question. That is evidence the criterion is
not reliably measurable as posed — not merely that this panel was noisy. It also
bounds what the LLM judge can be validated against: a judge cannot be shown to
agree with a human standard that humans do not share.

Consequently, conclusions in the paper lean on the hallucination flag (the most
reliable criterion, and the one where the judge is substantially trustworthy at
κ=0.640) rather than on architectural coherence, where human-judge agreement is
weak (κ=0.177).
