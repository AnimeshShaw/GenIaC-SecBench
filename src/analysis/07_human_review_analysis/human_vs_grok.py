import pandas as pd
import os
from sklearn.metrics import accuracy_score, cohen_kappa_score

reviews_dir = r'data\human_reviews'
files = [f for f in os.listdir(reviews_dir) if f.endswith('.csv')]
dfs = [pd.read_csv(os.path.join(reviews_dir, f)) for f in files]

common_scenarios = set(dfs[0]['scenario_id'])
for df in dfs[1:]:
    common_scenarios = common_scenarios.intersection(set(df['scenario_id']))

for i in range(len(dfs)):
    dfs[i] = dfs[i][dfs[i]['scenario_id'].isin(common_scenarios)].sort_values('scenario_id').reset_index(drop=True)

df_consensus = dfs[0][['scenario_id']].copy()

for metric in ['human_architectural_coherence', 'human_real_world_plausibility', 'human_security_test_relevance']:
    ratings = pd.concat([df[metric] for df in dfs], axis=1)
    consensus = ratings.mode(axis=1)[0].astype(int)
    df_consensus[metric + '_consensus'] = consensus

ratings_h = pd.concat([df['human_hallucination_flag'] for df in dfs], axis=1)
df_consensus['human_hallucination_flag_consensus'] = ratings_h.mode(axis=1)[0]

df_grok = pd.read_csv(r'data\human_review_answer_key.csv').sort_values('scenario_id').reset_index(drop=True)
df_eval = pd.merge(df_consensus, df_grok, on='scenario_id')

print("=== CONSENSUS HUMAN vs. GROK-4.6 (AI JUDGE) (n=18) ===")

def eval_metric(metric_name, col_human, col_ai, is_ordinal=True):
    h = df_eval[col_human].astype(str)
    a = df_eval[col_ai].astype(str)
    
    acc = accuracy_score(h, a)
    weights = 'quadratic' if is_ordinal else None
    try:
        kappa = cohen_kappa_score(h, a, weights=weights)
    except:
        kappa = 1.0 if acc == 1.0 else 0.0
        
    print(f"\nMetric: {metric_name}")
    print(f"  Exact Agreement: {acc*100:.1f}%")
    if is_ordinal:
        print(f"  Quadratic Weighted Kappa: {kappa:.3f}")
        h_num = pd.to_numeric(h)
        a_num = pd.to_numeric(a)
        within_one = (abs(h_num - a_num) <= 1).mean()
        print(f"  Within +/- 1 Point: {within_one*100:.1f}%")
    else:
        print(f"  Cohen's Kappa: {kappa:.3f}")

eval_metric('Architectural Coherence', 'human_architectural_coherence_consensus', 'architectural_coherence')
eval_metric('Real-World Plausibility', 'human_real_world_plausibility_consensus', 'real_world_plausibility')
eval_metric('Security-Test Relevance', 'human_security_test_relevance_consensus', 'security_test_relevance')
eval_metric('Hallucination Flag', 'human_hallucination_flag_consensus', 'hallucination_flag', is_ordinal=False)
