import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

def run_command(cmd, cwd):
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Validation timed out after 30 seconds"
    except Exception as e:
        return False, str(e)

def get_tool_path(tool_name):
    """Cross-platform tool discovery: env var override > PATH > OS-specific
    fallback locations. No hardcoded per-machine paths -- this is what let
    the Docker image's Linux binaries actually get found."""
    import shutil

    env_override = os.environ.get(f"{tool_name.upper().replace('-', '_')}_PATH")
    if env_override and Path(env_override).exists():
        return env_override

    path = shutil.which(tool_name)
    if path:
        return path

    if sys.platform == "win32":
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        winget_fallbacks = {
            'terraform': r"Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe",
            'kubeconform': r"Microsoft\WinGet\Packages\YannHamon.kubeconform_Microsoft.Winget.Source_8wekyb3d8bbwe\kubeconform.exe",
        }
        if tool_name in winget_fallbacks:
            candidate = os.path.join(local_appdata, winget_fallbacks[tool_name])
            if Path(candidate).exists():
                return candidate
    return tool_name  # last resort: hope it's on PATH under this exact name


# Shared Terraform provider plugin cache. Without this, `terraform init`
# downloads a fresh copy of every provider binary into each scenario's
# .terraform/ directory -- across ~1,000 scenarios this is what produced the
# 32 GB of vendored cache purged during the repo reorganization. Sharing one
# cache directory means `terraform init` symlinks/hardlinks instead of
# re-downloading. Module sources (as opposed to providers) still get pulled
# per-directory by design, so cleanup_terraform_cache() below still runs.
_TF_PLUGIN_CACHE = PATHS.root / ".terraform_plugin_cache"
_TF_PLUGIN_CACHE.mkdir(exist_ok=True)
os.environ.setdefault("TF_PLUGIN_CACHE_DIR", str(_TF_PLUGIN_CACHE))


def cleanup_terraform_cache(directory):
    """Remove the per-scenario .terraform/ metadata dir and lock file after
    validation. Provider binaries live in the shared plugin cache above and
    are unaffected; this only removes the per-directory module/state litter."""
    import shutil as _shutil
    tf_dir = Path(directory) / ".terraform"
    if tf_dir.exists():
        _shutil.rmtree(tf_dir, ignore_errors=True)
    lock_file = Path(directory) / ".terraform.lock.hcl"
    if lock_file.exists():
        lock_file.unlink(missing_ok=True)


def validate_terraform(directory):
    tf_cmd = get_tool_path("terraform")
    try:
        init_success, init_out = run_command(f'"{tf_cmd}" init -backend=false', cwd=directory)
        if not init_success:
            return False, f"Terraform Init Failed:\n{init_out}"

        val_success, val_out = run_command(f'"{tf_cmd}" validate -json', cwd=directory)
        if not val_success:
            return False, f"Terraform Validate Failed:\n{val_out}"
        return True, "Valid"
    finally:
        cleanup_terraform_cache(directory)

def validate_cloudformation(file_path):
    cfn_cmd = get_tool_path("cfn-lint")
    cmd = f'"{cfn_cmd}" {file_path.name}'
    success, out = run_command(cmd, cwd=file_path.parent)
    if not success:
        return False, f"cfn-lint Failed:\n{out}"
    return True, "Valid"

def validate_arm(file_path):
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False, "Root is not a JSON object"
        if "resources" not in data:
            return False, "Missing 'resources' key"
        return True, "Valid"
    except Exception as e:
        return False, f"ARM JSON Parsing Failed:\n{str(e)}"

def validate_kubernetes(file_path):
    kube_cmd = get_tool_path("kubeconform")
    cmd = f'"{kube_cmd}" -strict {file_path.name}'
    success, out = run_command(cmd, cwd=file_path.parent)
    if not success:
        return False, f"Kubernetes Validation Failed:\n{out}"
    return True, "Valid"

def get_scenarios(complex_json=None, simple_json=None):
    complex_json = complex_json or str(PATHS.prompts / "scenarios_complex.json")
    simple_json = simple_json or str(PATHS.prompts / "scenarios.json")
    scenarios = {}
    if Path(complex_json).exists():
        with open(complex_json, 'r') as f:
            for s in json.load(f):
                scenarios[s["id"]] = s
    if Path(simple_json).exists():
        with open(simple_json, 'r') as f:
            for s in json.load(f):
                scenarios[s["id"]] = s
    return scenarios

