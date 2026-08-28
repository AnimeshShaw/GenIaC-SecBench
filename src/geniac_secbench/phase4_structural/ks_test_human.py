import sys
import pandas as pd
import json
from scipy.stats import ks_2samp
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    llm_metrics_path = PATHS.summary_reports / 'structural_metrics.csv'
    human_metrics_path = PATHS.summary_reports / 'human_reference_metrics.csv'
    
    if not llm_metrics_path.exists() or not human_metrics_path.exists():
        logger.error("Missing metrics files!")
        return
        
    df_llm = pd.read_csv(llm_metrics_path)
    df_human = pd.read_csv(human_metrics_path)
    
    models = df_llm['model'].unique()
    metrics = ['ast_depth', 'resource_count', 'resource_diversity']
    
    results = []
    
    logger.info(f"Loaded {len(df_human)} human templates and {len(df_llm)} LLM outputs.")
    
    for model in models:
        df_model = df_llm[df_llm['model'] == model]
        
        for metric in metrics:
            model_dist = df_model[metric].dropna()
            human_dist = df_human[metric].dropna()
            
            if len(model_dist) > 0 and len(human_dist) > 0:
                stat, pval = ks_2samp(model_dist, human_dist)
                
                results.append({
                    'model': model,
                    'metric': metric,
                    'ks_statistic': stat,
                    'p_value': pval,
                    'model_mean': model_dist.mean(),
                    'human_mean': human_dist.mean()
                })
                
    out_df = pd.DataFrame(results)
    out_csv = PATHS.summary_reports / 'ks_test_human_baseline.csv'
    out_df.to_csv(out_csv, index=False)
    
    with open(PATHS.summary_reports / 'ks_test_human_baseline.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    logger.info(f"KS-Test against human baseline completed. Saved to {out_csv}")

if __name__ == '__main__':
    main()
