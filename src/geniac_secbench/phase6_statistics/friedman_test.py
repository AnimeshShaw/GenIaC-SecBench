import sys
import pandas as pd
import numpy as np
import scipy.stats as stats
import json
import logging
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format='%(message)s')

def holm_bonferroni(p_values):
    """Simple Holm-Bonferroni correction."""
    sorted_indices = np.argsort(p_values)
    m = len(p_values)
    adjusted_p = np.zeros(m)
    for k, i in enumerate(sorted_indices):
        adjusted_p[i] = min(1.0, p_values[i] * (m - k))
    
    # Enforce monotonicity
    for k in range(1, m):
        idx = sorted_indices[k]
        prev_idx = sorted_indices[k-1]
        adjusted_p[idx] = max(adjusted_p[prev_idx], adjusted_p[idx])
        
    return adjusted_p

def run_friedman(df, metric, stratum_name):
    # Pivot so rows = scenarios, cols = models
    pivot = df.pivot(index='scenario_id', columns='model', values=metric)
    
    # Drop rows with any NaN (scenarios where not all models have a score)
    pivot_clean = pivot.dropna()
    N = len(pivot_clean)
    k = len(pivot_clean.columns)
    
    if N < 2 or k < 2:
        return {'status': 'insufficient_data', 'N': N, 'k': k}
        
    # Run Friedman
    models = pivot_clean.columns.tolist()
    data = [pivot_clean[m].values for m in models]
    stat, p_val = stats.friedmanchisquare(*data)
    
    # Kendall's W
    w = stat / (N * (k - 1)) if k > 1 and N > 0 else 0
    
    res = {
        'status': 'success',
        'stratum': stratum_name,
        'N': int(N),
        'k': int(k),
        'statistic': float(stat),
        'p_value': float(p_val),
        'kendall_w': float(w),
        'models': models,
        'post_hoc': []
    }
    
    if p_val < 0.05:
        # Post-hoc Wilcoxon
        pairs = list(itertools.combinations(models, 2))
        p_vals = []
        for m1, m2 in pairs:
            # wilcoxon can fail if differences are all zero
            diff = pivot_clean[m1] - pivot_clean[m2]
            if np.all(diff == 0):
                p_vals.append(1.0)
            else:
                try:
                    w_stat, w_p = stats.wilcoxon(pivot_clean[m1], pivot_clean[m2])
                    p_vals.append(w_p)
                except ValueError:
                    p_vals.append(1.0)
                    
        adj_p_vals = holm_bonferroni(p_vals)
        for pair, p, adj_p in zip(pairs, p_vals, adj_p_vals):
            res['post_hoc'].append({
                'pair': pair,
                'p_value': float(p),
                'adj_p_value': float(adj_p),
                'significant': bool(adj_p < 0.05)
            })
            
    return res, pivot_clean

def run_thinking_contrasts(pivot_clean, pairs):
    results = []
    for m1, m2 in pairs:
        if m1 in pivot_clean.columns and m2 in pivot_clean.columns:
            diff = pivot_clean[m1] - pivot_clean[m2]
            if np.all(diff == 0):
                p_val = 1.0
                stat = 0.0
            else:
                try:
                    stat, p_val = stats.wilcoxon(pivot_clean[m1], pivot_clean[m2])
                except ValueError:
                    p_val = 1.0
                    stat = 0.0
            
            results.append({
                'contrast': f"{m1} vs {m2}",
                'statistic': float(stat),
                'p_value': float(p_val),
                'significant': bool(p_val < 0.05)
            })
    return results

def main():
    data_dir = PATHS.summary_reports

    df = pd.read_csv(data_dir / 'master_results.csv')
    
    metric = 'checkov_vulns_norm'
    
    results = {}
    
    # 1. Simple stratum
    df_simple = df[df['complexity'] == 'simple']
    res_simple, pivot_simple = run_friedman(df_simple, metric, 'simple')
    results['friedman_simple'] = res_simple
    
    logging.info(f"--- Friedman Test (Simple) ---")
    if res_simple['status'] == 'success':
        logging.info(f"N={res_simple['N']}, k={res_simple['k']}")
        logging.info(f"Statistic={res_simple['statistic']:.4f}, p={res_simple['p_value']:.4e}, W={res_simple['kendall_w']:.4f}")
    
    # 2. Complex stratum
    df_complex = df[df['complexity'] == 'complex']
    res_complex, pivot_complex = run_friedman(df_complex, metric, 'complex')
    results['friedman_complex'] = res_complex
    
    logging.info(f"\n--- Friedman Test (Complex) ---")
    if res_complex['status'] == 'success':
        logging.info(f"N={res_complex['N']}, k={res_complex['k']}")
        logging.info(f"Statistic={res_complex['statistic']:.4f}, p={res_complex['p_value']:.4e}, W={res_complex['kendall_w']:.4f}")
        
    # 4. Thinking contrasts
    thinking_pairs = [
        ('claude-opus-4-6', 'claude-opus-4-6-thinking'),
        ('gpt-5', 'gpt-5-thinking')
    ]
    
    logging.info(f"\n--- Thinking Contrasts (Simple) ---")
    if res_simple['status'] == 'success':
        contrasts_simple = run_thinking_contrasts(pivot_simple, thinking_pairs)
        results['thinking_contrasts_simple'] = contrasts_simple
        for c in contrasts_simple:
            logging.info(f"{c['contrast']}: stat={c['statistic']:.2f}, p={c['p_value']:.4e} {'(sig)' if c['significant'] else ''}")
            
    logging.info(f"\n--- Thinking Contrasts (Complex) ---")
    if res_complex['status'] == 'success':
        contrasts_complex = run_thinking_contrasts(pivot_complex, thinking_pairs)
        results['thinking_contrasts_complex'] = contrasts_complex
        for c in contrasts_complex:
            logging.info(f"{c['contrast']}: stat={c['statistic']:.2f}, p={c['p_value']:.4e} {'(sig)' if c['significant'] else ''}")
            
    output_path = data_dir / 'statistical_results.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    logging.info(f"\nSaved results to {output_path}")

if __name__ == '__main__':
    main()
