"""
GenIaC-SecBench - Final Report Visualizations (Phase 8)
==========================================================
Generates the publication-ready figures referenced throughout docs/findings/
and paper/. This script was missing from the repository entirely prior to
the Aug 2026 remediation -- the figures in data/figures/ existed as
pre-rendered output with no source code to reproduce them. Restored here
from the CSV schemas the figures were evidently built from (see the git
history / docs/_archive_v1 for what the original renders looked like).

Reads exclusively from data/summary_reports/*.csv (the canonical output of
Phase 3/6) and writes PNG (300 DPI) + PDF to data/figures/ and paper/figures/.

Usage:
    python -m geniac_secbench.phase8_reporting.visualize_final
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

sns.set_theme(style="whitegrid", context="paper")
PALETTE = sns.color_palette("colorblind")

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN"]
SEVERITY_COLORS = {
    "CRITICAL": "#8B0000", "HIGH": "#D62728", "MEDIUM": "#FF8C00",
    "LOW": "#FFD700", "INFO": "#87CEEB", "UNKNOWN": "#A9A9A9",
}


def save(fig, name: str):
    for out_dir in (PATHS.figures, PATHS.paper_figures):
        out_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_dir / f"{name}.png", dpi=300, bbox_inches="tight")
        fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {name}.png / .pdf -> {PATHS.figures} and {PATHS.paper_figures}")


def plot_cis_category_heatmap(df: pd.DataFrame):
    pivot = df.pivot_table(index="model", columns="cis_category", values="count", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="Reds", ax=ax, cbar_kws={"label": "Finding count"})
    ax.set_title("Vulnerability Findings by CIS Category and Model")
    ax.set_xlabel("CIS Benchmark Category")
    ax.set_ylabel("Model")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    save(fig, "cis_category_heatmap")


def plot_scanner_agreement(df: pd.DataFrame):
    pivot = df.pivot_table(index="model", columns="scanner", values="fail_count", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(11, 6))
    pivot.plot(kind="bar", ax=ax, color=PALETTE[: len(pivot.columns)])
    ax.set_title("Findings per Scanner by Model (Checkov vs. Trivy vs. KICS)")
    ax.set_xlabel("Model")
    ax.set_ylabel("Finding count")
    ax.legend(title="Scanner")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    save(fig, "scanner_agreement")


def plot_severity_distribution(df: pd.DataFrame):
    pivot = df.pivot_table(index="model", columns="severity", values="count", aggfunc="sum", fill_value=0)
    present = [s for s in SEVERITY_ORDER if s in pivot.columns]
    pivot = pivot[present]
    fig, ax = plt.subplots(figsize=(11, 6))
    pivot.plot(kind="bar", stacked=True, ax=ax, color=[SEVERITY_COLORS[s] for s in present])
    ax.set_title("Severity Distribution of Findings by Model")
    ax.set_xlabel("Model")
    ax.set_ylabel("Finding count")
    ax.legend(title="Severity", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    save(fig, "severity_distribution")


def plot_schema_validity_pass_rate(master: pd.DataFrame):
    pass_rate = master.groupby("model")["terraform_valid"].mean().sort_values(ascending=False) * 100
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(pass_rate.index, pass_rate.values, color=PALETTE[0])
    ax.set_title("Schema Validity Pass Rate by Model")
    ax.set_xlabel("Model")
    ax.set_ylabel("Pass rate (%)")
    ax.set_ylim(0, 100)
    ax.bar_label(bars, fmt="%.1f%%", padding=2)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    save(fig, "schema_validity_pass_rate")


def plot_vuln_density_boxplot(master: pd.DataFrame):
    m = master.copy()
    m["total_vulns_norm"] = m[["checkov_vulns_norm", "trivy_vulns_norm", "kics_vulns_norm"]].sum(axis=1)
    order = m.groupby("model")["total_vulns_norm"].median().sort_values().index
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.boxplot(data=m, x="model", y="total_vulns_norm", order=order, ax=ax, palette="colorblind", hue="model", legend=False)
    ax.set_title("Vulnerability Density (Findings per Resource) by Model")
    ax.set_xlabel("Model")
    ax.set_ylabel("Vulns / resource (all scanners summed)")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    save(fig, "vuln_density_boxplot")


def main():
    sr = PATHS.summary_reports

    cis = pd.read_csv(sr / "summary_cis_category.csv")
    plot_cis_category_heatmap(cis)

    scanner = pd.read_csv(sr / "summary_model_scanner.csv")
    plot_scanner_agreement(scanner)

    severity = pd.read_csv(sr / "summary_severity.csv")
    plot_severity_distribution(severity)

    master = pd.read_csv(sr / "master_results.csv")
    plot_schema_validity_pass_rate(master)
    plot_vuln_density_boxplot(master)

    print("\nAll figures regenerated from data/summary_reports/*.csv.")


if __name__ == "__main__":
    main()
