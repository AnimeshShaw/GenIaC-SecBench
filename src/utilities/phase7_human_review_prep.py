import pandas as pd
import numpy as np

# Load the full LLM judge scores
df = pd.read_csv('data/summary_reports/llm_judge_scores.csv')

# We want a representative sample of 20 scenarios (20% of the dataset)
# We will stratify by 'complexity' and whether it was flagged as a hallucination to ensure edge cases are reviewed

# Create a stratification key
df['strat_key'] = df['complexity'] + "_" + df['hallucination_flag'].astype(str)

# Sample 20 items proportionally based on the stratification key
# Using a fixed random state for reproducibility
sampled_df = df.groupby('strat_key', group_keys=False).apply(lambda x: x.sample(n=max(1, int(np.round(20 * len(x) / len(df)))), random_state=42))

# In case rounding gives us slightly more/less than 20, let's adjust (usually it's close enough, let's check size)
if len(sampled_df) > 20:
    sampled_df = sampled_df.sample(n=20, random_state=42)
elif len(sampled_df) < 20:
    remaining = df.loc[~df.index.isin(sampled_df.index)].sample(n=20-len(sampled_df), random_state=42)
    sampled_df = pd.concat([sampled_df, remaining])

# Sort for readability
sampled_df = sampled_df.sort_values(by=['complexity', 'scenario_id'])

# Create empty columns for human review
sampled_df['human_architectural_coherence'] = ''
sampled_df['human_real_world_plausibility'] = ''
sampled_df['human_security_test_relevance'] = ''
sampled_df['human_hallucination_flag'] = ''

# Select columns to output in the template
# We will include the LLM's scores so the reviewer can do a blind review? 
# Wait, for Cohen's Kappa, the human should IDEALLY be blind to the LLM's score to avoid bias.
# Let's hide the LLM scores in the template, only keeping scenario_id and complexity.
output_cols = [
    'scenario_id', 
    'complexity',
    'human_architectural_coherence',
    'human_real_world_plausibility',
    'human_security_test_relevance',
    'human_hallucination_flag'
]

template_df = sampled_df[output_cols]
template_df.to_csv('data/human_review_template.csv', index=False)

# Also save an answer key so we can calculate Kappa later
answer_key_cols = [
    'scenario_id',
    'architectural_coherence',
    'real_world_plausibility',
    'security_test_relevance',
    'hallucination_flag'
]
sampled_df[answer_key_cols].to_csv('data/human_review_answer_key.csv', index=False)

print(f"Generated human review template with {len(template_df)} scenarios.")
