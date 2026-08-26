"""
GenIaC-SecBench - Phase 3b: security scan of the human-authored reference corpus
=================================================================================

Runs the same three scanners (Checkov, Trivy, KICS) over the 634 human-written
IaC files used as the structural baseline, and joins the findings to the
per-file resource counts in `human_reference_metrics.csv` to produce a HUMAN
vulnerability density directly comparable to the per-model densities in
`master_results.csv`.

Why this exists
---------------
Until now the human corpus was used only for STRUCTURAL comparison (AST depth,
resource count, resource diversity via KS tests). It had never been security
scanned -- `data/scan_results/` contained only the LLM outputs. Every
vulnerability-density figure in the study was therefore LLM-vs-LLM with no human
anchor, which leaves the central practical question unanswerable:

    Are LLMs actually worse than human engineers at writing secure IaC,
    or do they simply write *more* infrastructure per file?

Without a human density baseline, "LLMs average 8-12 vulnerabilities per
resource" has no referent. With it, the comparison is direct.

Caveats that belong in the paper (see docs/THREATS_TO_VALIDITY.md 5.5)
----------------------------------------------------------------------
* The human corpus is NOT a matched control. These files were not written
  against the 100 benchmark scenarios; they come from three public repositories
  and many are curated *examples* rather than production infrastructure.
  Example templates are often deliberately minimal and may omit hardening that
  production code would carry -- which can bias the human baseline in EITHER
  direction. State the direction is unknown rather than assuming it favours one.
* Scanner rule coverage differs by format, and the corpus format mix
  (tf/yaml/json) differs from the generated mix. Report per-format where cell
  sizes allow.

Usage:
    python -m geniac_secbench.phase3_scanning.scan_human_baseline
    python -m geniac_secbench.phase3_scanning.scan_human_baseline --rescan
"""

