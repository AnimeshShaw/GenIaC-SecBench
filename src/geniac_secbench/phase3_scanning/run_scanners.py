"""
GenIaC-SecBench - Security Scanner Pipeline
============================================
Runs Checkov, Trivy, and KICS against all generated IaC code and saves
structured JSON results, split back out to one file per (scenario, scanner)
so downstream parsing is unaffected by how the scan itself was batched.

Design notes (read before changing invocation strategy):

- **Batched, not per-scenario.** Each scanner is invoked ONCE per
  (dataset, model) directory rather than once per scenario. A cold KICS
  invocation costs ~90s in query-loading overhead regardless of how much
  code it scans; batching a 40-scenario directory in one call costs ~10s
  total. The report is then split back into per-scenario JSON files by
  matching each finding's file path against the known scenario IDs in that
  batch, so `data/scan_results/<dataset>/<model>/<scenario_id>/<scanner>.json`
  still exists exactly as before -- parse_results.py does not need to change.

- **Checkov runs through an isolated venv.** Checkov depends on
  `bc-python-hcl2`, which claims the same `hcl2` import name as the vanilla
  `python-hcl2` package the structural-metrics scripts need to parse modern
  Terraform syntax. Both cannot be installed in the same environment without
  one silently shadowing the other (this broke checkov entirely during the
  Phase 2 remediation -- see docs/THREATS_TO_VALIDITY.md). `.venv_checkov/`
  isolates checkov's dependency tree; `scripts/setup_checkov_env.py` creates
  it. Also note: checkov's Windows `.cmd` console-script shim searches PATH
  for a `python` to re-exec itself with, ignoring which venv it was
  installed into -- so checkov MUST be invoked as
  `<venv_python> -m checkov.main`, never via the `checkov`/`checkov.cmd`
  shim, or it silently runs against the wrong (and possibly broken) Python
  environment.

- **`.terraform/` is excluded defensively.** Terraform module caches
  (created by `terraform init` during Phase 2 validation) can contain
  vendored third-party `.tf` files. If they slip into a scan target, their
  findings would be misattributed to the model. Verified empirically that 0%
  of pre-remediation findings came from this source, but the exclusion is
  cheap insurance and required since KICS/Trivy don't share Checkov's
  default vendored-module exclusion.

Usage:
    python -m geniac_secbench.phase3_scanning.run_scanners
    python -m geniac_secbench.phase3_scanning.run_scanners --scanner checkov
    python -m geniac_secbench.phase3_scanning.run_scanners --model gpt-5
    python -m geniac_secbench.phase3_scanning.run_scanners --coverage-report
"""

import os
import sys
import csv
import json
import shutil
import subprocess
import argparse
import logging
import tempfile
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def _checkov_venv_python() -> Path:
    # GENIAC_CHECKOV_VENV lets the Docker image (which sets up the isolated
    # venv at /opt/venv_checkov, outside the repo tree) point here without
    # relying on the local-dev convention of .venv_checkov/ at repo root.
    override = os.environ.get("GENIAC_CHECKOV_VENV")
    venv_dir = Path(override) if override else (PATHS.root / ".venv_checkov")
    return venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


CHECKOV_VENV_PYTHON = _checkov_venv_python()

# ---------------------------------------------------------------------------
# Cross-platform tool discovery
# ---------------------------------------------------------------------------

def get_tool_path(binary_name: str) -> str | None:
    """Env var override > PATH > third_party/ fallback. Returns None if the
    tool genuinely cannot be found (caller decides whether that's fatal)."""
    env_override = os.environ.get(f"{binary_name.upper()}_PATH")
    if env_override and Path(env_override).exists():
        return env_override

    path = shutil.which(binary_name)
    if path:
        return path

    if binary_name == "kics":
        for candidate in [
            PATHS.third_party / "kics" / ("kics.exe" if sys.platform == "win32" else "kics"),
        ]:
            if candidate.exists():
                return str(candidate)

    return None


def _checkov_invocation() -> list[str] | None:
    """Returns the base command list for invoking checkov, preferring the
    isolated venv (see module docstring). Falls back to PATH lookup for
    environments (e.g. the Docker image) where there's no hcl2 conflict."""
    if CHECKOV_VENV_PYTHON.exists():
        return [str(CHECKOV_VENV_PYTHON), "-m", "checkov.main"]
    checkov_bin = get_tool_path("checkov")
    if checkov_bin:
        return [checkov_bin]
    return None


def _checkov_cmd(target_dir: str) -> list[str] | None:
    base = _checkov_invocation()
    if base is None:
        return None
    return base + ["-d", target_dir, "-o", "json", "--quiet", "--compact"]


def _trivy_cmd(target_dir: str) -> list[str] | None:
    trivy_bin = get_tool_path("trivy")
    if trivy_bin is None:
        return None
    return [trivy_bin, "config", target_dir, "-f", "json", "--quiet"]


