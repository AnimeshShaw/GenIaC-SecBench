"""
GenIaC-SecBench - Figure: density by prompt class, under two classifications.

Accompanies Section IV-A. The point of the figure is the *disagreement*: the
functional-only stratum -- the only one that could isolate unprompted default
posture -- is placed on opposite sides of the insecure class by two independent
classification schemes. Showing both side by side makes that instability legible
in a way a single set of bars would hide.

Usage:
    python -m geniac_secbench.phase8_reporting.visualize_prompt_class
"""

import sys
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

BINS = [0, 1, 2, 5, 10, 20, 10 ** 6]
LAB = ["1", "2", "3-5", "6-10", "11-20", "20+"]
CLASSES = ["insecure_prescriptive", "secure_prescriptive", "functional_only"]
PRETTY = {
    "insecure_prescriptive": "insecure-\nprescriptive",
    "secure_prescriptive": "secure-\nprescriptive",
    "functional_only": "functional-\nonly",
}
AUDIT_MAP = {
    "EXPLICIT_INSECURE_SECURITY_REQUIREMENT": "insecure_prescriptive",
    "EXPLICIT_SECURE_SECURITY_REQUIREMENT": "secure_prescriptive",
    "FUNCTIONAL_OR_TOPOLOGY_ONLY_CONSERVATIVE": "functional_only",
}


def pooled_ratio(df, human):
    """Size-matched ratio pooled across configurations."""
    num = den = n = 0
    for b in LAB:
        hb = human[human.bin == b].density.dropna()
        gb = df[df.bin == b].dens.dropna()
        if len(hb) < 5 or len(gb) < 3:
            continue
        num += gb.mean() * len(gb)
        den += hb.mean() * len(gb)
        n += len(gb)
    return (num / den if n else float("nan")), n


def main():
    sr = PATHS.summary_reports
    h = pd.read_csv(sr / "human_baseline_density.csv", encoding="utf-8-sig")
    h = h[h.resource_count > 0].copy()
    h["bin"] = pd.cut(h.resource_count, BINS, labels=LAB)

    m = pd.read_csv(sr / "master_results.csv", encoding="utf-8-sig")
    m["total"] = m[["checkov_vulns", "trivy_vulns", "kics_vulns"]].fillna(0).sum(axis=1)
    rc = pd.to_numeric(m.resource_count, errors="coerce")
    m["dens"] = m.total / rc.where(rc > 0)
    m = m.dropna(subset=["dens"]).copy()
    m["bin"] = pd.cut(m.resource_count, BINS, labels=LAB)

    ours = pd.read_csv(sr / "prompt_classification.csv", encoding="utf-8-sig")
    schemes = {"This work": dict(zip(ours.scenario_id, ours.prompt_class))}

    audit_path = sr / "prompt_classification_audit.csv"
    if audit_path.exists():
        with open(audit_path, encoding="utf-8-sig") as fh:
            schemes["Independent audit"] = {
                r["id"]: AUDIT_MAP.get(r["classification"], "functional_only")
                for r in csv.DictReader(fh)
            }

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    width = 0.36
    colors = {"This work": "#3b6ea5", "Independent audit": "#c2703d"}

    for i, (name, mapping) in enumerate(schemes.items()):
        d = m.copy()
        d["cls"] = d.scenario_id.map(mapping)
        vals, labels = [], []
        for c in CLASSES:
            r, n = pooled_ratio(d[d.cls == c], h)
            vals.append(r)
            labels.append(f"n={n}")
        xs = [x + (i - (len(schemes) - 1) / 2) * width for x in range(len(CLASSES))]
        bars = ax.bar(xs, vals, width, label=name, color=colors.get(name, "#777"),
                      edgecolor="black", linewidth=0.5)
        for b, v, lb in zip(bars, vals, labels):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}x",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")
            ax.text(b.get_x() + b.get_width() / 2, 0.12, lb,
                    ha="center", va="bottom", fontsize=7, color="white")

    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.text(len(CLASSES) - 0.45, 1.07, "human baseline", fontsize=8, style="italic")

    ax.set_xticks(range(len(CLASSES)))
    ax.set_xticklabels([PRETTY[c] for c in CLASSES], fontsize=9)
    ax.set_ylabel("Density relative to human\n(size-matched, pooled)", fontsize=9)
    ax.set_title("Vulnerability density by prompt class, under two independent "
                 "classifications", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, max(4.6, ax.get_ylim()[1]))
    fig.tight_layout()

    for out in (PATHS.data / "figures", PATHS.root / "paper" / "figures"):
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / "prompt_class_density.png", dpi=300)
    print("Wrote prompt_class_density.png")


if __name__ == "__main__":
    main()
