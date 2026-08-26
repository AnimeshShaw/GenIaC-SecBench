"""
GenIaC-SecBench - Phase 8: Findings report generator
=====================================================

Reads every result artifact in data/summary_reports/ and emits the full findings
summary as Markdown.

Why this exists: the pre-remediation findings documents were written by hand, and
several of their headline numbers did not match the CSVs they claimed to
summarize (e.g. reported schema pass rates of 15% and 20% for llama3 and mistral
against actual values of 1.0% and 10.0%). Hand-transcribed results drift from
their source the moment anything is re-run. Generating the report FROM the data
makes that class of error impossible, and makes every number in the paper
regenerable with one command.

Usage:
    python -m geniac_secbench.phase8_reporting.findings_report
    python -m geniac_secbench.phase8_reporting.findings_report --out docs/findings/RESULTS.md
"""

import sys
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

SCANNERS = ["checkov_vulns", "trivy_vulns", "kics_vulns"]


def _load(name):
    p = PATHS.summary_reports / name
    if not p.exists():
        return None
    # utf-8-sig, not utf-8: several artifacts in this repo were written by tools
    # that emit a BOM, and json.loads rejects a leading BOM outright. utf-8-sig
    # strips one if present and is a no-op otherwise, so it is always safe here.
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8-sig"))
    return pd.read_csv(p, encoding="utf-8-sig")


def fmt(v, nd=2, dash="--"):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return dash
    if isinstance(v, float):
        if abs(v) < 0.001 and v != 0:
            return f"{v:.2e}"
        return f"{v:.{nd}f}"
    return str(v)


def section_corpus(md, master, coverage):
    md.append("## 1. Corpus and coverage\n")
    n = len(master)
    md.append(f"- **{n:,}** (scenario x model) observations, one per generated file.")
    md.append(f"- **{master['model'].nunique()}** model arms, "
              f"**{master['scenario_id'].nunique()}** distinct scenarios.\n")

    piv = master.groupby(["model", "complexity"]).size().unstack(fill_value=0)
    for c in ("simple", "complex"):
        if c not in piv.columns:
            piv[c] = 0
    piv = piv[["simple", "complex"]]
    piv["total"] = piv.sum(axis=1)
    md.append("| model | simple | complex | total |")
    md.append("|---|---:|---:|---:|")
    for m, r in piv.sort_index().iterrows():
        flag = "" if (r["simple"] == 60 and r["complex"] == 40) else "  *(incomplete)*"
        md.append(f"| `{m}`{flag} | {r['simple']} | {r['complex']} | {r['total']} |")
    md.append("")

    if coverage is not None and len(coverage):
        tot = coverage.groupby("scanner")[["scenarios_total", "scenarios_covered"]].sum()
        md.append("**Scanner coverage**\n")
        md.append("| scanner | covered | total | % |")
        md.append("|---|---:|---:|---:|")
        for s, r in tot.iterrows():
            pct = 100 * r["scenarios_covered"] / max(r["scenarios_total"], 1)
            md.append(f"| {s} | {int(r['scenarios_covered'])} | "
                      f"{int(r['scenarios_total'])} | {pct:.1f}% |")
        md.append("")


def section_density(md, master):
    md.append("## 2. Vulnerability density by model\n")
    md.append("Density = total findings across all three scanners / resource count. "
              "Resource count is the AST-derived value; rows with zero resources "
              "carry no exposure and are excluded from the density mean.\n")
    m = master.copy()
    m["total_vulns"] = m[SCANNERS].fillna(0).sum(axis=1)
    rc = pd.to_numeric(m["resource_count"], errors="coerce")
    m["density"] = m["total_vulns"] / rc.where(rc > 0)

    for stratum in ["simple", "complex"]:
        sub = m[m["complexity"] == stratum]
        if not len(sub):
            continue
        g = sub.groupby("model").agg(
            n=("scenario_id", "size"),
            resources=("resource_count", "mean"),
            findings=("total_vulns", "mean"),
            density=("density", "mean"),
        ).sort_values("density")
        md.append(f"### {stratum} stratum\n")
        md.append("| model | n | mean resources | mean findings | **density** |")
        md.append("|---|---:|---:|---:|---:|")
        for mm, r in g.iterrows():
            md.append(f"| `{mm}` | {int(r['n'])} | {fmt(r['resources'])} | "
                      f"{fmt(r['findings'])} | **{fmt(r['density'])}** |")
        md.append("")


