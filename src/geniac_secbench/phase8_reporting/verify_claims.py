"""
GenIaC-SecBench - Claim verification
=====================================

Checks the assertions made in the paper against the released artifacts, and
fails loudly when they disagree.

Why this exists
---------------
This project has now had two distinct classes of paper-vs-data drift:

1. **Hand-transcribed numbers.** The first findings documents reported schema
   pass rates of 15% and 20% where the data said 1.0% and 10.0%. Fixed by
   generating results documents from the data (``findings_report.py``).

2. **Hand-written prose.** The first preprint stated that scenarios "specify
   functional requirements only and never mention security controls." A majority
   prescribe a security state outright. It also said "four vendors" where the
   model registry spans six. Neither error touched a number, so the generated
   results document could not catch them; both were caught by an external
   auditor and by a manual re-read respectively.

The second class is what this script targets. A claim like "prompts are
functional-only" or "six vendors" is checkable against the artifacts, and any
checkable claim in the paper should be checked mechanically rather than trusted.

Each check states the claim as it appears in the paper, computes the
corresponding value from released data, and reports PASS or FAIL. This is run in
CI and before any submission.

Usage:
    python -m geniac_secbench.phase8_reporting.verify_claims
    python -m geniac_secbench.phase8_reporting.verify_claims --paper paper/main.tex
"""

import re
import sys
import json
import argparse
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

VENDOR_PREFIX = {
    "claude": "Anthropic", "gemini": "Google", "gpt": "OpenAI",
    "llama": "Meta", "mistral": "Mistral AI", "phi": "Microsoft",
}

results = []


def check(name, claim, actual, ok):
    results.append((ok, name, claim, actual))


def load(fname):
    p = PATHS.summary_reports / fname
    if not p.exists():
        return None
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8-sig"))
    return pd.read_csv(p, encoding="utf-8-sig")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default=str(PATHS.root / "paper" / "main.tex"))
    args = ap.parse_args()

    tex = Path(args.paper).read_text(encoding="utf-8") if Path(args.paper).exists() else ""
    m = load("master_results.csv")
    f = load("findings_raw.csv")
    if m is None or f is None:
        print("master_results.csv / findings_raw.csv missing - run the pipeline first.")
        sys.exit(1)
    fa = f[f.status == "FAILED"] if "status" in f.columns else f

    # ---- corpus scale -------------------------------------------------
    check("scenarios", "100", m.scenario_id.nunique(), m.scenario_id.nunique() == 100)
    check("configurations", "12", m.model.nunique(), m.model.nunique() == 12)
    check("artifacts", "1,196", len(m), len(m) == 1196)
    check("findings", "38,803", len(fa), len(fa) == 38803)

    h = load("human_baseline_density.csv")
    if h is not None:
        check("human corpus", "634", len(h), len(h) == 634)

    # ---- vendor count: the "four vendors" error ------------------------
    vendors = {v for mod in m.model.unique()
               for k, v in VENDOR_PREFIX.items() if mod.startswith(k)}
    claimed = None
    for word, n in (("six", 6), ("five", 5), ("four", 4), ("three", 3)):
        if re.search(rf"\b{word} vendors\b", tex):
            claimed = (word, n)
            break
    if claimed:
        check("vendor count", f"'{claimed[0]} vendors' in paper",
              f"{len(vendors)} ({', '.join(sorted(vendors))})",
              claimed[1] == len(vendors))
    else:
        check("vendor count", "(no 'N vendors' phrase found)", len(vendors), True)

    # ---- the functional-only claim -------------------------------------
    # Any surviving assertion that prompts never mention security is a
    # regression: it is the exact error the first preprint shipped.
    bad_patterns = [
        r"functional requirements only",
        r"never mention security",
        r"No prompt mentions security",
    ]
    hits = [p for p in bad_patterns if re.search(p, tex, re.I)]
    check("prompt description",
          "must NOT claim prompts are functional-only",
          f"{len(hits)} offending phrase(s): {hits}" if hits else "no offending phrase",
          not hits)

    pc = load("prompt_classification.csv")
    if pc is not None:
        n_ins = int((pc.prompt_class == "insecure_prescriptive").sum())
        n_fun = int((pc.prompt_class == "functional_only").sum())
        check("prompt classes released", "classification artifact present",
              f"{n_ins} insecure / {n_fun} functional-only of {len(pc)}", True)
        # If most prompts prescribe security, the paper must say so somewhere.
        if (len(pc) - n_fun) > len(pc) / 2:
            mentions = bool(re.search(r"prescrib", tex, re.I))
            check("prescriptiveness disclosed",
                  "paper must discuss prompt prescriptiveness",
                  "discussed" if mentions else "NOT discussed", mentions)

    # ---- severity totals ------------------------------------------------
    for col, claim in (("severity_critical", 778), ("severity_high", 3725),
                       ("severity_medium", 7919), ("severity_low", 10036)):
        got = int(m[col].sum())
        check(col, f"{claim:,}", f"{got:,}", got == claim)

    # ---- coverage --------------------------------------------------------
    cov = load("scan_coverage.csv")
    if cov is not None:
        t = cov.groupby("scanner")[["scenarios_total", "scenarios_covered"]].sum()
        full = bool((t.scenarios_covered == t.scenarios_total).all())
        check("scanner coverage", "100% on all three",
              "; ".join(f"{s} {int(r.scenarios_covered)}/{int(r.scenarios_total)}"
                        for s, r in t.iterrows()), full)

    # ---- master table integrity -----------------------------------------
    dups = int(m.duplicated(subset=["model", "complexity", "scenario_id"]).sum())
    check("master table duplicates", "0", dups, dups == 0)

    # ---- report ----------------------------------------------------------
    width = max(len(n) for _, n, _, _ in results) + 2
    print(f"\n{'CHECK'.ljust(width)}{'CLAIM':<42}{'ACTUAL':<34}RESULT")
    print("-" * (width + 88))
    for ok, name, claim, actual in results:
        print(f"{name.ljust(width)}{str(claim):<42}{str(actual):<34}{'PASS' if ok else 'FAIL'}")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("\nFAILURES:")
        for _, name, claim, actual in failed:
            print(f"  {name}: paper says {claim}, data says {actual}")
        sys.exit(1)
    print("All paper claims verified against released artifacts.")


if __name__ == "__main__":
    main()
