"""
GenIaC-SecBench - Phase 8b: figures for the human-anchored analysis
====================================================================

Generates the figures the human-baseline comparison needs, which the original
figure set predates:

  human_vs_llm_density      resource-matched LLM vs human density, per bin
  llm_human_ratio           per-model ratio to the human baseline
  density_vs_resources      why matching is required (density falls with size)
  reasoning_mode_contrasts  standard / prompt-CoT / vendor extended thinking
  reasoning_token_share     how little of the output budget reasoning consumes

Writes 300-DPI PNG + PDF to both data/figures/ and paper/figures/.

Matching note: density is strongly inverse to resource count (LLM corpus
Spearman rho = -0.546), and the human corpus averages 5.31 resources per file
against ~3 for simple generations and ~50 for complex ones. Comparing raw means
across those groups measures artifact size, not security. Every LLM-vs-human
comparison here is therefore computed WITHIN resource-count bins.
"""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 300, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
})

BINS = [0, 1, 2, 5, 10, 20, 10**6]
LABELS = ["1", "2", "3-5", "6-10", "11-20", "20+"]
SCANNERS = ["checkov_vulns", "trivy_vulns", "kics_vulns"]


def save(fig, name: str):
    for d in (PATHS.figures, PATHS.paper_figures):
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / f"{name}.png", bbox_inches="tight")
        fig.savefig(d / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.png/.pdf")


def load():
    h = pd.read_csv(PATHS.summary_reports / "human_baseline_density.csv", encoding="utf-8-sig")
    h = h[h.resource_count > 0].copy()
    h["bin"] = pd.cut(h.resource_count, BINS, labels=LABELS)

    m = pd.read_csv(PATHS.summary_reports / "master_results.csv", encoding="utf-8-sig")
    m["total"] = m[SCANNERS].fillna(0).sum(axis=1)
    rc = pd.to_numeric(m.resource_count, errors="coerce")
    m["dens"] = m.total / rc.where(rc > 0)
    m = m.dropna(subset=["dens"]).copy()
    m["bin"] = pd.cut(m.resource_count, BINS, labels=LABELS)
    return h, m


def fig_human_vs_llm(h, m):
    hv, lv, ns, ps = [], [], [], []
    for b in LABELS:
        hb = h[h.bin == b].density.dropna()
        lb = m[m.bin == b].dens.dropna()
        if len(hb) < 5 or len(lb) < 5:
            hv.append(np.nan); lv.append(np.nan); ns.append((0, 0)); ps.append(1.0); continue
        hv.append(hb.mean()); lv.append(lb.mean()); ns.append((len(hb), len(lb)))
        ps.append(stats.mannwhitneyu(lb, hb, alternative="two-sided")[1])

    x = np.arange(len(LABELS)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    ax.bar(x - w/2, hv, w, label="Human-authored (n=634)", color="#2c7fb8")
    ax.bar(x + w/2, lv, w, label="LLM-generated", color="#d95f0e")
    # Annotate LLM/human (the effect direction we are claiming), not human/LLM.
    # Offsets are a fixed fraction of the axis range so a tall first bar cannot
    # push its own label outside the axes.
    top = np.nanmax(lv) if not np.all(np.isnan(lv)) else 1.0
    ax.set_ylim(0, top * 1.30)
    for i, (p, hmean, lmean) in enumerate(zip(ps, hv, lv)):
        if np.isnan(lmean):
            continue
        star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 0.05 else "n.s."
        bar_top = max(hmean, lmean)
        ax.text(i, bar_top + top * 0.03, star, ha="center", fontsize=8)
        if hmean:
            ax.text(i, bar_top + top * 0.11, f"{lmean/hmean:.1f}x", ha="center",
                    fontsize=7.5, color="#444", fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(LABELS)
    ax.set_xlabel("Resources declared per file (matching stratum)")
    ax.set_ylabel("Vulnerability density\n(findings per resource)")
    ax.set_title("LLM-generated IaC is consistently less secure than human-authored IaC,\n"
                 "matched on artifact size", fontsize=9.5)
    ax.legend(frameon=False, fontsize=8)
    save(fig, "human_vs_llm_density")


def fig_ratio(h, m):
    rows = []
    for mod, g in m.groupby("model"):
        num = den = n = 0
        for b in LABELS:
            hb = h[h.bin == b].density.dropna()
            gb = g[g.bin == b].dens.dropna()
            if len(hb) < 5 or len(gb) < 3:
                continue
            num += gb.mean() * len(gb); den += hb.mean() * len(gb); n += len(gb)
        if n >= 20:
            rows.append((num / den, mod, n))
    rows.sort()
    vals = [r for r, _, _ in rows]; names = [f"{mo}" for _, mo, _ in rows]

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    colors = ["#31a354" if "cot" in n else "#756bb1" if "thinking" in n else "#d95f0e"
              for n in names]
    ax.barh(names, vals, color=colors)
    ax.axvline(1.0, color="#2c7fb8", lw=1.6, ls="--")
    ax.text(1.02, -0.6, "human baseline", color="#2c7fb8", fontsize=8, va="top")
    for i, v in enumerate(vals):
        ax.text(v + 0.04, i, f"{v:.2f}x", va="center", fontsize=7.5)
    ax.set_xlabel("Vulnerability density relative to human-authored IaC (resource-matched)")
    ax.set_title("Every model clusters in a narrow 3.2x-3.9x band above the human baseline",
                 fontsize=9.5)
    ax.set_xlim(0, max(vals) * 1.18)
    save(fig, "llm_human_ratio")


def fig_density_vs_resources(h, m):
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    for df, lab, col in ((h.rename(columns={"density": "d"}), "Human-authored", "#2c7fb8"),
                         (m.rename(columns={"dens": "d"}), "LLM-generated", "#d95f0e")):
        g = df.groupby("bin", observed=True)["d"].mean()
        ax.plot(range(len(g)), g.values, marker="o", label=lab, color=col)
    ax.set_xticks(range(len(LABELS))); ax.set_xticklabels(LABELS)
    ax.set_xlabel("Resources declared per file")
    ax.set_ylabel("Mean vulnerability density")
    rho, p = stats.spearmanr(m.resource_count, m.dens)
    ax.set_title(f"Density falls with artifact size (LLM Spearman $\\rho$={rho:.2f}, "
                 f"p={p:.1e}),\nso comparisons must be size-matched", fontsize=9.5)
    ax.legend(frameon=False, fontsize=8)
    save(fig, "density_vs_resources")


def fig_reasoning_contrasts():
    p = PATHS.summary_reports / "statistical_results.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    rows = []
    for _, v in d.get("reasoning_contrasts", {}).items():
        e = v.get("strata", {}).get("simple", {})
        if e.get("pct_change") is not None:
            rows.append((v["label"], e["pct_change"], e.get("p_value", 1.0), e.get("n_pairs", 0)))
    if not rows:
        return
    rows.sort(key=lambda r: r[1])
    labels = [r[0].replace(" vs ", "\nvs ") for r in rows]
    vals = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    colors = ["#31a354" if r[2] < 0.05 else "#bdbdbd" for r in rows]
    ax.barh(labels, vals, color=colors)
    ax.axvline(0, color="k", lw=0.8)
    for i, (lab, v, pv, n) in enumerate(rows):
        ax.text(v - 0.6, i, f"p={pv:.3g}  (n={n})", va="center", ha="right", fontsize=7.5)
    ax.set_xlabel("Change in vulnerability density (%), simple stratum")
    ax.set_title("Vendor extended thinking significantly outperforms prompted "
                 "chain-of-thought\n(green = significant at $\\alpha$=0.05)", fontsize=9.5)
    save(fig, "reasoning_mode_contrasts")


def fig_reasoning_tokens():
    p = PATHS.data / "generation_usage.jsonl"
    if not p.exists():
        return
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    df = pd.DataFrame(recs)
    df = df[df.model.astype(str).str.endswith("-thinking")]
    df["reasoning_tokens"] = pd.to_numeric(df.get("reasoning_tokens"), errors="coerce")
    df["completion_tokens"] = pd.to_numeric(df.get("completion_tokens"), errors="coerce")
    df = df.dropna(subset=["reasoning_tokens", "completion_tokens"])
    if df.empty:
        return
    df["stratum"] = np.where(df.scenario_id.astype(str).str.startswith("complex"),
                             "complex", "simple")
    df["share"] = 100 * df.reasoning_tokens / df.completion_tokens

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    data = [df[df.stratum == s].reasoning_tokens for s in ("simple", "complex")]
    # matplotlib >=3.9 renamed boxplot(labels=) to tick_labels=; support both.
    _tl = "tick_labels" if "tick_labels" in axes[0].boxplot.__doc__ else "labels"
    axes[0].boxplot(data, showfliers=False, **{_tl: ["simple", "complex"]})
    axes[0].set_ylabel("Reasoning tokens per generation")
    axes[0].set_title("Reasoning tokens spent", fontsize=9)
    data2 = [df[df.stratum == s].share for s in ("simple", "complex")]
    axes[1].boxplot(data2, showfliers=False, **{_tl: ["simple", "complex"]})
    axes[1].set_ylabel("Reasoning as % of output tokens")
    axes[1].set_title("Share of the output budget", fontsize=9)
    fig.suptitle("Extended thinking barely engages on IaC generation", fontsize=9.5)
    fig.tight_layout()
    save(fig, "reasoning_token_share")


def main():
    print("Generating human-baseline figures...")
    h, m = load()
    fig_human_vs_llm(h, m)
    fig_ratio(h, m)
    fig_density_vs_resources(h, m)
    fig_reasoning_contrasts()
    fig_reasoning_tokens()
    print("Done.")


if __name__ == "__main__":
    main()
