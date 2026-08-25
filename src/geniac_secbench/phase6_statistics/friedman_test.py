"""
GenIaC-SecBench - Phase 6: Omnibus rank tests across models
============================================================

Answers the core question "do the models differ?" within each complexity
stratum, using a repeated-measures design (every model sees the same scenarios).

WHAT CHANGED IN THE REMEDIATION (and why) -- read before editing
-----------------------------------------------------------------

The pre-remediation version pivoted scenarios x models and called
`pivot.dropna()` before `scipy.stats.friedmanchisquare`. Friedman requires
COMPLETE blocks, so listwise deletion is the only way to feed it -- but the
consequences here were severe and undisclosed:

1. **The simple stratum collapsed to N=8 of 60 scenarios.** One model
   (claude-sonnet-4-6) had zero simple-stratum generations and another had 8
   of 60, so requiring every model to be present dropped 87% of the blocks.
   A "significant" result on N=8 was reported alongside one on N=40 without
   noting they rest on different amounts of evidence.

2. **The two strata silently compared DIFFERENT MODEL SETS.** dropna() removes
   whole scenarios, but which models survive depends on coverage, which
   differed by stratum. Kendall's W was then compared across strata
   (0.640 simple vs 0.440 complex) and read as "model spread widens on
   complexity" -- a comparison that is not licensed when k differs, because W
   is a function of k.

The fix is to use the **Skillings-Mack** statistic, which is the correct
generalization of Friedman to incomplete block designs: it ranks within each
block over only the treatments PRESENT in that block, then standardizes by
block size. With complete data it reduces to Friedman. We report it as the
primary omnibus test, and still report complete-case Friedman alongside so the
two are comparable and the effect of missingness is visible rather than hidden.

We also enforce a single, explicit model set across both strata, so any
cross-stratum comparison of W is like-for-like.

Metric note: the pre-remediation run used `checkov_vulns_norm` -- a
SINGLE-scanner metric -- while the paper argues at length that single-scanner
results are biased (Finding 5). Now that all three scanners have full coverage,
the default metric is total vulnerability density across all three. The old
metric remains selectable via --metric for comparability with archived results.

Usage:
    python -m geniac_secbench.phase6_statistics.friedman_test
    python -m geniac_secbench.phase6_statistics.friedman_test --metric checkov_vulns_norm
"""

import sys
import json
import logging
import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

SCANNER_COLS = ["checkov_vulns", "trivy_vulns", "kics_vulns"]