def _kics_cmd(target_dir: str, out_file: Path) -> list[str] | None:
    kics_bin = get_tool_path("kics")
    if kics_bin is None:
        return None
    return [
        kics_bin, "scan", "-p", target_dir,
        "-o", str(out_file.parent), "--report-formats", "json",
        "--output-name", out_file.stem,
        "--exclude-paths", ".terraform,.git",
    ]


SCANNERS = ["checkov", "trivy", "kics"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_invalid_scenarios(csv_path: Path) -> set:
    """Returns a set of (dataset, model, scenario_id) that failed Phase 2
    schema validation, so they're excluded from the vulnerability corpus."""
    invalid = set()
    if not csv_path.exists():
        logger.warning("Validation CSV %s not found. Skipping validation filter.", csv_path)
        return invalid
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("is_valid") == "False":
                invalid.add((row["dataset"], row["model"], row["scenario_id"]))
    return invalid


def scenario_id_from_path(path_str: str, known_ids: set) -> str | None:
    """Match a finding's file path back to the scenario it came from,
    independent of whether the path is absolute/relative or uses / or \\."""
    normalized = path_str.replace("\\", "/")
    for part in normalized.split("/"):
        if part in known_ids:
            return part
    return None


def needs_scan(out_base: Path, scenario_ids: list[str], scanner: str) -> list[str]:
    """Idempotency check: which scenarios in this batch are missing this
    scanner's output file. Already-scanned scenarios are left untouched."""
    return [sid for sid in scenario_ids if not (out_base / sid / f"{scanner}.json").exists()]


def write_split_output(out_base: Path, sid: str, scanner: str, payload) -> None:
    out_dir = out_base / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{scanner}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f)


# ---------------------------------------------------------------------------
# Per-scanner batch runners -- each takes a model directory containing N
# scenario subdirectories, runs the scanner ONCE, and splits results.
# ---------------------------------------------------------------------------

def batch_checkov(model_dir: Path, scenario_ids: list[str], out_base: Path) -> int:
    cmd = _checkov_cmd(str(model_dir.resolve()))
    if cmd is None:
        logger.warning("checkov not available (venv missing and not on PATH). Skipping.")
        return 0
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        report = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.error("checkov batch scan failed for %s: %s", model_dir, e)
        return 0

    blocks = report if isinstance(report, list) else [report]
    by_scenario: dict[str, list] = {sid: [] for sid in scenario_ids}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for check in (block.get("results", {}) or {}).get("failed_checks", []) or []:
            sid = scenario_id_from_path(str(check.get("file_path", "")), set(scenario_ids))
            if sid:
                by_scenario[sid].append({**check, "_check_type": block.get("check_type")})

    written = 0
    for sid, checks in by_scenario.items():
        write_split_output(out_base, sid, "checkov", {
            "results": {"failed_checks": checks},
        })
        written += 1
    return written


def batch_trivy(model_dir: Path, scenario_ids: list[str], out_base: Path) -> int:
    cmd = _trivy_cmd(str(model_dir.resolve()))
    if cmd is None:
        logger.warning("trivy not available (not on PATH / TRIVY_PATH unset). Skipping.")
        return 0
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        report = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.error("trivy batch scan failed for %s: %s", model_dir, e)
        return 0

    by_scenario: dict[str, list] = {sid: [] for sid in scenario_ids}
    for res in report.get("Results", []) or []:
        target = str(res.get("Target", ""))
        if ".terraform" in target.replace("\\", "/").split("/"):
            continue
        sid = scenario_id_from_path(target, set(scenario_ids))
        if sid:
            by_scenario[sid].append(res)

    written = 0
    for sid, results in by_scenario.items():
        write_split_output(out_base, sid, "trivy", {**{k: v for k, v in report.items() if k != "Results"}, "Results": results})
        written += 1
    return written


def batch_kics(model_dir: Path, scenario_ids: list[str], out_base: Path, tmp_dir: Path) -> int:
    kics_bin = get_tool_path("kics")
    if kics_bin is None:
        logger.warning("kics not available (not on PATH / KICS_PATH / third_party/kics). Skipping.")
        return 0
    out_name = f"kics_batch_{model_dir.parent.name}_{model_dir.name}"
    out_file = tmp_dir / out_name
    cmd = _kics_cmd(str(model_dir.resolve()), out_file)
    try:
        subprocess.run(cmd, cwd=str(Path(kics_bin).parent), capture_output=True, text=True, timeout=600)
        with open(str(out_file) + ".json", "r", encoding="utf-8") as f:
            report = json.load(f)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("kics batch scan failed for %s: %s", model_dir, e)
        return 0

    by_scenario: dict[str, list] = {sid: [] for sid in scenario_ids}
    for query in report.get("queries", []) or []:
        for finding_file in query.get("files", []) or []:
            sid = scenario_id_from_path(str(finding_file.get("file_name", "")), set(scenario_ids))
            if sid:
                by_scenario[sid].append({**{k: v for k, v in query.items() if k != "files"}, "file": finding_file})

    written = 0
    for sid, findings in by_scenario.items():
        write_split_output(out_base, sid, "kics", {"queries": findings})
        written += 1
    return written


