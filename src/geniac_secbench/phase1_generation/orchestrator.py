"""
InfraSecBench - End-to-End Orchestrator
=======================================
Runs the full pipeline sequentially:
  1. Generate IaC code from LLMs
  2. Scan generated code with security tools
  3. Parse and aggregate results
  4. Generate visualisations

Usage:
    python src/orchestrator.py              # Full pipeline
    python src/orchestrator.py --skip-gen   # Skip generation (use existing code)
    python src/orchestrator.py --dry-run    # Preview without API calls
"""

import subprocess
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

PKG = "src/geniac_secbench"  # subprocess invocation root, relative to PATHS.root

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_step(name: str, cmd: list[str]) -> bool:
    """Run a pipeline step, returning True on success."""
    logger.info("=" * 60)
    logger.info("STEP: %s", name)
    logger.info("CMD:  %s", " ".join(cmd))
    logger.info("=" * 60)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        logger.error("Step '%s' failed with exit code %d", name, result.returncode)
        return False
    logger.info("Step '%s' completed successfully.", name)
    return True


def main():
    parser = argparse.ArgumentParser(description="InfraSecBench – E2E Orchestrator")
    parser.add_argument("--skip-gen", action="store_true", help="Skip the IaC generation step.")
    parser.add_argument("--skip-scan", action="store_true", help="Skip the scanning step.")
    parser.add_argument("--skip-parse", action="store_true", help="Skip the parsing step.")
    parser.add_argument("--skip-viz", action="store_true", help="Skip the visualisation step.")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to the generation step.")
    parser.add_argument("--model", type=str, default=None, help="Run only a specific model.")
    args = parser.parse_args()

    python = sys.executable
    steps = []

    # Step 1: Generate IaC
    if not args.skip_gen:
        # Must stay in sync with MODEL_REGISTRY in generate_iac.py.
        # "claude-3-5-sonnet" was renamed to "claude-sonnet-4-6" (the label named a
        # previous-generation model but the registry called the current one), and the
        # Anthropic reasoning arm is now split into -cot (prompt-engineered) and
        # -thinking (real extended thinking). See docs/THREATS_TO_VALIDITY.md §1.1/§1.4.
        MODELS_TO_RUN = [
            "gpt-5", "claude-opus-4-6", "gemini-3.7-flash", "gemini-3.1-pro",
            "gpt-4o", "claude-sonnet-4-6",
            "gpt-5-thinking", "claude-opus-4-6-thinking", "claude-opus-4-6-cot",
        ]
        
        DATASETS = [str(PATHS.prompts / "scenarios_complex.json"), str(PATHS.prompts / "scenarios.json")]

        models_list = [args.model] if args.model else MODELS_TO_RUN

        for ds in DATASETS:
            for m in models_list:
                gen_cmd = [python, f"{PKG}/phase1_generation/generate_iac.py", "--model", m, "--scenarios", ds]
                if args.dry_run:
                    gen_cmd.append("--dry-run")
                ds_name = "complex" if "complex" in ds else "simple"
                steps.append((f"Generate IaC Code ({m} - {ds_name})", gen_cmd))

    # Step 2: Run Scanners
    if not args.skip_scan:
        scan_cmd = [python, f"{PKG}/phase3_scanning/run_scanners.py"]
        if args.model:
            scan_cmd.extend(["--model", args.model])
        steps.append(("Run Security Scanners", scan_cmd))

    # Step 3: Parse Results
    if not args.skip_parse:
        steps.append(("Parse & Aggregate Results", [python, f"{PKG}/phase3_scanning/parse_results.py"]))

    # Step 4: Visualise
    if not args.skip_viz:
        steps.append(("Generate Visualisations", [python, f"{PKG}/phase8_reporting/visualize_final.py"]))

    if not steps:
        logger.warning("All steps skipped. Nothing to do.")
        return

    logger.info("InfraSecBench Pipeline – %d step(s) queued", len(steps))

    for name, cmd in steps:
        success = run_step(name, cmd)
        if not success:
            logger.error("Pipeline aborted at step: %s", name)
            sys.exit(1)

    logger.info("=" * 60)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