def section_validity(md, master):
    md.append("## 3. Schema validity (deployability)\n")
    v = master.copy()
    v["valid"] = v["terraform_valid"].astype(str).str.lower().isin(["true", "1"])
    g = v.groupby("model")["valid"].agg(["sum", "size"])
    g["pass_rate"] = 100 * g["sum"] / g["size"]
    g = g.sort_values("pass_rate", ascending=False)
    md.append("| model | valid | total | pass rate |")
    md.append("|---|---:|---:|---:|")
    for mm, r in g.iterrows():
        md.append(f"| `{mm}` | {int(r['sum'])} | {int(r['size'])} | {r['pass_rate']:.1f}% |")
    md.append("")


def section_omnibus(md, stats):
    if not stats:
        return
    md.append("## 4. Do the models differ? (omnibus)\n")
    md.append(f"Metric: `{stats.get('metric')}`. Primary test: "
              f"**{stats.get('primary_test')}**.\n")
    md.append("| stratum | Skillings-Mack chi2 | df | p | blocks used | "
              "complete-case Friedman N | blocks discarded |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for s, body in stats.get("strata", {}).items():
        p = body.get("primary_omnibus", {})
        f = body.get("secondary_omnibus", {})
        md.append(f"| {s} | {fmt(p.get('statistic'))} | {p.get('df')} | "
                  f"{fmt(p.get('p_value'))} | {p.get('n_blocks_used')} | "
                  f"{f.get('n_blocks', '--')} | {f.get('blocks_discarded', '--')} |")
    md.append("")
    disc = [b.get("secondary_omnibus", {}).get("n_blocks")
            for b in stats.get("strata", {}).values()]
    if any(d == 0 for d in disc if d is not None):
        md.append("> **Note.** Complete-case Friedman retains **zero** blocks in at least "
                  "one stratum: with this many arms and uneven coverage, no scenario has "
                  "every model present. The classical test is not merely weaker here, it "
                  "is uncomputable -- which is why Skillings-Mack is the primary test.\n")


def section_reasoning(md, stats):
    if not stats or "reasoning_contrasts" not in stats:
        return
    md.append("## 5. Reasoning-mode contrasts\n")
    md.append("Paired within-model comparisons -- same model, same scenarios, one "
              "variable toggled. `-cot` is a prompt-engineered chain-of-thought "
              "suffix; `-thinking` is the vendor's reasoning feature. They are "
              "distinct conditions (see THREATS_TO_VALIDITY.md 1.1).\n")
    md.append("| contrast | stratum | n | mean before | mean after | change | p |")
    md.append("|---|---|---:|---:|---:|---:|---:|")
    for _, v in stats["reasoning_contrasts"].items():
        for s, e in v.get("strata", {}).items():
            if not e.get("n_pairs"):
                continue
            pc = e.get("pct_change")
            pcs = f"{pc:+.1f}%" if pc is not None else "--"
            sig = " **\\***" if (e.get("p_value") is not None and e["p_value"] < 0.05) else ""
            md.append(f"| {v['label']} | {s} | {e['n_pairs']} | {fmt(e.get('mean_a'), 3)} | "
                      f"{fmt(e.get('mean_b'), 3)} | {pcs} | {fmt(e.get('p_value'), 4)}{sig} |")
    md.append("\n`*` significant at alpha=0.05.\n")


def section_glmm(md, glmm):
    if not glmm:
        return
    sp = glmm.get("specification", {})
    od = glmm.get("overdispersion", {})
    md.append("## 6. Negative binomial rate model\n")
    md.append(f"- Reference model: `{sp.get('reference_model')}`")
    md.append(f"- Exposure offset: `{sp.get('offset')}` -- coefficients are rate ratios "
              f"**per resource**")
    md.append(f"- Overdispersion variance/mean = **{fmt(od.get('variance_to_mean_ratio'), 1)}** "
              f"(Poisson requires 1, so NB2 is required)")
    md.append(f"- Rows fitted {sp.get('rows_fitted')} of {sp.get('rows_total')}; "
              f"{sp.get('rows_zero_exposure_excluded')} excluded for zero exposure")
    md.append(f"- Outcome filtering: {sp.get('outcome_filtering')}\n")

    pm = glmm.get("models", {}).get("nb_with_offset", {})
    rows = []
    for k, v in pm.get("coefficients", {}).items():
        if "model_cat" in k and "complexity" not in k and v.get("irr") is not None:
            rows.append((v["irr"], k.split("T.")[-1].rstrip("]"),
                         v.get("ci_lower"), v.get("ci_upper"), v.get("p_value")))
    rows.sort()
    if rows:
        md.append("| model | IRR | 95% CI | p |")
        md.append("|---|---:|---|---:|")
        for irr, name, lo, hi, p in rows:
            ci = f"[{fmt(lo)}, {fmt(hi)}]" if lo is not None else "--"
            sig = " **\\***" if (p is not None and p < 0.05) else ""
            md.append(f"| `{name}` | {fmt(irr)} | {ci} | {fmt(p, 4)}{sig} |")
        md.append("")


def section_human(md):
    hj = _load("human_agreement_metrics.json")
    if not hj:
        return
    md.append("## 7. Human evaluation and LLM-judge agreement\n")
    md.append("```json")
    md.append(json.dumps(hj, indent=2)[:2500])
    md.append("```\n")


def section_ks(md):
    ks = _load("ks_test_human_baseline.csv")
    if ks is None or not len(ks):
        return
    md.append("## 8. Structural divergence from human-authored IaC\n")
    md.append("Two-sample Kolmogorov-Smirnov, each model against the 634-file human "
              "reference corpus.\n")
    md.append("```")
    md.append(ks.to_string(index=False)[:3000])
    md.append("```\n")


def section_usage(md):
    p = PATHS.data / "generation_usage.jsonl"
    if not p.exists():
        return
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not recs:
        return
    df = pd.DataFrame(recs)
    md.append("## 9. Generation cost and reasoning-token usage\n")
    if "reasoning_tokens" in df.columns:
        rt = pd.to_numeric(df["reasoning_tokens"], errors="coerce").dropna()
        if len(rt):
            md.append(f"- Reasoning tokens per generation: median **{rt.median():.0f}**, "
                      f"max **{rt.max():.0f}**, over {len(rt)} logged generations.")
            md.append("- Measured against a 16,000-token budget under the fixed-budget "
                      "configuration: `budget_tokens` is a ceiling the model may "
                      "underspend, not a target. A small reasoning effect on this task "
                      "class must not be read as \"reasoning does not help\" in general.\n")
    if "completion_tokens" in df.columns:
        ct = pd.to_numeric(df["completion_tokens"], errors="coerce").dropna()
        md.append(f"- Completion tokens logged: **{ct.sum():,.0f}** total, "
                  f"median **{ct.median():,.0f}** per generation.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PATHS.root / "docs" / "findings" / "RESULTS.md"))
    args = ap.parse_args()

    master = _load("master_results.csv")
    if master is None:
        print("master_results.csv not found -- run the pipeline first.")
        sys.exit(1)
    coverage = _load("scan_coverage.csv")
    stats = _load("statistical_results.json")
    glmm = _load("nb_glmm_results.json")

    md = ["# GenIaC-SecBench -- Results",
          "",
          "> Generated from `data/summary_reports/` by "
          "`geniac_secbench.phase8_reporting.findings_report`. "
          "Do not hand-edit: regenerate after any pipeline run.",
          ""]

    section_corpus(md, master, coverage)
    section_density(md, master)
    section_validity(md, master)
    section_omnibus(md, stats)
    section_reasoning(md, stats)
    section_glmm(md, glmm)
    section_ks(md)
    section_human(md)
    section_usage(md)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out} ({len(md)} lines)")


if __name__ == "__main__":
    main()
