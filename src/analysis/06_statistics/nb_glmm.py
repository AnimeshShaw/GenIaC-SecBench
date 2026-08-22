import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.genmod.families import Poisson
from statsmodels.genmod.cov_struct import Exchangeable
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')

def safe_float(val):
    try:
        if np.isnan(val):
            return "NaN"
        if np.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return float(val)
    except:
        return str(val)

def main():
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / 'data'
    
    df = pd.read_csv(data_dir / 'master_results.csv')
    
    df['total_vulns'] = df['checkov_vulns'] + df['trivy_vulns'] + df['kics_vulns']
    
    df['model_cat'] = df['model'].astype(str)
    df['complexity_cat'] = df['complexity'].astype(str)
    
    df_clean = df.dropna(subset=['total_vulns', 'model_cat', 'complexity_cat', 'scenario_id'])
    df_clean['scenario_id'] = df_clean['scenario_id'].astype(str)
    
    model_sums = df_clean.groupby('model_cat')['total_vulns'].sum()
    valid_models = model_sums[model_sums > 0].index
    df_clean = df_clean[df_clean['model_cat'].isin(valid_models)]
    
    scenario_sums = df_clean.groupby('scenario_id')['total_vulns'].sum()
    valid_scenarios = scenario_sums[scenario_sums > 0].index
    df_clean = df_clean[df_clean['scenario_id'].isin(valid_scenarios)]
    
    df_clean = df_clean.copy()
    
    df_clean['model_cat'] = pd.Categorical(df_clean['model_cat'])
    df_clean['complexity_cat'] = pd.Categorical(df_clean['complexity_cat'])
    
    try:
        fam = Poisson()
        cov_struct = Exchangeable()
        
        model = smf.gee('total_vulns ~ C(model_cat) * C(complexity_cat)', 
                        data=df_clean, 
                        groups=df_clean['scenario_id'], 
                        family=fam, 
                        cov_struct=cov_struct)
        result = model.fit()
        
        logging.info(result.summary())
        
        params = result.params
        conf = result.conf_int()
        pvalues = result.pvalues
        
        results_out = {
            'converged': bool(result.converged),
            'coefficients': {}
        }
        
        for name in params.index:
            beta = params[name]
            irr = np.exp(beta)
            ci_lower = np.exp(conf.loc[name, 0])
            ci_upper = np.exp(conf.loc[name, 1])
            pval = pvalues[name]
            
            results_out['coefficients'][name] = {
                'beta': safe_float(beta),
                'irr': safe_float(irr),
                'ci_lower': safe_float(ci_lower),
                'ci_upper': safe_float(ci_upper),
                'p_value': safe_float(pval)
            }
            
        output_path = data_dir / 'nb_glmm_results.json'
        with open(output_path, 'w') as f:
            json.dump(results_out, f, indent=2)
        logging.info(f"\nSaved GLMM results to {output_path}")
        
    except Exception as e:
        logging.error(f"Error fitting GEE model: {e}")

if __name__ == '__main__':
    main()
