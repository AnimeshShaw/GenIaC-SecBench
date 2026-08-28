"""
GenIaC-SecBench - Phase 7: inter-rater and human-vs-judge agreement
====================================================================

Computes, prints, and **persists** every agreement statistic:

  * Fleiss' kappa across the three human reviewers (per criterion)
  * A human consensus score per scenario, with an explicit tie rule
  * Agreement between that consensus and the independent LLM judge (Grok 4.6):
    exact agreement, within-1 agreement, Cohen's kappa (binary) and
    quadratic-weighted kappa (ordinal)

Supersedes the print-only `fleiss_kappa.py` and `human_vs_grok.py`.

Two defects in those scripts are fixed here:

1. **Nothing was persisted.** Both wrote results to stdout only. The paper's
   agreement figures were read from `human_agreement_metrics.json`, a file no
   pipeline step regenerated -- so re-running Phase 7 could not update it, and it
   silently aged out of sync with the data it claimed to summarize.

2. **The consensus rule was implicit and biased.** Consensus used
   `ratings.mode(axis=1)[0]`, and pandas returns modes in SORTED order. When all
   three reviewers disagreed (e.g. 2/4/5) there is no mode, every value ties, and
   `[0]` silently selected the LOWEST -- systematically biasing consensus
   downward exactly on the scenarios where reviewers disagreed most. Ties are now
   resolved by the MEDIAN, which is the defensible summary for ordinal data, and
   the number of tie-broken scenarios is reported rather than hidden.

Note on n: kappa requires complete blocks, so all statistics are computed over
the scenarios scored by ALL reviewers (the intersection), not the union.

Usage:
    python -m geniac_secbench.phase7_human_review.agreement_metrics
"""

import os
import sys
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.inter_rater import fleiss_kappa
from sklearn.metrics import accuracy_score, cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ORDINAL = {
    "architectural_coherence": ("human_architectural_coherence", [1, 2, 3, 4, 5]),
    "real_world_plausibility": ("human_real_world_plausibility", [1, 2, 3, 4, 5]),
    "security_test_relevance": ("human_security_test_relevance", [1, 2, 3, 4, 5]),
}
BINARY = {"hallucination_flag": ("human_hallucination_flag", ["Y", "N"])}


def _safe(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(f) or np.isinf(f)) else f


def load_raters():
    d = PATHS.human_reviews
    # Only per-rater files. The directory also holds review_template_blank.csv
    # and grok_judge_answer_key.csv, which are not rater data.
    files = sorted(f for f in os.listdir(d)
                   if f.startswith("human_review_") and f.endswith(".csv"))
    dfs = [pd.read_csv(d / f, encoding="utf-8-sig") for f in files]
    if not dfs:
        raise FileNotFoundError(f"no human_review_*.csv in {d}")

    common = set(dfs[0]["scenario_id"])
    for df in dfs[1:]:
        common &= set(df["scenario_id"])
    common = sorted(common)

    dfs = [df[df["scenario_id"].isin(common)]
             .sort_values("scenario_id").reset_index(drop=True) for df in dfs]
    return files, dfs, common


def compute_fleiss(dfs, col, categories):
    n = len(dfs[0])
    table = np.zeros((n, len(categories)))
    for i in range(n):
        ratings = [str(df.loc[i, col]) for df in dfs]
        for j, cat in enumerate(categories):
            table[i, j] = ratings.count(str(cat))
    return float(fleiss_kappa(table))


def consensus_ordinal(dfs, col):
    """Majority value per scenario; ties broken by the median.

    `mode()[0]` returns the smallest modal value, which on a full 3-way
    disagreement means "always take the lowest score". Median is the correct
    ordinal summary and is symmetric.
    """
    ratings = pd.concat([pd.to_numeric(df[col], errors="coerce") for df in dfs], axis=1)
    out, n_ties = [], 0
    for _, row in ratings.iterrows():
        vals = row.dropna().tolist()
        if not vals:
            out.append(np.nan)
            continue
        counts = pd.Series(vals).value_counts()
        if (counts == counts.max()).sum() > 1:      # no unique majority
            n_ties += 1
            out.append(float(np.median(vals)))
        else:
            out.append(float(counts.idxmax()))
    return pd.Series(out), n_ties


def consensus_binary(dfs, col):
    ratings = pd.concat([df[col].astype(str).str.strip().str.upper() for df in dfs], axis=1)
    out, n_ties = [], 0
    for _, row in ratings.iterrows():
        vals = [v for v in row.tolist() if v in ("Y", "N")]
        if not vals:
            out.append(None)
            continue
        counts = pd.Series(vals).value_counts()
        if (counts == counts.max()).sum() > 1:
            n_ties += 1
            # Tie on a safety flag resolves to the CONSERVATIVE answer: if any
            # reviewer suspected a hallucination and the panel split evenly, do
            # not record the scenario as clean.
            out.append("Y")
        else:
            out.append(str(counts.idxmax()))
    return pd.Series(out), n_ties