BATCH_RUNNERS = {"checkov": batch_checkov, "trivy": batch_trivy}  # kics handled separately (needs tmp_dir)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def scan_all(
    gen_root: Path,
    results_root: Path,
    scanner_names: list[str] | None = None,
    model_filter: str | None = None,
    validation_csv: Path | None = None,
    exclude_invalid: bool = False,
):
    # NOTE on exclude_invalid: the project's own methodology
    # (docs/methodology/iac_benchmark_methodology.md, Phase 3) explicitly
    # allows scanning everything and flagging Phase-2 failures as a separate
    # category, rather than skipping them at scan time -- and the original
    # pre-remediation data did exactly that (e.g. llama3's complex scenarios
    # are 40/40 schema-invalid yet 40/40 Checkov-scanned in the archived
    # results). Excluding invalid scenarios at scan time would silently
    # regress coverage below what already exists. Default is OFF to match;
    # `terraform_valid` remains available as a column for downstream
    # statistical filtering (Phase 6) instead.
    validation_csv = validation_csv or (PATHS.summary_reports / "schema_validity.csv")
    invalid_scenarios = load_invalid_scenarios(validation_csv) if exclude_invalid else set()
    active_scanners = scanner_names or SCANNERS

    dataset_dirs = sorted([d for d in gen_root.iterdir() if d.is_dir()])
    coverage_rows = []

    with tempfile.TemporaryDirectory(prefix="geniac_kics_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        for dataset_dir in dataset_dirs:
            dataset_name = dataset_dir.name
            model_dirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir()])
            if model_filter:
                model_dirs = [d for d in model_dirs if d.name == model_filter]

            for model_dir in tqdm(model_dirs, desc=f"{dataset_name}", unit="model"):
                model_name = model_dir.name
                all_scenario_ids = sorted(
                    d.name for d in model_dir.iterdir()
                    if d.is_dir() and d.name != ".terraform"
                )
                # Exclude scenarios that failed Phase 2 schema validation.
                scenario_ids = [
                    sid for sid in all_scenario_ids
                    if (dataset_name, model_name, sid) not in invalid_scenarios
                ]
                out_base = results_root / dataset_name / model_name

                for scanner in active_scanners:
                    missing = needs_scan(out_base, scenario_ids, scanner)
                    if not missing:
                        continue  # idempotent skip: this model/dataset/scanner is fully covered
                    logger.info(
                        "%s/%s: %d/%d scenarios missing %s -- running batch scan",
                        dataset_name, model_name, len(missing), len(scenario_ids), scanner,
                    )
                    if scanner == "kics":
                        batch_kics(model_dir, scenario_ids, out_base, tmp_dir)
                    else:
                        BATCH_RUNNERS[scanner](model_dir, scenario_ids, out_base)

                for scanner in active_scanners:
                    covered = sum((out_base / sid / f"{scanner}.json").exists() for sid in scenario_ids)
                    coverage_rows.append({
                        "dataset": dataset_name, "model": model_name, "scanner": scanner,
                        "scenarios_total": len(scenario_ids), "scenarios_covered": covered,
                    })

    coverage_path = PATHS.summary_reports / "scan_coverage.csv"
    with open(coverage_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["dataset", "model", "scanner", "scenarios_total", "scenarios_covered"])
        writer.writeheader()
        writer.writerows(coverage_rows)
    logger.info("Coverage manifest written to %s", coverage_path)

    incomplete = [r for r in coverage_rows if r["scenarios_covered"] < r["scenarios_total"]]
    if incomplete:
        logger.warning("%d (model, scanner) pairs are still short of full coverage:", len(incomplete))
        for r in incomplete:
            logger.warning("  %s/%s [%s]: %d/%d", r["dataset"], r["model"], r["scanner"], r["scenarios_covered"], r["scenarios_total"])
    else:
        logger.info("Full scanner coverage achieved across all models and datasets.")

    logger.info("Scanning complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GenIaC-SecBench Security Scanner Pipeline")
    parser.add_argument("--generated", type=str, default=str(PATHS.generated))
    parser.add_argument("--results", type=str, default=str(PATHS.scan_results))
    parser.add_argument("--validation-csv", type=str, default=str(PATHS.summary_reports / "schema_validity.csv"))
    parser.add_argument("--scanner", type=str, nargs="+", choices=SCANNERS, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument(
        "--exclude-invalid", action="store_true",
        help="Skip scenarios that failed Phase 2 schema validation (off by default -- see scan_all() docstring)",
    )
    args = parser.parse_args()

    scan_all(
        gen_root=Path(args.generated),
        results_root=Path(args.results),
        scanner_names=args.scanner,
        model_filter=args.model,
        validation_csv=Path(args.validation_csv),
        exclude_invalid=args.exclude_invalid,
    )


if __name__ == "__main__":
    main()
