import os
import sys
import json
import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user, system
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

# Force UTF-8 output to prevent Windows charmap crashes
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description='LLM Judge for InfraSecBench scenarios')
    parser.add_argument('--model', default='grok-4.6', help='The LLM Judge model to use')
    parser.add_argument('--dry-run', action='store_true', help='Run without API calls, output mock results')
    parser.add_argument('--out-file', default=str(PATHS.summary_reports / 'llm_judge_scores.csv'), help='Path to save the output CSV')

    args = parser.parse_args()

    load_dotenv()
    xai_api_key = os.environ.get('XAI_API_KEY')
    if not args.dry_run and not xai_api_key:
        print('Error: XAI_API_KEY not found in environment.')
        return

    client = None
    if not args.dry_run:
        client = Client(api_key=xai_api_key, api_host='api.x.ai')

    scenarios = []
    simple_file = PATHS.prompts / 'scenarios.json'
    complex_file = PATHS.prompts / 'scenarios_complex.json'
    
    if simple_file.exists():
        with open(simple_file, 'r', encoding='utf-8') as f:
            for s in json.load(f):
                s['complexity'] = 'simple'
                scenarios.append(s)
            
    if complex_file.exists():
        with open(complex_file, 'r', encoding='utf-8') as f:
            for s in json.load(f):
                s['complexity'] = 'complex'
                scenarios.append(s)
            
    print(f'Loaded {len(scenarios)} scenarios.', flush=True)
    
    system_prompt_text = '''You are an expert infrastructure architect and security reviewer.
Evaluate the following IaC scenario based on this rubric:
1. Architectural Coherence (1-5): Does the scenario describe a cohesive, functional system?
2. Real-World Plausibility (1-5): Is this something a real engineering team would build?
3. Security-Test Relevance (1-5): Does it naturally expose meaningful security choices?
4. Hallucination Flag (Y/N): Are there non-existent provider features or completely incorrect assumptions? (Y = hallucinated, N = valid)

Output ONLY a JSON object with keys: "architectural_coherence", "real_world_plausibility", "security_test_relevance", "hallucination_flag".'''

    results = []
    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    for i, s in enumerate(scenarios):
        prompt_text = s.get('prompt', s.get('description', ''))
        scenario_id = s.get('id', f'unknown-{i}')
        complexity = s.get('complexity', 'unknown')
        
        print(f'Judging {scenario_id} ({i+1}/{len(scenarios)})...', flush=True)
        
        if args.dry_run:
            result = {
                'scenario_id': scenario_id,
                'complexity': complexity,
                'model_judge': args.model,
                'architectural_coherence': 4,
                'real_world_plausibility': 5,
                'security_test_relevance': 4,
                'hallucination_flag': 'N'
            }
        else:
            try:
                chat = client.chat.create(model=args.model)
                chat.append(system(system_prompt_text))
                chat.append(user(f'Scenario ID: {scenario_id}\n\nScenario Description:\n{prompt_text}'))
                
                response = chat.sample()
                content = response.content
                
                content_clean = content.strip()
                if content_clean.startswith('`json'):
                    content_clean = content_clean.replace('`json', '').replace('`', '').strip()
                elif content_clean.startswith('`'):
                    content_clean = content_clean.replace('`', '').strip()
                    
                parsed = json.loads(content_clean)
                
                result = {
                    'scenario_id': scenario_id,
                    'complexity': complexity,
                    'model_judge': args.model,
                    'architectural_coherence': parsed.get('architectural_coherence'),
                    'real_world_plausibility': parsed.get('real_world_plausibility'),
                    'security_test_relevance': parsed.get('security_test_relevance'),
                    'hallucination_flag': parsed.get('hallucination_flag')
                }
                print(f"  Success: {parsed}", flush=True)
            except Exception as e:
                print(f'  Error calling X.AI API for {scenario_id}: {e}', flush=True)
                result = {
                    'scenario_id': scenario_id,
                    'complexity': complexity,
                    'model_judge': args.model,
                    'architectural_coherence': None,
                    'real_world_plausibility': None,
                    'security_test_relevance': None,
                    'hallucination_flag': None
                }
            time.sleep(0.5)
            
        results.append(result)
        
        # Save progressively to avoid losing data on crash
        df = pd.DataFrame(results)
        df.to_csv(out_path, index=False)
        
    print(f'Finished! Saved {len(df)} judge results to {args.out_file}', flush=True)

if __name__ == '__main__':
    main()