def main():
    files, dfs, common = load_raters()
    logger.info("Raters: %d (%s)", len(dfs), ", ".join(files))
    logger.info("Scenarios scored by ALL raters: %d", len(common))

    results = {
        "_schema": "geniac-secbench/agreement/v2",
        "n_raters": len(dfs),
        "rater_files": files,
        "n_scenarios_common": len(common),
        "note": ("Kappa requires complete blocks, so all statistics use the "
                 "intersection of scenarios scored by every rater."),
        "fleiss_kappa": {},
        "human_vs_judge": {},
    }

    logger.info("\n=== INTER-RATER AGREEMENT (FLEISS' KAPPA) ===")
    for name, (col, cats) in {**ORDINAL, **BINARY}.items():
        try:
            k = compute_fleiss(dfs, col, cats)
            results["fleiss_kappa"][name] = _safe(k)
            logger.info("  %-28s %.4f", name, k)
        except Exception as e:  # noqa: BLE001
            results["fleiss_kappa"][name] = None
            logger.info("  %-28s ERROR: %s", name, e)

    # ---- consensus + judge comparison ------------------------------------
    key = PATHS.human_reviews / "grok_judge_answer_key.csv"
    if not key.exists():
        logger.warning("\nJudge answer key not found at %s -- skipping judge comparison.", key)
    else:
        cons = dfs[0][["scenario_id"]].copy()
        ties = {}
        for name, (col, _) in ORDINAL.items():
            s, nt = consensus_ordinal(dfs, col)
            cons[name] = s
            ties[name] = nt
        for name, (col, _) in BINARY.items():
            s, nt = consensus_binary(dfs, col)
            cons[name] = s
            ties[name] = nt
        results["consensus_ties_broken"] = ties

        judge = pd.read_csv(key, encoding="utf-8-sig").sort_values("scenario_id").reset_index(drop=True)
        merged = pd.merge(cons, judge, on="scenario_id", suffixes=("_human", "_judge"))
        results["n_scenarios_compared"] = int(len(merged))

        logger.info("\n=== HUMAN CONSENSUS vs LLM JUDGE (n=%d) ===", len(merged))
        for name in list(ORDINAL) + list(BINARY):
            hcol, jcol = f"{name}_human", f"{name}_judge"
            if hcol not in merged.columns or jcol not in merged.columns:
                if name in merged.columns and jcol in merged.columns:
                    hcol = name
                else:
                    logger.info("  %-28s (columns not found)", name)
                    continue
            ordinal = name in ORDINAL
            if ordinal:
                # Compare ordinals NUMERICALLY, not as strings. The consensus is
                # a float (4.0) and the judge key an int (4); string comparison
                # makes every pair unequal and reports 0% exact agreement.
                # With 3 raters the median is always an actual rating value, so
                # rounding to int is lossless here.
                h = pd.to_numeric(merged[hcol], errors="coerce").round().astype("Int64").astype(str)
                a = pd.to_numeric(merged[jcol], errors="coerce").round().astype("Int64").astype(str)
            else:
                h = merged[hcol].astype(str).str.strip().str.upper()
                a = merged[jcol].astype(str).str.strip().str.upper()
            entry = {"exact_agreement": _safe(accuracy_score(h, a))}
            try:
                entry["kappa"] = _safe(cohen_kappa_score(
                    h, a, weights="quadratic" if ordinal else None))
                entry["kappa_type"] = "quadratic_weighted" if ordinal else "cohen"
            except Exception:  # noqa: BLE001
                entry["kappa"] = None
            if ordinal:
                hn = pd.to_numeric(h, errors="coerce")
                an = pd.to_numeric(a, errors="coerce")
                entry["within_one"] = _safe((abs(hn - an) <= 1).mean())
            results["human_vs_judge"][name] = entry
            logger.info("  %-28s exact=%5.1f%%  kappa=%s%s", name,
                        100 * (entry["exact_agreement"] or 0),
                        f"{entry['kappa']:.3f}" if entry["kappa"] is not None else "n/a",
                        f"  within1={100*entry['within_one']:.1f}%" if entry.get("within_one") is not None else "")

        if any(ties.values()):
            logger.info("\n  Ties broken (no unique majority): %s", ties)

    out = PATHS.summary_reports / "human_agreement_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("\nWrote %s", out)


if __name__ == "__main__":
    main()
