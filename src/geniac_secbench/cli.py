"""
GenIaC-SecBench - Pipeline CLI
================================
Single entry point for running the benchmark pipeline end to end or one
phase at a time. Replaces the old root-level `reproduce.py`, which called
two scripts that no longer existed (`validate_all.py`, `glmm_analysis.py`)
and never invoked `build_master_table.py`, `parse_results.py`, Phase 7, or
Phase 8 at all -- a full `--all` run silently stopped after generation.

Usage:
    python -m geniac_secbench.cli --phase all              # everything, in order
    python -m geniac_secbench.cli --phase scan              # Phase 3 only
    python -m geniac_secbench.cli --phase analyze            # Phases 4+6 only
    python -m geniac_secbench.cli --phase all --skip-generation
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PKG_ROOT = Path(__file__).resolve().parent


def run(module: str, extra_args: list[str] | None = None) -> None:
    """Run a phase script as `python -m geniac_secbench.<module>`."""
    cmd = [sys.executable, "-m", f"geniac_secbench.{module}"] + (extra_args or [])
    logger.info("--- Running %s ---", module)
    result = subprocess.run(cmd, cwd=str(PATHS.root))
    if result.returncode != 0:
        logger.error("Phase script %s failed with exit code %d", module, result.returncode)
        sys.exit(result.returncode)


PHASES = {
    "generate": [
        "phase1_generation.orchestrator",  # generation only; pass --skip-scan --skip-parse --skip-viz below
    ],
    "validate": [
        "phase2_validation.validate_iac",
    ],
    "scan": [
        "phase3_scanning.run_scanners",
        # The human reference corpus is scanned with the IDENTICAL toolchain.
        # This is what makes the central comparison possible: without it every
        # density figure is model-vs-model with no reference point.
        "phase3_scanning.scan_human_baseline",
        "phase3_scanning.parse_results",
    ],
    "structural": [
        "phase4_structural.extract_metrics",
        "phase4_structural.extract_human_metrics",
        "phase4_structural.ks_test",
        "phase4_structural.ks_test_human",
    ],
    "judge": [
        "phase5_llm_judge.judge",
    ],
    "statistics": [
        "phase6_statistics.build_master_table",
        "phase6_statistics.friedman_test",
        "phase6_statistics.nb_glmm",
    ],
    # Inter-rater and human-vs-judge agreement. Uses agreement_metrics, which
    # supersedes the earlier fleiss_kappa.py / human_vs_grok.py pair: those two
    # printed to stdout and persisted nothing, so re-running Phase 7 could not
    # refresh human_agreement_metrics.json and the paper's kappa figures aged
    # out of sync with the data. They also took the lowest value on a 3-way
    # rater tie instead of the median.
    "human_review": [
        "phase7_human_review.agreement_metrics",
    ],
    "report": [
        "phase8_reporting.visualize_final",
        "phase8_reporting.visualize_human_baseline",
        # Regenerates docs/findings/RESULTS.md straight from the result files,
        # so no published number is ever hand-transcribed.
        "phase8_reporting.findings_report",
    ],
}

# `analyze` = everything that doesn't need API keys or scanner binaries --
# safe to run against an already-downloaded dataset (matches the old
# `--analyze-only` flag's intent).
PHASES["analyze"] = (PHASES["structural"] + PHASES["statistics"]
                     + PHASES["human_review"] + PHASES["report"])


def main():
    parser = argparse.ArgumentParser(description="GenIaC-SecBench pipeline CLI")
    parser.add_argument(
        "--phase",
        choices=["all", *PHASES.keys()],
        default="analyze",
        help="Which phase to run. 'all' runs generate -> validate -> scan -> structural -> judge -> statistics -> human_review -> report.",
    )
    parser.add_argument("--model", type=str, default=None, help="Restrict to a single model where the phase supports it.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without calling LLM APIs (generation phase only).")
    args = parser.parse_args()

    if args.phase == "all":
        order = ["generate", "validate", "scan", "structural", "judge",
                 "statistics", "human_review", "report"]
    else:
        order = [args.phase]

    for phase in order:
        for module in PHASES[phase]:
            extra = []
            if args.model and "generate" not in module and "validate" not in module and "run_scanners" not in module:
                pass  # most analysis scripts operate over all models at once by design
            if args.model and module in ("phase2_validation.validate_iac", "phase3_scanning.run_scanners"):
                extra += ["--model", args.model]
            if args.dry_run and module == "phase1_generation.orchestrator":
                extra += ["--dry-run"]
            run(module, extra)

    logger.info("Pipeline complete (phase=%s).", args.phase)


if __name__ == "__main__":
    main()
