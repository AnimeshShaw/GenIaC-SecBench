import pandas as pd
from sklearn.metrics import cohen_kappa_score, accuracy_score
import sys

praj_file = 'data/human_reviews/human_review_praj.csv'
grok_file = 'data/human_review_answer_key.csv'

try:
    df_praj = pd.read_csv(praj_file)
    df_grok = pd.read_csv(grok_file)
except Exception as e:
    print(f"Error loading files: {e}")
    sys.exit(1)

# Merge on scenario_id
df = pd.merge(df_praj, df_grok, on='scenario_id', suffixes=('_human', '_ai'))

if len(df) == 0:
    print("No matching scenarios found!")
    sys.exit(1)

print(f"--- Early Validation Results (n={len(df)}) ---")
print(f"Reviewer: {df['reviewer_name'].iloc[0]}")

def evaluate_metric(metric_name, col_human, col_ai, is_ordinal=True):
    h = df[col_human].astype(str)
    a = df[col_ai].astype(str)
    acc = accuracy_score(h, a)
    
    weights = 'quadratic' if is_ordinal else None
    
    # Handle case where all values might be exactly the same
    try:
        kappa = cohen_kappa_score(h, a, weights=weights)
    except:
        kappa = 1.0 if acc == 1.0 else 0.0
        
    print(f"\nMetric: {metric_name}")
    print(f"  Exact Agreement (Accuracy): {acc*100:.1f}%")
    if is_ordinal:
        print(f"  Quadratic Weighted Kappa:   {kappa:.3f}")
    else:
        print(f"  Cohen's Kappa:              {kappa:.3f}")
        
    # Also calculate "Within 1 point" agreement for ordinal
    if is_ordinal:
        h_num = pd.to_numeric(h)
        a_num = pd.to_numeric(a)
        within_one = (abs(h_num - a_num) <= 1).mean()
        print(f"  Within +/- 1 Point:         {within_one*100:.1f}%")

evaluate_metric('Architectural Coherence', 'human_architectural_coherence', 'architectural_coherence', is_ordinal=True)
evaluate_metric('Real-World Plausibility', 'human_real_world_plausibility', 'real_world_plausibility', is_ordinal=True)
evaluate_metric('Security-Test Relevance', 'human_security_test_relevance', 'security_test_relevance', is_ordinal=True)
evaluate_metric('Hallucination Flag', 'human_hallucination_flag', 'hallucination_flag', is_ordinal=False)

