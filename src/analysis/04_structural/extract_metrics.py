import os
import json
import logging
import argparse
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

import hcl2
import yaml

# Add a default constructor to handle CloudFormation tags like !Ref, !GetAtt, etc.
def default_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return str(node)

yaml.SafeLoader.add_multi_constructor('!', default_constructor)

def get_ast_depth(obj, current_depth=1):
    if isinstance(obj, dict):
        if not obj: return current_depth
        return max((get_ast_depth(v, current_depth + 1) for v in obj.values()), default=current_depth)
    elif isinstance(obj, list):
        if not obj: return current_depth
        return max((get_ast_depth(item, current_depth + 1) for item in obj), default=current_depth)
    return current_depth

def extract_metrics(file_path: Path, tool: str) -> dict:
    """Extract structural metrics from an IaC file based on its tool type."""
    metrics = {
        "resource_count": 0,
        "resource_diversity": 0,
        "ast_depth": 0,
        "iam_complexity": 0
    }
    
    try:
        if tool == "Terraform":
            with open(file_path, 'r', encoding='utf-8') as f:
                parsed = hcl2.load(f)
            
            metrics["ast_depth"] = get_ast_depth(parsed)
            
            resources = parsed.get("resource", [])
            unique_types = set()
            iam_keywords = ["iam", "policy", "role", "permission", "binding"]
            
            for res_block in resources:
                for res_type, res_dict in res_block.items():
                    metrics["resource_count"] += len(res_dict)
                    unique_types.add(res_type)
                    
                    if any(k in res_type.lower() for k in iam_keywords):
                        metrics["iam_complexity"] += len(res_dict)
            
            metrics["resource_diversity"] = len(unique_types)
            
        elif tool == "ARM" or tool == "CloudFormation":
            # Treat CloudFormation as JSON/YAML interchangeably
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix == ".json":
                    parsed = json.load(f)
                else:
                    parsed = yaml.safe_load(f) or {}
            
            metrics["ast_depth"] = get_ast_depth(parsed)
            
            resources = parsed.get("Resources", parsed.get("resources", []))
            unique_types = set()
            iam_keywords = ["iam", "policy", "role", "permission", "roleassignment"]
            
            if isinstance(resources, dict):
                metrics["resource_count"] = len(resources)
                for res_name, res_dict in resources.items():
                    r_type = res_dict.get("Type", res_dict.get("type", "Unknown"))
                    unique_types.add(r_type)
                    if any(k in r_type.lower() for k in iam_keywords):
                        metrics["iam_complexity"] += 1
            elif isinstance(resources, list):
                metrics["resource_count"] = len(resources)
                for res in resources:
                    r_type = res.get("type", res.get("Type", "Unknown"))
                    unique_types.add(r_type)
                    if any(k in r_type.lower() for k in iam_keywords):
                        metrics["iam_complexity"] += 1
                        
            metrics["resource_diversity"] = len(unique_types)
            
        elif tool == "Kubernetes" or "K8s" in tool:
            with open(file_path, 'r', encoding='utf-8') as f:
                docs = list(yaml.safe_load_all(f))
            
            metrics["ast_depth"] = get_ast_depth(docs)
            unique_types = set()
            iam_keywords = ["role", "clusterrole", "rolebinding", "clusterrolebinding", "serviceaccount"]
            
            for doc in docs:
                if not doc: continue
                metrics["resource_count"] += 1
                kind = doc.get("kind", "Unknown")
                unique_types.add(kind)
                if any(k in kind.lower() for k in iam_keywords):
                    metrics["iam_complexity"] += 1
                    
            metrics["resource_diversity"] = len(unique_types)
            
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        
    return metrics

def process_dataset(data_dir: Path, dataset_type: str) -> pd.DataFrame:
    rows = []
    if not data_dir.exists():
        return pd.DataFrame()
        
    for model_dir in data_dir.iterdir():
        if not model_dir.is_dir(): continue
        
        for scenario_dir in model_dir.iterdir():
            if not scenario_dir.is_dir(): continue
            
            tool = "Unknown"
            if list(scenario_dir.glob("*.tf")): tool = "Terraform"
            elif list(scenario_dir.glob("*.yaml")): tool = "CloudFormation/K8s"
            elif list(scenario_dir.glob("*.json")): tool = "ARM"
            
            for file_path in scenario_dir.iterdir():
                if file_path.suffix in [".tf", ".json", ".yaml"]:
                    metrics = extract_metrics(file_path, tool)
                    metrics.update({
                        "dataset": dataset_type,
                        "model": model_dir.name,
                        "scenario_id": scenario_dir.name,
                        "file_name": file_path.name
                    })
                    rows.append(metrics)
    return pd.DataFrame(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/generated", type=str)
    parser.add_argument("--output", default="data/structural_metrics.csv", type=str)
    args = parser.parse_args()
    
    base_dir = Path(args.data_dir)
    
    df_simple = process_dataset(base_dir / "simple", "simple")
    df_complex = process_dataset(base_dir / "complex", "complex")
    
    df_all = pd.concat([df_simple, df_complex], ignore_index=True)
    
    if not df_all.empty:
        df_all.to_csv(args.output, index=False)
        logger.info(f"Extracted metrics for {len(df_all)} files -> {args.output}")
    else:
        logger.warning("No files processed.")

if __name__ == "__main__":
    main()
