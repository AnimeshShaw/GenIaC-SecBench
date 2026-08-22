import pandas as pd
import json

df = pd.read_csv('data/human_review_template.csv')
scenarios_to_review = set(df['scenario_id'])

# Load scenario descriptions
all_scenarios = []
with open('data/scenarios.json', 'r', encoding='utf-8') as f:
    all_scenarios.extend(json.load(f))
with open('data/scenarios_complex.json', 'r', encoding='utf-8') as f:
    all_scenarios.extend(json.load(f))

scenario_dict = {s['id']: s for s in all_scenarios if 'id' in s}

with open('docs/human_review_guide.md', 'w', encoding='utf-8') as f:
    f.write('# Human Review Guide for Phase 7\n\n')
    f.write('Please review the following 20 sampled scenarios and enter your scores (1-5) and Hallucination Flag (Y/N) into data/human_review_template.csv.\n\n')
    f.write('### Rubric:\n')
    f.write('- **Architectural Coherence (1-5):** Does the scenario describe a cohesive, functional system?\n')
    f.write('- **Real-World Plausibility (1-5):** Is this something a real engineering team would build?\n')
    f.write('- **Security-Test Relevance (1-5):** Does it naturally expose meaningful security choices?\n')
    f.write('- **Hallucination Flag (Y/N):** Are there non-existent provider features or completely incorrect assumptions? (Y = hallucinated, N = valid)\n\n')
    f.write('---\n\n')
    
    for idx, row in df.iterrows():
        sid = row['scenario_id']
        comp = row['complexity']
        desc = scenario_dict.get(sid, {}).get('prompt', scenario_dict.get(sid, {}).get('description', 'Description not found.'))
        
        f.write(f'## {idx+1}. Scenario ID: {sid} ({comp})\n')
        f.write(f'**Description:**\n{desc}\n\n')

print("Created docs/human_review_guide.md")
