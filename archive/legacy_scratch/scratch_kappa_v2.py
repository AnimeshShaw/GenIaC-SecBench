import pandas as pd
from sklearn.metrics import cohen_kappa_score, accuracy_score
import sys

manickam_file = r'data\human_reviews\human_review_manickam.csv'
praj_file = r'data\human_reviews\human_review_praj.csv'
grok_file = r'data\human_review_answer_key.csv'

df_manickam = pd.read_csv(manickam_file)
df_grok = pd.read_csv(grok_file)
df_praj = pd.read_csv(praj_file)

# We will calculate two sets of agreements:
# 1. Manickam vs Grok (AI Judge)
# 2. Manickam vs Prajjuwal (Human Inter-Rater Reliability)

# Merge Manickam and Grok
df_mg = pd.merge(df_manickam, df_grok, on='scenario_id', suffixes=('_human', '_ai'))

# Merge Manickam and Prajjuwal
df_mp = pd.merge(df_manickam, df_praj, on='scenario_id', suffixes=('_m', '_p'))

def eval_metric(metric_name, col1, col2, df, is_ordinal=True, print_details=True):
    v1 = df[col1].astype(str)
    v2 = df[col2].astype(str)
    
    acc = accuracy_score(v1, v2)
    weights = 'quadratic' if is_ordinal else None
    try:
        kappa = cohen_kappa_score(v1, v2, weights=weights)
    except:
        kappa = 1.0 if acc == 1.0 else 0.0
        
    if print_details:
        print(f"\nMetric: {metric_name}")
        print(f"  Exact Agreement: {acc*100:.1f}%")
        if is_ordinal:
            print(f"  Quadratic Weighted Kappa: {kappa:.3f}")
            v1_num = pd.to_numeric(v1)
            v2_num = pd.to_numeric(v2)
            within_one = (abs(v1_num - v2_num) <= 1).mean()
            print(f"  Within +/- 1 Point: {within_one*100:.1f}%")
        else:
            print(f"  Cohen's Kappa: {kappa:.3f}")

print("=== PART 1: Manickam vs. Grok-4.6 (AI Judge) ===")
eval_metric('Architectural Coherence', 'human_architectural_coherence', 'architectural_coherence', df_mg)
eval_metric('Real-World Plausibility', 'human_real_world_plausibility', 'real_world_plausibility', df_mg)
eval_metric('Security-Test Relevance', 'human_security_test_relevance', 'security_test_relevance', df_mg)
eval_metric('Hallucination Flag', 'human_hallucination_flag', 'hallucination_flag', df_mg, is_ordinal=False)

print("\n\n=== PART 2: INTER-HUMAN RELIABILITY (Manickam vs. Prajjuwal) ===")
eval_metric('Architectural Coherence', 'human_architectural_coherence_m', 'human_architectural_coherence_p', df_mp)
eval_metric('Real-World Plausibility', 'human_real_world_plausibility_m', 'human_real_world_plausibility_p', df_mp)
eval_metric('Security-Test Relevance', 'human_security_test_relevance_m', 'human_security_test_relevance_p', df_mp)
eval_metric('Hallucination Flag', 'human_hallucination_flag_m', 'human_hallucination_flag_p', df_mp, is_ordinal=False)