import sys
import json
import shutil
import logging
import argparse
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS
from geniac_secbench.phase3_scanning.run_scanners import (
    get_tool_path, _checkov_invocation, _utf8_env,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

RAW_OUT = PATHS.data / "scan_results_human"
FINDINGS_OUT = PATHS.summary_reports / "human_baseline_findings.csv"
DENSITY_OUT = PATHS.summary_reports / "human_baseline_density.csv"


def _norm(p: str) -> str:
    return str(p).replace("\\", "/").lower()


def scan_checkov(target: Path, out: Path) -> int:
    base = _checkov_invocation()
    if base is None:
        logger.warning("checkov unavailable; skipping")
        return 0
    cmd = base + ["-d", str(target), "-o", "json", "--quiet", "--compact"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=_utf8_env())
        data = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.error("checkov failed on %s: %s", target, e)
        return 0
    out.write_text(json.dumps(data), encoding="utf-8")
    blocks = data if isinstance(data, list) else [data]
    return sum(len((b.get("results", {}) or {}).get("failed_checks", []) or [])
               for b in blocks if isinstance(b, dict))


def scan_trivy(target: Path, out: Path) -> int:
    binp = get_tool_path("trivy")
    if not binp:
        logger.warning("trivy unavailable; skipping")
        return 0
    cmd = [binp, "config", str(target), "-f", "json", "--quiet"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=_utf8_env())
        data = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.error("trivy failed on %s: %s", target, e)
        return 0
    out.write_text(json.dumps(data), encoding="utf-8")
    return sum(len(res.get("Misconfigurations", []) or [])
               for res in (data.get("Results") or []))


def scan_kics(target: Path, out: Path) -> int:
    binp = get_tool_path("kics")
    if not binp:
        logger.warning("kics unavailable; skipping")
        return 0
    with tempfile.TemporaryDirectory(prefix="geniac_kics_human_") as td:
        # Dots are stripped from --output-name by KICS's own extension handling
        # (see run_scanners.batch_kics); keep the name dot-free.
        name = f"kics_human_{target.name}".replace(".", "_")
        cmd = [binp, "scan", "-p", str(target), "-o", td,
               "--report-formats", "json", "--output-name", name,
               "--exclude-paths", ".terraform,.git"]
        try:
            proc = subprocess.run(cmd, cwd=str(Path(binp).parent),
                                  capture_output=True, text=True, timeout=3600, env=_utf8_env())
        except subprocess.TimeoutExpired:
            logger.error("kics timed out on %s", target)
            return 0
        rp = Path(td) / f"{name}.json"
        if not rp.exists():
            logger.error("kics produced no report for %s (exit=%s)", target, proc.returncode)
            return 0
        data = json.loads(rp.read_text(encoding="utf-8"))
    out.write_text(json.dumps(data), encoding="utf-8")
    return sum(len(q.get("files", []) or []) for q in (data.get("queries") or []))


def extract_findings(raw_dir: Path) -> pd.DataFrame:
    """Flatten the three raw reports into one row per finding, keyed by file path."""
    rows = []

    p = raw_dir / "checkov.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        for b in (data if isinstance(data, list) else [data]):
            if not isinstance(b, dict):
                continue
            for c in (b.get("results", {}) or {}).get("failed_checks", []) or []:
                rows.append({"scanner": "checkov", "file_path": c.get("file_path", ""),
                             "rule_id": c.get("check_id", ""),
                             "severity": (c.get("severity") or "UNKNOWN"),
                             "description": c.get("check_name", "")})

    p = raw_dir / "trivy.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        for res in (data.get("Results") or []):
            tgt = res.get("Target", "")
            for m in (res.get("Misconfigurations") or []):
                rows.append({"scanner": "trivy", "file_path": tgt,
                             "rule_id": m.get("ID", ""),
                             "severity": (m.get("Severity") or "UNKNOWN"),
                             "description": m.get("Title", "")})

    p = raw_dir / "kics.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        for q in (data.get("queries") or []):
            for f in (q.get("files") or []):
                rows.append({"scanner": "kics", "file_path": f.get("file_name", ""),
                             "rule_id": q.get("query_id", ""),
                             "severity": (q.get("severity") or "UNKNOWN").upper(),
                             "description": q.get("query_name", "")})

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescan", action="store_true", help="Re-run scanners even if reports exist.")
    args = ap.parse_args()

    corpus = PATHS.data / "human_reference_dataset"
    if not corpus.is_dir():
        logger.error("Human corpus not found at %s", corpus)
        sys.exit(1)

    repos = sorted([d for d in corpus.iterdir() if d.is_dir()])
    logger.info("Human corpus: %d repositories", len(repos))

    all_findings = []
    for repo in repos:
        out_dir = RAW_OUT / repo.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, fn in (("checkov", scan_checkov), ("trivy", scan_trivy), ("kics", scan_kics)):
            target = out_dir / f"{name}.json"
            if target.exists() and not args.rescan:
                logger.info("%s/%s already scanned; skipping", repo.name, name)
                continue
            logger.info("scanning %s with %s ...", repo.name, name)
            n = fn(repo, target)
            logger.info("  %s: %d findings", name, n)
        df = extract_findings(out_dir)
        if len(df):
            df["repo"] = repo.name
            all_findings.append(df)

    if not all_findings:
        logger.error("No findings extracted.")
        sys.exit(1)

    findings = pd.concat(all_findings, ignore_index=True)
    findings.to_csv(FINDINGS_OUT, index=False, encoding="utf-8")
    logger.info("Wrote %s (%d findings)", FINDINGS_OUT, len(findings))

    # ---- join to per-file resource counts --------------------------------
    metrics = pd.read_csv(PATHS.summary_reports / "human_reference_metrics.csv",
                          encoding="utf-8-sig")
    metrics["_key"] = metrics["file_path"].map(_norm)

    # Scanner paths are relative to the scanned repo dir; match on suffix.
    counts = {}
    for _, r in findings.iterrows():
        counts[_norm(r["file_path"])] = counts.get(_norm(r["file_path"]), 0) + 1

    def lookup(key: str) -> int:
        total = 0
        for fk, c in counts.items():
            # a finding path is a suffix of the absolute metric path (or vice versa)
            if fk and (key.endswith(fk.lstrip("./")) or fk.endswith(key.split("human_reference_dataset/")[-1])):
                total += c
        return total

    metrics["vuln_count"] = metrics["_key"].map(lookup)
    metrics["density"] = metrics["vuln_count"] / metrics["resource_count"].where(
        metrics["resource_count"] > 0)
    metrics.drop(columns=["_key"]).to_csv(DENSITY_OUT, index=False, encoding="utf-8")
    logger.info("Wrote %s", DENSITY_OUT)

    scored = metrics[metrics["resource_count"] > 0]
    logger.info("\n=== HUMAN BASELINE ===")
    logger.info("files scanned            : %d", len(metrics))
    logger.info("files with >0 resources  : %d", len(scored))
    logger.info("total findings           : %d", int(metrics["vuln_count"].sum()))
    logger.info("mean resources / file    : %.2f", metrics["resource_count"].mean())
    logger.info("mean findings / file     : %.2f", metrics["vuln_count"].mean())
    logger.info("MEAN DENSITY (vuln/res)  : %.3f", scored["density"].mean())
    logger.info("MEDIAN DENSITY           : %.3f", scored["density"].median())
    logger.info("\nby format:")
    for fmt, g in scored.groupby("format"):
        logger.info("  %-6s n=%3d  resources=%5.2f  findings=%6.2f  density=%.3f",
                    fmt, len(g), g["resource_count"].mean(),
                    g["vuln_count"].mean(), g["density"].mean())


if __name__ == "__main__":
    main()
