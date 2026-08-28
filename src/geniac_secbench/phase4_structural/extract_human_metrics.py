import os
import sys
import json
import logging
from pathlib import Path
import pandas as pd
import hcl2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# CloudFormation custom tag constructor
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
        return max((get_ast_depth(v, current_depth + 1) for v in obj), default=current_depth)
    return current_depth

def extract_terraform_metrics(parsed_dict):
    ast_depth = get_ast_depth(parsed_dict)
    resource_count = 0
    unique_resource_types = set()
    
    # Terraform HCL parses into a list of dicts. We look for 'resource' keys.
    if isinstance(parsed_dict, dict) and 'resource' in parsed_dict:
        for res_type_dict in parsed_dict['resource']:
            for res_type, res_blocks in res_type_dict.items():
                unique_resource_types.add(res_type)
                resource_count += len(res_blocks)
                
    return ast_depth, resource_count, len(unique_resource_types)

def extract_cfn_k8s_metrics(parsed_dict):
    ast_depth = get_ast_depth(parsed_dict)
    resource_count = 0
    unique_resource_types = set()
    
    # Check if CloudFormation
    if 'Resources' in parsed_dict and isinstance(parsed_dict['Resources'], dict):
        resource_count = len(parsed_dict['Resources'])
        for res_name, res_props in parsed_dict['Resources'].items():
            if isinstance(res_props, dict) and 'Type' in res_props:
                unique_resource_types.add(res_props['Type'])
    # Check if Kubernetes
    elif 'kind' in parsed_dict and 'apiVersion' in parsed_dict:
        resource_count = 1
        unique_resource_types.add(parsed_dict['kind'])
    # Check if K8s List
    elif 'items' in parsed_dict and isinstance(parsed_dict['items'], list):
        resource_count = len(parsed_dict['items'])
        for item in parsed_dict['items']:
            if isinstance(item, dict) and 'kind' in item:
                unique_resource_types.add(item['kind'])
                
    return ast_depth, resource_count, len(unique_resource_types)

def is_valid_iac_file(file_path):
    ext = file_path.suffix.lower()
    if ext == '.tf':
        return True
    if ext in ['.yaml', '.yml', '.json']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000) # Read first 2KB for heuristics
                if 'AWSTemplateFormatVersion' in content or '"Resources"' in content or 'Resources:' in content or 'apiVersion:' in content or '"apiVersion"' in content:
                    return True
        except:
            pass
    return False

def main():
    dataset_dir = PATHS.human_reference_dataset
    results = []
    
    logger.info(f"Walking {dataset_dir} for human IaC files...")
    
    processed_count = 0
    error_count = 0
    
    for root, _, files in os.walk(dataset_dir):
        for file in files:
            path = Path(root) / file
            
            if not is_valid_iac_file(path):
                continue
                
            ext = path.suffix.lower()
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    if ext == '.tf':
                        parsed = hcl2.load(f)
                        depth, count, div = extract_terraform_metrics(parsed)
                    elif ext == '.json':
                        parsed = json.load(f)
                        depth, count, div = extract_cfn_k8s_metrics(parsed)
                    elif ext in ['.yaml', '.yml']:
                        parsed = yaml.safe_load(f)
                        if not isinstance(parsed, dict):
                            continue # Skip empty or string-only yamls
                        depth, count, div = extract_cfn_k8s_metrics(parsed)
                    else:
                        continue
                        
                # Only keep files that actually have resources
                if count > 0:
                    results.append({
                        'file_path': str(path),
                        'format': ext.strip('.'),
                        'ast_depth': depth,
                        'resource_count': count,
                        'resource_diversity': div
                    })
                    processed_count += 1
            except Exception as e:
                # Silently catch parsing errors (human repos contain broken stuff sometimes)
                error_count += 1
                
    logger.info(f"Successfully extracted metrics from {processed_count} human IaC files.")
    logger.info(f"Encountered parsing errors on {error_count} files (ignored).")
    
    out_path = PATHS.summary_reports / 'human_reference_metrics.csv'
    df = pd.DataFrame(results)
    df.to_csv(out_path, index=False)
    logger.info(f"Saved human metrics to {out_path}")

if __name__ == '__main__':
    main()
