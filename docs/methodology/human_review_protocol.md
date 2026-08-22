# Human Review Protocol & Inter-Rater Reliability

Scope: what your two reviewers actually do, in what format, and how you turn their scores into a defensible reliability number.

---

## 1. What's being reviewed

Not vulnerabilities — that's automated (Phase 3). Reviewers assess whether each sampled **scenario** is architecturally realistic, i.e. the thing your "is this hallucinated" objection is actually about. Feed them exactly what `stratified_sampling.py` copied out: the scenario itself (spec/description and, if the scenario includes one, its reference IaC), nothing else — no model outputs, no Checkov results, no complexity label if you want the label itself to be part of what's implicitly checked.

## 2. Reviewer independence

- Both reviewers score every sampled scenario **without seeing each other's scores or discussing them** until both are fully done. This is non-negotiable — it's the condition that makes kappa meaningful. Agreement measured after they've compared notes measures conformity, not reliability.
- If reviewers are also coauthors (as you're planning), the incentive to converge is real — say explicitly, in writing to them, that independent-first scoring is a condition of the co-authorship credit.

## 3. Rubric

Vague "rate realism 1–10" produces unusable, unreproducible numbers. Use fixed, anchored criteria:

| # | Criterion | Question | Scale |
|---|---|---|---|
| 1 | Architectural coherence | Do the resources/components form an internally consistent design a real engineer might produce? | 1 (incoherent) – 5 (fully coherent) |
| 2 | Real-world plausibility | Could this scenario plausibly arise in a production cloud environment, vs. a contrived construct? | 1 (contrived) – 5 (highly plausible) |
| 3 | Security-test relevance | Does the scenario actually create a meaningful security decision point, or is any "vulnerability" trivial/forced? | 1 (trivial) – 5 (meaningful) |
| 4 | Hallucination flag | Does the scenario reference nonexistent services, impossible configurations, or fundamentally broken requirements? | Y / N |

Give reviewers 1–2 anchor examples per criterion (a clear 1 and a clear 5) before they start — without anchors, two careful reviewers will still drift apart on what "3" means.

## 4. Response format

One row per (scenario × reviewer). CSV columns, exact header:

```
scenario_id,complexity,reviewer_id,architectural_coherence,real_world_plausibility,security_relevance,hallucination_flag,notes
```

`hallucination_flag` as `Y`/`N` only. `notes` free text — capture *why* on any score of 1–2, you'll want it for the reconciliation step and for quoting in the paper's limitations/examples section. Two files in, one per reviewer — don't let them share a live spreadsheet while scoring; that's the independence rule again, enforced by tooling instead of trust.

## 5. Process

1. Both reviewers score independently (Section 2–4).
2. Compute Cohen's kappa per criterion (Section 6) on the *independent* scores — this is your reported reliability figure, computed before any reconciliation.
3. Flag disagreements: hallucination-flag mismatches, or any 1–5 criterion differing by ≥2 points.
4. Reconcile flagged items only — short discussion, agree on a final adjudicated score. Document what changed and why (one line each is enough).
5. Report both numbers in the paper: raw inter-rater kappa (reliability), and the final adjudicated scores (what you actually use downstream).

## 6. Cohen's Kappa

**Proves:** whether two raters' agreement is above what chance alone would produce. Plain % agreement is misleading — two reviewers who both mark 90% of scenarios "fine" will agree 81%+ of the time by chance alone even if they're not really looking at the same thing.

**Formula:**
```
κ = (p_o − p_e) / (1 − p_e)
```
p_o = observed proportion of agreement. p_e = expected proportion of agreement by chance, computed from each rater's marginal distribution.

**Worked example** — `hallucination_flag`, 20 reviewed scenarios:

| | Reviewer 2: Y | Reviewer 2: N | Total |
|---|---|---|---|
| **Reviewer 1: Y** | 4 | 1 | 5 |
| **Reviewer 1: N** | 2 | 13 | 15 |
| **Total** | 6 | 14 | 20 |

```
p_o = (4 + 13) / 20 = 0.85

p_e = P(both Y) + P(both N)
    = (5/20 × 6/20) + (15/20 × 14/20)
    = (0.25 × 0.30) + (0.75 × 0.70)
    = 0.075 + 0.525 = 0.60

κ = (0.85 − 0.60) / (1 − 0.60) = 0.25 / 0.40 = 0.625
```

Interpretation (Landis & Koch, 1977): <0 poor · 0.01–0.20 slight · 0.21–0.40 fair · 0.41–0.60 moderate · **0.61–0.80 substantial** · 0.81–1.00 almost perfect. κ = 0.625 → substantial agreement, reportable as solid evidence the hallucination judgment is not noise.

**For the 1–5 ordinal criteria, use weighted kappa, not plain kappa.** Plain kappa treats a 1-vs-5 disagreement the same as a 1-vs-2 — clearly wrong for an ordinal scale. Use quadratic weights, which penalize large gaps more:
```
κ_w = 1 − (Σ w_ij·O_ij) / (Σ w_ij·E_ij)
```
where O is the observed and E the chance-expected confusion matrix, and w_ij = (i−j)² for quadratic weighting.

**Tooling:** `sklearn.metrics.cohen_kappa_score(rater1, rater2)` for plain kappa, `cohen_kappa_score(rater1, rater2, weights="quadratic")` for the ordinal criteria. Don't hand-compute past the toy example above.

## 7. If you later validate the LLM judge against this data

Once both the human scores and the LLM judge scores exist for the same sampled scenarios, compute the same weighted kappa between the LLM judge and the *adjudicated* human score. That number is what tells you whether the judge is worth citing as corroborating evidence or whether it's just noise with extra steps. Don't skip reporting it even if it comes out low — a disclosed weak correlation is far better for your credibility than an undisclosed one.
