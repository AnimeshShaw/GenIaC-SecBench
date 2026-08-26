# GenIaC-SecBench -- Results

> Generated from `data/summary_reports/` by `geniac_secbench.phase8_reporting.findings_report`. Do not hand-edit: regenerate after any pipeline run.

## 1. Corpus and coverage

- **1,132** (scenario x model) observations, one per generated file.
- **12** model arms, **100** distinct scenarios.

| model | simple | complex | total |
|---|---:|---:|---:|
| `claude-opus-4-6` | 60 | 40 | 100 |
| `claude-opus-4-6-cot`  *(incomplete)* | 8 | 40 | 48 |
| `claude-opus-4-6-thinking`  *(incomplete)* | 60 | 29 | 89 |
| `claude-sonnet-4-6`  *(incomplete)* | 60 | 35 | 95 |
| `gemini-3.1-pro` | 60 | 40 | 100 |
| `gemini-3.7-flash` | 60 | 40 | 100 |
| `gpt-4o` | 60 | 40 | 100 |
| `gpt-5` | 60 | 40 | 100 |
| `gpt-5-thinking` | 60 | 40 | 100 |
| `llama3` | 60 | 40 | 100 |
| `mistral` | 60 | 40 | 100 |
| `phi3` | 60 | 40 | 100 |

**Scanner coverage**

| scanner | covered | total | % |
|---|---:|---:|---:|
| checkov | 1132 | 1132 | 100.0% |
| kics | 1132 | 1132 | 100.0% |
| trivy | 1132 | 1132 | 100.0% |

## 2. Vulnerability density by model

Density = total findings across all three scanners / resource count. Resource count is the AST-derived value; rows with zero resources carry no exposure and are excluded from the density mean.

### simple stratum

| model | n | mean resources | mean findings | **density** |
|---|---:|---:|---:|---:|
| `claude-opus-4-6-cot` | 8 | 9.38 | 27.00 | **2.89** |
| `gpt-5-thinking` | 60 | 3.82 | 15.43 | **8.44** |
| `claude-sonnet-4-6` | 60 | 4.78 | 18.25 | **8.84** |
| `gpt-5` | 60 | 3.47 | 16.13 | **9.45** |
| `gemini-3.7-flash` | 60 | 3.28 | 16.43 | **9.50** |
| `claude-opus-4-6-thinking` | 60 | 3.87 | 19.23 | **10.53** |
| `mistral` | 60 | 1.97 | 15.28 | **10.98** |
| `gemini-3.1-pro` | 60 | 2.93 | 18.38 | **11.24** |
| `llama3` | 60 | 2.10 | 14.82 | **11.29** |
| `claude-opus-4-6` | 60 | 3.28 | 20.18 | **12.12** |
| `gpt-4o` | 60 | 2.25 | 18.15 | **12.30** |
| `phi3` | 60 | 0.00 | 0.00 | **--** |

### complex stratum

| model | n | mean resources | mean findings | **density** |
|---|---:|---:|---:|---:|
| `claude-opus-4-6-cot` | 40 | 69.95 | 90.10 | **1.90** |
| `phi3` | 40 | 0.07 | 0.33 | **4.33** |
| `claude-opus-4-6` | 40 | 61.30 | 98.03 | **4.38** |
| `llama3` | 40 | 7.03 | 21.32 | **4.61** |
| `gemini-3.7-flash` | 40 | 33.10 | 55.58 | **4.94** |
| `claude-opus-4-6-thinking` | 29 | 68.00 | 104.59 | **5.05** |
| `gpt-5` | 40 | 40.10 | 75.65 | **5.49** |
| `gemini-3.1-pro` | 40 | 28.65 | 58.05 | **5.55** |
| `gpt-5-thinking` | 40 | 44.77 | 58.60 | **5.65** |
| `claude-sonnet-4-6` | 35 | 85.20 | 64.20 | **5.82** |
| `gpt-4o` | 40 | 12.40 | 38.58 | **6.64** |
| `mistral` | 40 | 4.75 | 26.05 | **8.49** |

## 3. Schema validity (deployability)

