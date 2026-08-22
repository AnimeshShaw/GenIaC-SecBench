import os
import json
import argparse
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def plot_ecdf(df, metric, output_dir):
    plt.figure(figsize=(10, 6))
    sns.ecdfplot(data=df, x=metric, hue="model")
    plt.title(f"ECDF of {metric} by Model")
    plt.tight_layout()
    plt.savefig(output_dir / f"ks_ecdf_{metric}.png")
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-csv", default="data/structural_metrics.csv")
    parser.add_argument("--reference-dir", type=str, help="Directory containing reference dataset")
    parser.add_argument("--cross-model", action="store_true", default=True, help="Compare each model vs all others")
    parser.add_argument("--out-dir", default="data")
    
    args = parser.parse_args()
    if args.reference_dir:
        args.cross_model = False
        
    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    
    df = pd.read_csv(args.metrics_csv)
    metrics = ["resource_count", "resource_diversity", "ast_depth", "iam_complexity"]
    
    results = []
    
    if args.reference_dir:
        try:
            from src.phase4_structural.extract_metrics import process_dataset
        except ImportError:
            import sys
            sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
            from src.phase4_structural.extract_metrics import process_dataset
            
        ref_df = process_dataset(Path(args.reference_dir), "reference")
        # For each model, compare to reference
        for model in df["model"].unique():
            model_df = df[df["model"] == model]
            for metric in metrics:
                stat, pval = stats.ks_2samp(model_df[metric], ref_df[metric])
                results.append({
                    "comparison": "model_vs_reference",
                    "model": model,
                    "metric": metric,
                    "ks_stat": stat,
                    "p_value": pval
                })
    else:
        # Cross model
        models = df["model"].unique()
        for model in models:
            model_df = df[df["model"] == model]
            other_df = df[df["model"] != model]
            for metric in metrics:
                stat, pval = stats.ks_2samp(model_df[metric], other_df[metric])
                results.append({
                    "comparison": "model_vs_others",
                    "model": model,
                    "metric": metric,
                    "ks_stat": stat,
                    "p_value": pval
                })
        
        # Plot ECDFs
        for metric in metrics:
            plot_ecdf(df, metric, fig_dir)
            
    # Simple vs Complex within each model
    for model in df["model"].unique():
        model_df = df[df["model"] == model]
        simple_df = model_df[model_df["dataset"] == "simple"]
        complex_df = model_df[model_df["dataset"] == "complex"]
        
        if not simple_df.empty and not complex_df.empty:
            for metric in metrics:
                stat, pval = stats.ks_2samp(simple_df[metric], complex_df[metric])
                results.append({
                    "comparison": "simple_vs_complex",
                    "model": model,
                    "metric": metric,
                    "ks_stat": stat,
                    "p_value": pval
                })

    # Save to JSON
    with open(out_dir / "ks_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    # Print table
    print(f"{'Comparison':<20} | {'Model':<25} | {'Metric':<20} | {'KS Stat':<10} | {'P-Value':<10}")
    print("-" * 95)
    for r in results:
        print(f"{r['comparison']:<20} | {r['model']:<25} | {r['metric']:<20} | {r['ks_stat']:<10.4f} | {r['p_value']:<10.4e}")

if __name__ == '__main__':
    main()
