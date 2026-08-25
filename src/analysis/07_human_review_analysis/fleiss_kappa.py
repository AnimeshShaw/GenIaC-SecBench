import pandas as pd
import numpy as np
import os
from statsmodels.stats.inter_rater import fleiss_kappa

reviews_dir = r'data\human_reviews'
files = [f for f in os.listdir(reviews_dir) if f.endswith('.csv')]

dfs = [pd.read_csv(os.path.join(reviews_dir, f)) for f in files]

# Find common scenario IDs across all raters
common_scenarios = set(dfs[0]['scenario_id'])
for df in dfs[1:]:
    common_scenarios = common_scenarios.intersection(set(df['scenario_id']))

print(f"Loaded {len(dfs)} human reviews. Common scenarios across all raters: {len(common_scenarios)}")

# Filter dfs to only common scenarios and sort
for i in range(len(dfs)):
    dfs[i] = dfs[i][dfs[i]['scenario_id'].isin(common_scenarios)].sort_values('scenario_id').reset_index(drop=True)

def calculate_fleiss(metric_col, categories):
    n_subjects = len(dfs[0])
    k_categories = len(categories)
    agg_table = np.zeros((n_subjects, k_categories))
    
    for i in range(n_subjects):
        ratings = [str(df.loc[i, metric_col]) for df in dfs]
        for j, cat in enumerate(categories):
            agg_table[i, j] = ratings.count(str(cat))
            
    return fleiss_kappa(agg_table)

metrics = {
    'Architectural Coherence': ('human_architectural_coherence', [1, 2, 3, 4, 5]),
    'Real-World Plausibility': ('human_real_world_plausibility', [1, 2, 3, 4, 5]),
    'Security-Test Relevance': ('human_security_test_relevance', [1, 2, 3, 4, 5]),
    'Hallucination Flag': ('human_hallucination_flag', ['Y', 'N'])
}

print("\n=== MULTI-RATER AGREEMENT (FLEISS' KAPPA) ===")
print("-" * 50)
for name, (col, cats) in metrics.items():
    try:
        kappa = calculate_fleiss(col, cats)
        print(f"{name:.<30} {kappa:.4f}")
    except Exception as e:
        print(f"{name:.<30} ERROR: {e}")