| model | valid | total | pass rate |
|---|---:|---:|---:|
| `claude-opus-4-6-thinking` | 31 | 89 | 34.8% |
| `gemini-3.1-pro` | 33 | 100 | 33.0% |
| `gemini-3.7-flash` | 32 | 100 | 32.0% |
| `claude-opus-4-6` | 32 | 100 | 32.0% |
| `claude-sonnet-4-6` | 30 | 95 | 31.6% |
| `gpt-4o` | 30 | 100 | 30.0% |
| `gpt-5` | 29 | 100 | 29.0% |
| `gpt-5-thinking` | 26 | 100 | 26.0% |
| `mistral` | 9 | 100 | 9.0% |
| `claude-opus-4-6-cot` | 4 | 48 | 8.3% |
| `llama3` | 6 | 100 | 6.0% |
| `phi3` | 5 | 100 | 5.0% |

## 4. Do the models differ? (omnibus)

Metric: `total_vulns_norm`. Primary test: **Skillings-Mack (handles incomplete blocks)**.

| stratum | Skillings-Mack chi2 | df | p | blocks used | complete-case Friedman N | blocks discarded |
|---|---:|---:|---:|---:|---:|---:|
| simple | 64.10 | 10 | 6.01e-10 | 60 | 0 | 60 |
| complex | 78.36 | 11 | 3.06e-12 | 40 | 0 | 40 |

> **Note.** Complete-case Friedman retains **zero** blocks in at least one stratum: with this many arms and uneven coverage, no scenario has every model present. The classical test is not merely weaker here, it is uncomputable -- which is why Skillings-Mack is the primary test.

## 5. Reasoning-mode contrasts

Paired within-model comparisons -- same model, same scenarios, one variable toggled. `-cot` is a prompt-engineered chain-of-thought suffix; `-thinking` is the vendor's reasoning feature. They are distinct conditions (see THREATS_TO_VALIDITY.md 1.1).

| contrast | stratum | n | mean before | mean after | change | p |
|---|---|---:|---:|---:|---:|---:|
| standard vs extended-thinking | simple | 60 | 12.124 | 10.526 | -13.2% | 0.0122 **\*** |
| standard vs extended-thinking | complex | 24 | 5.980 | 5.236 | -12.4% | 0.1780 |
| standard vs prompt-CoT | simple | 8 | 2.973 | 2.892 | -2.7% | 1.0000 |
| standard vs prompt-CoT | complex | 33 | 2.217 | 2.110 | -4.8% | 0.7506 |
| prompt-CoT vs extended-thinking | simple | 8 | 2.892 | 2.636 | -8.9% | 0.1250 |
| prompt-CoT vs extended-thinking | complex | 24 | 2.643 | 2.224 | -15.9% | 0.1434 |
| standard vs reasoning_effort=high | simple | 58 | 9.393 | 8.439 | -10.2% | 0.1527 |
| standard vs reasoning_effort=high | complex | 29 | 6.199 | 6.320 | +2.0% | 0.7007 |

`*` significant at alpha=0.05.

## 6. Negative binomial rate model

- Reference model: `claude-opus-4-6`
- Exposure offset: `log(resource_count)` -- coefficients are rate ratios **per resource**
- Overdispersion variance/mean = **133.5** (Poisson requires 1, so NB2 is required)
- Rows fitted 938 of 1132; 194 excluded for zero exposure
- Outcome filtering: NONE. All observations retained, including zero-count rows and zero-count scenarios (v1 dropped these).

| model | IRR | 95% CI | p |
|---|---:|---|---:|
| `claude-opus-4-6-cot` | 0.73 | [0.54, 0.99] | 0.0417 **\*** |
| `claude-opus-4-6-thinking` | 0.90 | [0.72, 1.12] | 0.3387 |
| `gemini-3.7-flash` | 1.19 | [0.98, 1.44] | 0.0854 |
| `gpt-5` | 1.23 | [1.02, 1.47] | 0.0278 **\*** |
| `gpt-5-thinking` | 1.24 | [1.01, 1.53] | 0.0427 **\*** |
| `claude-sonnet-4-6` | 1.25 | [0.59, 2.65] | 0.5620 |
| `gemini-3.1-pro` | 1.30 | [1.15, 1.48] | 2.39e-05 **\*** |
| `mistral` | 1.33 | [0.21, 8.24] | 0.7611 |
| `llama3` | 1.46 | [0.97, 2.21] | 0.0692 |
| `gpt-4o` | 1.58 | [0.73, 3.44] | 0.2462 |
| `phi3` | 4.66 | [2.97, 7.31] | 2.40e-11 **\*** |

## 8. Structural divergence from human-authored IaC

Two-sample Kolmogorov-Smirnov, each model against the 634-file human reference corpus.