def main():
    parser = argparse.ArgumentParser(description="Phase 2: IaC Schema/Syntactic Validation")
    parser.add_argument("--model", type=str, default="all", help="Model to validate (e.g. gpt-4o, or all)")
    parser.add_argument("--dataset", type=str, default="all", choices=["complex", "simple", "all"], help="Dataset complexity")
    parser.add_argument("--output-csv", type=str, default=str(PATHS.summary_reports / "schema_validity.csv"), help="Path to append results")
    args = parser.parse_args()

    base_dir = PATHS.generated
    scenarios = get_scenarios()
    
    datasets = ["complex", "simple"] if args.dataset == "all" else [args.dataset]
    
    # Check if CSV exists, if not write header
    csv_exists = Path(args.output_csv).exists()
    out_file = open(args.output_csv, 'a', newline='', encoding='utf-8')
    writer = csv.writer(out_file)
    if not csv_exists:
        writer.writerow(["dataset", "model", "scenario_id", "tool", "is_valid", "error_message"])
        
    for ds in datasets:
        ds_dir = base_dir / ds
        if not ds_dir.exists():
            continue
            
        models = [args.model] if args.model != "all" else [d.name for d in ds_dir.iterdir() if d.is_dir()]
        
        for model in models:
            model_dir = ds_dir / model
            if not model_dir.exists():
                continue
                
            logging.info(f"Validating {model} ({ds})")
            
            for sid_dir in model_dir.iterdir():
                if not sid_dir.is_dir():
                    continue
                    
                sid = sid_dir.name
                scenario_meta = scenarios.get(sid, {})
                tool = scenario_meta.get("tool", "Unknown")
                
                # Check what files exist in the dir
                tf_files = list(sid_dir.glob("*.tf"))
                yaml_files = list(sid_dir.glob("*.yaml"))
                json_files = list(sid_dir.glob("*.json"))
                
                is_valid = False
                error_msg = "No recognizable IaC files found."
                
                if tool == "Terraform" and tf_files:
                    is_valid, error_msg = validate_terraform(sid_dir)
                elif tool == "CloudFormation" and (yaml_files or json_files):
                    file_to_check = yaml_files[0] if yaml_files else json_files[0]
                    is_valid, error_msg = validate_cloudformation(file_to_check)
                elif tool == "ARM" and json_files:
                    is_valid, error_msg = validate_arm(json_files[0])
                elif tool == "Kubernetes" and yaml_files:
                    is_valid, error_msg = validate_kubernetes(yaml_files[0])
                
                writer.writerow([ds, model, sid, tool, is_valid, error_msg])
                out_file.flush()
                
    out_file.close()
    _dedupe_and_prune(Path(args.output_csv))
    logging.info("Validation complete.")


def _dedupe_and_prune(csv_path: Path) -> None:
    """Collapse the append-only log into one row per (dataset, model, scenario).

    This file is opened in 'a' mode so results stream to disk as each scenario is
    validated (a crash mid-run keeps what was already checked). The cost is that
    a SECOND run appends a second full copy instead of replacing the first. That
    happened during the Aug 2026 remediation: schema_validity.csv reached 2,115
    rows for 1,132 generated files -- 937 duplicates -- and build_master_table
    then joined against it, inflating master_results.csv to 2,115 rows with every
    model's counts roughly doubled. Nothing errored; the numbers were simply wrong.

    It also strips rows whose model directory no longer exists, so a renamed arm
    (e.g. claude-3-5-sonnet -> claude-sonnet-4-6) doesn't linger as a phantom
    model in every downstream table.

    Keeps the LAST row for each key -- the most recent validation wins.
    """
    if not csv_path.exists():
        return
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
    except Exception as e:  # noqa: BLE001
        logging.warning("Could not post-process %s: %s", csv_path, e)
        return

    before = len(df)
    key = ["dataset", "model", "scenario_id"]
    if not all(k in df.columns for k in key):
        return
    df = df.drop_duplicates(subset=key, keep="last")
    deduped = before - len(df)

    live = {p.name for ds in ("simple", "complex")
            for p in (PATHS.generated / ds).iterdir()
            if (PATHS.generated / ds).exists() and p.is_dir()}
    if live:
        stale = df[~df["model"].isin(live)]
        if len(stale):
            logging.warning("Dropping %d rows for models no longer on disk: %s",
                            len(stale), sorted(stale["model"].unique()))
            df = df[df["model"].isin(live)]

    df.to_csv(csv_path, index=False)
    logging.info("schema_validity: %d -> %d rows (%d duplicates removed)",
                 before, len(df), deduped)

if __name__ == "__main__":
    main()
