"""
InfraSecBench - Security Scanner Pipeline
==========================================
Runs Checkov, Trivy, and KICS against all generated IaC code and saves
structured JSON results. Excludes scenarios that failed Phase 2 validation.

Prerequisites:
    pip install checkov
    winget install AquaSecurity.Trivy
    KICS binary in tools/kics/

Usage:
    python src/phase3_scanning/run_scanners.py
    python src/phase3_scanning/run_scanners.py --scanner checkov        # Run only Checkov
    python src/phase3_scanning/run_scanners.py --model gpt-5            # Scan only one model's output
"""

import os
import sys
import csv
import json
import shutil
import subprocess
import argparse
import logging
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scanner Definitions
# ---------------------------------------------------------------------------

def get_tool_path(binary_name):
    path = shutil.which(binary_name)
    if path: return path
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if binary_name == 'trivy':
        return os.path.join(local_appdata, r"Microsoft\WinGet\Packages\AquaSecurity.Trivy_Microsoft.Winget.Source_8wekyb3d8bbwe\trivy.exe")
    elif binary_name == 'kics':
        kics_path = Path("tools/kics/kics.exe").resolve()
        if kics_path.exists(): return str(kics_path)
    elif binary_name == 'checkov':
        if sys.platform == "win32":
            return os.path.join(os.path.dirname(sys.executable), "Scripts", "checkov.cmd")
    return binary_name

def _checkov_cmd(target_dir: str, out_file: Path) -> list[str]:
    return [get_tool_path("checkov"), "-d", target_dir, "-o", "json", "--quiet", "--compact"]

def _trivy_cmd(target_dir: str, out_file: Path) -> list[str]:
    return [get_tool_path("trivy"), "config", target_dir, "-f", "json", "--quiet"]

def _kics_cmd(target_dir: str, out_file: Path) -> list[str]:
    return [get_tool_path("kics"), "scan", "-p", target_dir, "-o", str(out_file.parent), "--report-formats", "json", "--output-name", out_file.stem]

SCANNERS = {
    "checkov": {"cmd_builder": _checkov_cmd, "check_bin": "checkov", "writes_to_stdout": True},
    "trivy":   {"cmd_builder": _trivy_cmd,   "check_bin": "trivy", "writes_to_stdout": True},
    "kics":    {"cmd_builder": _kics_cmd,    "check_bin": "kics", "writes_to_stdout": False},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_scanner_installed(name: str, binary: str) -> bool:
    """Return True if the scanner binary is available."""
    if get_tool_path(binary) != binary or shutil.which(binary):
        return True
    logger.warning("Scanner '%s' not found. Skipping.", name)
    return False

def load_invalid_scenarios(csv_path: str) -> set:
    """Returns a set of (dataset, model, scenario_id) that failed Phase 2 validation."""
    invalid = set()
    if not Path(csv_path).exists():
        logger.warning(f"Validation CSV {csv_path} not found. Skipping validation filter.")
        return invalid
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('is_valid') == 'False':
                invalid.add((row['dataset'], row['model'], row['scenario_id']))
    return invalid

def run_scanner(cmd: list[str], out_file: Path, writes_to_stdout: bool, cwd=None) -> bool:
    """Execute a scanner command."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE if writes_to_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,  # 3 min per scan max
            cwd=cwd
        )
        if writes_to_stdout:
            out_file.write_text(result.stdout, encoding="utf-8")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Timeout scanning %s", cmd)
        return False
    except Exception as e:
        logger.error("Error running %s: %s", cmd[0], e)
        return False


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def scan_all(
    gen_root: Path,
    results_root: Path,
    scanner_names: list[str] | None = None,
    model_filter: str | None = None,
    validation_csv: str = "data/schema_validity.csv"
):
    invalid_scenarios = load_invalid_scenarios(validation_csv)
    
    active_scanners = {}
    for name, cfg in SCANNERS.items():
        if scanner_names and name not in scanner_names:
            continue
        if check_scanner_installed(name, cfg["check_bin"]):
            active_scanners[name] = cfg

    if not active_scanners:
        logger.error("No scanners available.")
        sys.exit(1)

    dataset_dirs = sorted([d for d in gen_root.iterdir() if d.is_dir()])
    
    for dataset_dir in dataset_dirs:
        dataset_name = dataset_dir.name
        model_dirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir()])
        if model_filter:
            model_dirs = [d for d in model_dirs if d.name == model_filter]

        for model_dir in model_dirs:
            model_name = model_dir.name
            scenario_dirs = sorted([d for d in model_dir.iterdir() if d.is_dir()])
            logger.info(f"Scanning model: {dataset_name}/{model_name} ({len(scenario_dirs)} scenarios)")

            for scenario_dir in tqdm(scenario_dirs, desc=f"{dataset_name}/{model_name}", unit="scenario"):
                sid = scenario_dir.name
                
                # Exclude if it failed Phase 2 validation
                if (dataset_name, model_name, sid) in invalid_scenarios:
                    continue
                
                out_base = results_root / dataset_name / model_name / sid

                for scanner_name, scanner_cfg in active_scanners.items():
                    out_file = out_base / f"{scanner_name}.json"
                    if out_file.exists():
                        continue  # idempotent skip
                    
                    target_dir_abs = scenario_dir.resolve()
                    out_file_abs = out_file.resolve()
                    cmd = scanner_cfg["cmd_builder"](str(target_dir_abs), out_file_abs)
                    
                    cwd = None
                    if scanner_name == "kics":
                        cwd = str(Path(get_tool_path("kics")).parent.resolve())

                    run_scanner(cmd, out_file_abs, scanner_cfg["writes_to_stdout"], cwd=cwd)

    logger.info("Scanning complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="InfraSecBench Security Scanner Pipeline")
    parser.add_argument("--generated", type=str, default="data/generated")
    parser.add_argument("--results", type=str, default="data/scan_results")
    parser.add_argument("--validation-csv", type=str, default="data/schema_validity.csv")
    parser.add_argument("--scanner", type=str, nargs="+", choices=list(SCANNERS.keys()), default=None)
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()

    scan_all(
        gen_root=Path(args.generated),
        results_root=Path(args.results),
        scanner_names=args.scanner,
        model_filter=args.model,
        validation_csv=args.validation_csv
    )

if __name__ == "__main__":
    main()