```
                   model             metric  ks_statistic       p_value  model_mean  human_mean
         claude-opus-4-6          ast_depth      0.259054  1.330522e-05   10.400000    8.940063
         claude-opus-4-6     resource_count      0.291609  5.337639e-07   26.490000    5.309148
         claude-opus-4-6 resource_diversity      0.267918  5.759369e-06   11.940000    3.787066
     claude-opus-4-6-cot          ast_depth      0.607387  3.329034e-16   13.250000    8.940063
     claude-opus-4-6-cot     resource_count      0.724763  4.847263e-24   59.854167    5.309148
     claude-opus-4-6-cot resource_diversity      0.698015  4.901955e-22   25.395833    3.787066
claude-opus-4-6-thinking          ast_depth      0.236132  2.577421e-04   10.146067    8.940063
claude-opus-4-6-thinking     resource_count      0.244036  1.401190e-04   24.764045    5.309148
claude-opus-4-6-thinking resource_diversity      0.228264  4.643560e-04   11.033708    3.787066
       claude-sonnet-4-6          ast_depth      0.309580  1.595034e-07   10.884211    8.940063
       claude-sonnet-4-6     resource_count      0.286336  1.724739e-06   34.410526    5.309148
       claude-sonnet-4-6 resource_diversity      0.291582  1.023701e-06   14.694737    3.787066
          gemini-3.1-pro          ast_depth      0.219054  4.005370e-04   10.100000    8.940063
          gemini-3.1-pro     resource_count      0.246404  4.159699e-05   13.220000    5.309148
          gemini-3.1-pro resource_diversity      0.230662  1.586527e-04    9.040000    3.787066
        gemini-3.7-flash          ast_depth      0.259054  1.330522e-05   10.480000    8.940063
        gemini-3.7-flash     resource_count      0.274795  2.952335e-06   15.210000    5.309148
        gemini-3.7-flash resource_diversity      0.260662  1.148374e-05    9.610000    3.787066
                  gpt-4o          ast_depth      0.189054  3.506399e-03    9.280000    8.940063
                  gpt-4o     resource_count      0.160189  2.083846e-02    6.310000    5.309148
                  gpt-4o resource_diversity      0.160662  2.027759e-02    5.030000    3.787066
                   gpt-5          ast_depth      0.259054  1.330522e-05   10.030000    8.940063
                   gpt-5     resource_count      0.264763  7.779482e-06   18.120000    5.309148
                   gpt-5 resource_diversity      0.246909  3.977011e-05    9.660000    3.787066
          gpt-5-thinking          ast_depth      0.229054  1.807075e-04    9.580000    8.940063
          gpt-5-thinking     resource_count      0.251073  2.748186e-05   20.200000    5.309148
          gpt-5-thinking resource_diversity      0.234448  1.167830e-04    9.920000    3.787066
                  llama3          ast_depth      0.190000  3.294205e-03    7.210000    8.940063
                  llama3     resource_count      0.260000  1.217459e-05    4.070000    5.309148
                  llama3 resource_diversity      0.253691  2.171638e-05    3.490000    3.787066
                 mistral
```

## 7. Human evaluation and LLM-judge agreement

```json
{
  "fleiss_kappa_inter_human": {
    "n_raters": 3,
    "n_subjects": 18,
    "architectural_coherence": 0.2098,
    "real_world_plausibility": 0.391,
    "security_test_relevance": 0.0588,
    "hallucination_flag": 0.2663
  },
  "consensus_vs_grok_4_6": {
    "architectural_coherence": {
      "exact_agreement_pct": 38.9,
      "within_one_point_pct": 72.2,
      "quadratic_weighted_kappa": 0.361
    },
    "real_world_plausibility": {
      "exact_agreement_pct": 66.7,
      "within_one_point_pct": 100.0,
      "quadratic_weighted_kappa": 0.8
    },
    "security_test_relevance": {
      "exact_agreement_pct": 61.1,
      "within_one_point_pct": 83.3,
      "quadratic_weighted_kappa": 0.367
    },
    "hallucination_flag": {
      "exact_agreement_pct": 94.4,
      "cohens_kappa": 0.64
    }
  }
}
```

## 9. Generation cost and reasoning-token usage

- Reasoning tokens per generation: median **19**, max **1988**, over 137 logged generations.
- Measured against a 16,000-token budget under the fixed-budget configuration: `budget_tokens` is a ceiling the model may underspend, not a target. A small reasoning effect on this task class must not be read as "reasoning does not help" in general.

- Completion tokens logged: **1,000,066** total, median **1,222** per generation.
