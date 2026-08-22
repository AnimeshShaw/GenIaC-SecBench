import argparse
import csv
import json
import logging
import os
import subprocess
import time
from pathlib import Path

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
    # Try finding in PATH first
    import shutil
    path = shutil.which(tool_name)
    if path: return path
    
    # Fallback to local appdata winget links/packages or conda
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if tool_name == 'terraform':
        return os.path.join(local_appdata, r"Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe")
    elif tool_name == 'kubeconform':
        return os.path.join(local_appdata, r"Microsoft\WinGet\Packages\YannHamon.kubeconform_Microsoft.Winget.Source_8wekyb3d8bbwe\kubeconform.exe")
    elif tool_name == 'cfn-lint':
        # Fallback to miniconda scripts
        return r"C:\Users\anim3\miniconda3\Scripts\cfn-lint.exe"
    return tool_name

def validate_terraform(directory):
    tf_cmd = get_tool_path("terraform")
    init_success, init_out = run_command(f'"{tf_cmd}" init -backend=false', cwd=directory)
    if not init_success:
        return False, f"Terraform Init Failed:\n{init_out}"
    
    val_success, val_out = run_command(f'"{tf_cmd}" validate -json', cwd=directory)
    if not val_success:
        return False, f"Terraform Validate Failed:\n{val_out}"
    return True, "Valid"

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

def get_scenarios(complex_json="data/scenarios_complex.json", simple_json="data/scenarios.json"):
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
    parser.add_argument("--output-csv", type=str, default="data/schema_validity.csv", help="Path to append results")
    args = parser.parse_args()

    base_dir = Path("data/generated")
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
    logging.info("Validation complete.")

if __name__ == "__main__":
    main()