def safe(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def holm_bonferroni(p_values):
    """Holm step-down adjusted p-values, order preserved."""
    m = len(p_values)
    if m == 0:
        return []
    order = np.argsort(p_values)
    adj = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p_values[idx]
        running = max(running, val)          # enforce monotonicity
        adj[idx] = min(1.0, running)
    return adj.tolist()


def skillings_mack(pivot: pd.DataFrame) -> dict:
    """Skillings-Mack test for incomplete block designs.

    pivot: rows = blocks (scenarios), cols = treatments (models), NaN = missing.

    Within each block, rank only the treatments present, then form
        A_j = sum_i sqrt(12 / (k_i + 1)) * (r_ij - (k_i + 1) / 2)
    where k_i is the number of treatments present in block i. Under H0,
    A ~ MVN(0, Sigma) with
        Sigma_jj = sum_i over blocks containing j of (k_i - 1)
        Sigma_jl = - (number of blocks containing both j and l)
    The statistic A' Sigma^- A is chi-square with df = rank(Sigma) (= k-1 when
    the design is connected). Reduces to Friedman for complete blocks.
    """
    models = list(pivot.columns)
    k = len(models)
    A = np.zeros(k)
    Sigma = np.zeros((k, k))
    blocks_used = 0

    for _, row in pivot.iterrows():
        present = [j for j, m in enumerate(models) if pd.notna(row[m])]
        k_i = len(present)
        if k_i < 2:
            continue                      # a block with <2 treatments carries no information
        blocks_used += 1
        vals = np.array([row[models[j]] for j in present], dtype=float)
        ranks = stats.rankdata(vals)      # average ranks handle ties
        c = np.sqrt(12.0 / (k_i + 1))
        for pos, j in enumerate(present):
            A[j] += c * (ranks[pos] - (k_i + 1) / 2.0)
        for pos, j in enumerate(present):
            Sigma[j, j] += (k_i - 1)
            for j2 in present:
                if j2 != j:
                    Sigma[j, j2] -= 1

    if blocks_used == 0:
        return {"error": "no usable blocks"}

    Sigma_pinv = np.linalg.pinv(Sigma)
    stat = float(A @ Sigma_pinv @ A)
    df = int(np.linalg.matrix_rank(Sigma))
    p = float(stats.chi2.sf(stat, df)) if df > 0 else None

    return {
        "test": "Skillings-Mack",
        "statistic": safe(stat),
        "df": df,
        "p_value": safe(p),
        "n_blocks_used": blocks_used,
        "n_treatments": k,
        "models": models,
        "note": ("Generalization of Friedman to incomplete blocks; uses every "
                 "scenario in which at least two models are present, rather than "
                 "discarding any scenario with a missing model."),
    }


def complete_case_friedman(pivot: pd.DataFrame) -> dict:
    """Classical Friedman on complete blocks only, reported for comparison so
    the cost of listwise deletion is explicit rather than invisible."""
    clean = pivot.dropna()
    N, k = len(clean), len(clean.columns)
    if N < 2 or k < 3:
        return {"test": "Friedman (complete cases)", "error": "insufficient complete blocks",
                "n_blocks": N, "n_treatments": k,
                "blocks_discarded": int(len(pivot) - N)}
    stat, p = stats.friedmanchisquare(*[clean[m].values for m in clean.columns])
    W = stat / (N * (k - 1)) if N and k > 1 else None
    return {
        "test": "Friedman (complete cases)",
        "statistic": safe(stat),
        "p_value": safe(p),
        "kendalls_w": safe(W),
        "n_blocks": N,
        "n_treatments": k,
        "blocks_discarded": int(len(pivot) - N),
        "pct_blocks_discarded": safe(100.0 * (len(pivot) - N) / max(len(pivot), 1)),
        "models": list(clean.columns),
    }


def posthoc_pairwise(pivot: pd.DataFrame) -> list:
    """Pairwise Wilcoxon signed-rank on the scenarios where BOTH models are
    present (pairwise deletion), with Holm-Bonferroni correction."""
    models = list(pivot.columns)
    rows, pvals = [], []
    for m1, m2 in itertools.combinations(models, 2):
        sub = pivot[[m1, m2]].dropna()
        n = len(sub)
        if n < 3:
            rows.append({"model_a": m1, "model_b": m2, "n_pairs": n,
                         "p_value": None, "note": "too few paired observations"})
            pvals.append(1.0)
            continue
        d = sub[m1] - sub[m2]
        if np.all(d == 0):
            rows.append({"model_a": m1, "model_b": m2, "n_pairs": n,
                         "p_value": 1.0, "note": "all differences zero"})
            pvals.append(1.0)
            continue
        try:
            stat, p = stats.wilcoxon(sub[m1], sub[m2])
            rows.append({"model_a": m1, "model_b": m2, "n_pairs": n,
                         "statistic": safe(stat), "p_value": safe(p),
                         "median_diff": safe(float(np.median(d)))})
            pvals.append(p if p is not None and not np.isnan(p) else 1.0)
        except Exception as e:  # noqa: BLE001
            rows.append({"model_a": m1, "model_b": m2, "n_pairs": n,
                         "p_value": None, "note": f"wilcoxon failed: {e}"})
            pvals.append(1.0)

    for row, adj in zip(rows, holm_bonferroni(pvals)):
        row["p_adjusted_holm"] = safe(adj)
        row["significant_005"] = bool(adj is not None and adj < 0.05)
    return rows


def build_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    df = df.copy()
    if metric == "total_vulns_norm":
        total = df[SCANNER_COLS].fillna(0).sum(axis=1)
        rc = pd.to_numeric(df["resource_count"], errors="coerce")
        df[metric] = total / rc.where(rc > 0)
    elif metric not in df.columns:
        raise KeyError(f"metric {metric!r} not in master_results.csv")
    return df


def run_stratum(df: pd.DataFrame, metric: str, stratum: str, models: list) -> dict:
    sub = df[(df["complexity"] == stratum) & (df["model"].isin(models))]
    pivot = sub.pivot_table(index="scenario_id", columns="model", values=metric, aggfunc="mean")
    pivot = pivot.reindex(columns=models)   # fixed model set, same in both strata

    sm = skillings_mack(pivot)
    fr = complete_case_friedman(pivot)
    logger.info("[%s] Skillings-Mack chi2=%s df=%s p=%s over %s blocks | "
                "complete-case Friedman N=%s (discarded %s)",
                stratum, sm.get("statistic"), sm.get("df"), sm.get("p_value"),
                sm.get("n_blocks_used"), fr.get("n_blocks"), fr.get("blocks_discarded"))

    return {
        "stratum": stratum,
        "metric": metric,
        "model_set": models,
        "n_scenarios_in_stratum": int(pivot.shape[0]),
        "coverage_per_model": {m: int(pivot[m].notna().sum()) for m in models},
        "primary_omnibus": sm,
        "secondary_omnibus": fr,
        "post_hoc": posthoc_pairwise(pivot),
    }


def reasoning_contrasts(df: pd.DataFrame, metric: str) -> dict:
    """Paired within-model contrasts: standard vs CoT vs vendor reasoning mode.

    These are the design's cleanest comparisons -- same model, same scenarios,
    one variable toggled -- so they are reported separately from the cross-model
    omnibus. See docs/THREATS_TO_VALIDITY.md on why the Anthropic arms are split
    into -cot (prompt-engineered) and -thinking (real extended thinking).
    """
    pairs = [
        ("claude-opus-4-6", "claude-opus-4-6-thinking", "standard vs extended-thinking"),
        ("claude-opus-4-6", "claude-opus-4-6-cot", "standard vs prompt-CoT"),
        ("claude-opus-4-6-cot", "claude-opus-4-6-thinking", "prompt-CoT vs extended-thinking"),
        ("gpt-5", "gpt-5-thinking", "standard vs reasoning_effort=high"),
    ]
    out = {}
    for a, b, label in pairs:
        res = {}
        for stratum in ["simple", "complex"]:
            sub = df[(df["complexity"] == stratum) & (df["model"].isin([a, b]))]
            piv = sub.pivot_table(index="scenario_id", columns="model", values=metric, aggfunc="mean")
            if a not in piv.columns or b not in piv.columns:
                res[stratum] = {"error": "arm missing", "n_pairs": 0}
                continue
            paired = piv[[a, b]].dropna()
            n = len(paired)
            entry = {"n_pairs": n,
                     "mean_a": safe(paired[a].mean()) if n else None,
                     "mean_b": safe(paired[b].mean()) if n else None}
            if n >= 3 and not np.all(paired[a].values == paired[b].values):
                try:
                    st, p = stats.wilcoxon(paired[a], paired[b])
                    entry.update({"statistic": safe(st), "p_value": safe(p)})
                    if entry["mean_a"]:
                        entry["pct_change"] = safe(100.0 * (entry["mean_b"] - entry["mean_a"]) / entry["mean_a"])
                except Exception as e:  # noqa: BLE001
                    entry["error"] = str(e)
            else:
                entry["note"] = "insufficient or identical paired data"
            res[stratum] = entry
        out[f"{a}__vs__{b}"] = {"label": label, "strata": res}
    return out


def main():
    ap = argparse.ArgumentParser(description="Omnibus rank tests across models.")
    ap.add_argument("--metric", default="total_vulns_norm",
                    help="Outcome column. Default total_vulns_norm (all three scanners, "
                         "per resource). Use checkov_vulns_norm to reproduce archived v1.")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else PATHS.summary_reports
    df = pd.read_csv(data_dir / "master_results.csv")
    df = build_metric(df, args.metric)

    # A single explicit model set for BOTH strata, so Kendall's W and the
    # omnibus statistics are comparable across strata (k must not vary).
    per = df.groupby(["model", "complexity"]).size().unstack(fill_value=0)
    strata = [c for c in per.columns]
    models = sorted(per[(per[strata] > 0).all(axis=1)].index.tolist())
    excluded = sorted(set(per.index) - set(models))
    if excluded:
        logger.warning("Excluded from cross-stratum tests (absent in >=1 stratum): %s", excluded)
    logger.info("Model set (k=%d): %s", len(models), models)

    results = {
        "_schema": "geniac-secbench/omnibus/v2",
        "metric": args.metric,
        "model_set": models,
        "models_excluded_for_incomplete_strata": excluded,
        "primary_test": "Skillings-Mack (handles incomplete blocks)",
        "strata": {},
        "reasoning_contrasts": reasoning_contrasts(df, args.metric),
    }
    for stratum in ["simple", "complex"]:
        results["strata"][stratum] = run_stratum(df, args.metric, stratum, models)

    out_path = data_dir / "statistical_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Wrote %s", out_path)


if __name__ == "__main__":
    main()
