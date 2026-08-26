# GenIaC-SecBench -- Results

> Generated from `data/summary_reports/` by `geniac_secbench.phase8_reporting.findings_report`. Do not hand-edit: regenerate after any pipeline run.

## 1. Corpus and coverage

- **1,196** (scenario x model) observations, one per generated file.
- **12** model arms, **100** distinct scenarios.

| model | simple | complex | total |
|---|---:|---:|---:|
| `claude-opus-4-6` | 60 | 40 | 100 |
| `claude-opus-4-6-cot` | 60 | 40 | 100 |
| `claude-opus-4-6-thinking`  *(incomplete)* | 60 | 39 | 99 |
| `claude-sonnet-4-6`  *(incomplete)* | 60 | 37 | 97 |
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
| checkov | 1196 | 1196 | 100.0% |
| kics | 1196 | 1196 | 100.0% |
| trivy | 1196 | 1196 | 100.0% |

## 2. Vulnerability density by model

Density = total findings across all three scanners / resource count. Resource count is the AST-derived value; rows with zero resources carry no exposure and are excluded from the density mean.

### simple stratum

| model | n | mean resources | mean findings | **density** |
|---|---:|---:|---:|---:|
| `gpt-5-thinking` | 60 | 3.82 | 15.43 | **8.44** |
| `claude-sonnet-4-6` | 60 | 4.78 | 18.25 | **8.84** |
| `gpt-5` | 60 | 3.47 | 16.13 | **9.45** |
| `gemini-3.7-flash` | 60 | 3.28 | 16.43 | **9.50** |
| `claude-opus-4-6-thinking` | 60 | 3.87 | 19.23 | **10.53** |
| `mistral` | 60 | 1.97 | 15.28 | **10.98** |
| `gemini-3.1-pro` | 60 | 2.93 | 18.38 | **11.24** |
| `llama3` | 60 | 2.10 | 14.82 | **11.29** |
| `claude-opus-4-6-cot` | 60 | 3.43 | 19.85 | **11.97** |
| `claude-opus-4-6` | 60 | 3.28 | 20.18 | **12.12** |
| `gpt-4o` | 60 | 2.25 | 18.15 | **12.30** |
| `phi3` | 60 | 0.00 | 0.00 | **--** |

### complex stratum

| model | n | mean resources | mean findings | **density** |
|---|---:|---:|---:|---:|
| `claude-opus-4-6-cot` | 40 | 69.95 | 90.10 | **1.90** |
| `claude-opus-4-6-thinking` | 39 | 63.41 | 84.31 | **4.06** |
| `phi3` | 40 | 0.07 | 0.33 | **4.33** |
| `claude-opus-4-6` | 40 | 61.30 | 98.03 | **4.38** |
| `llama3` | 40 | 7.03 | 21.32 | **4.61** |
| `gemini-3.7-flash` | 40 | 33.10 | 55.58 | **4.94** |
| `gpt-5` | 40 | 40.10 | 75.65 | **5.49** |
| `gemini-3.1-pro` | 40 | 28.65 | 58.05 | **5.55** |
| `gpt-5-thinking` | 40 | 44.77 | 58.60 | **5.65** |
| `claude-sonnet-4-6` | 37 | 87.16 | 83.65 | **5.66** |
| `gpt-4o` | 40 | 12.40 | 38.58 | **6.64** |
| `mistral` | 40 | 4.75 | 26.05 | **8.49** |

## 3. Schema validity (deployability)

| model | valid | total | pass rate |
|---|---:|---:|---:|
| `claude-opus-4-6-cot` | 35 | 100 | 35.0% |
| `claude-opus-4-6` | 34 | 100 | 34.0% |
| `claude-opus-4-6-thinking` | 32 | 99 | 32.3% |
| `gemini-3.1-pro` | 32 | 100 | 32.0% |
| `claude-sonnet-4-6` | 30 | 97 | 30.9% |
| `gemini-3.7-flash` | 30 | 100 | 30.0% |
| `gpt-4o` | 30 | 100 | 30.0% |
| `gpt-5` | 28 | 100 | 28.0% |
| `gpt-5-thinking` | 27 | 100 | 27.0% |
| `mistral` | 8 | 100 | 8.0% |
| `llama3` | 6 | 100 | 6.0% |
| `phi3` | 5 | 100 | 5.0% |

## 4. Do the models differ? (omnibus)

Metric: `total_vulns_norm`. Primary test: **Skillings-Mack (handles incomplete blocks)**.

| stratum | Skillings-Mack chi2 | df | p | blocks used | complete-case Friedman N | blocks discarded |
|---|---:|---:|---:|---:|---:|---:|
| simple | 69.32 | 10 | 6.01e-11 | 60 | 0 | 60 |
| complex | 81.18 | 11 | 8.74e-13 | 40 | 0 | 40 |

> **Note.** Complete-case Friedman retains **zero** blocks in at least one stratum: with this many arms and uneven coverage, no scenario has every model present. The classical test is not merely weaker here, it is uncomputable -- which is why Skillings-Mack is the primary test.

## 5. Reasoning-mode contrasts

Paired within-model comparisons -- same model, same scenarios, one variable toggled. `-cot` is a prompt-engineered chain-of-thought suffix; `-thinking` is the vendor's reasoning feature. They are distinct conditions (see THREATS_TO_VALIDITY.md 1.1).

| contrast | stratum | n | mean before | mean after | change | p |
|---|---|---:|---:|---:|---:|---:|
| standard vs extended-thinking | simple | 60 | 12.124 | 10.526 | -13.2% | 0.0122 **\*** |
| standard vs extended-thinking | complex | 31 | 4.858 | 4.170 | -14.2% | 0.1757 |
| standard vs prompt-CoT | simple | 60 | 12.124 | 11.966 | -1.3% | 0.2380 |
| standard vs prompt-CoT | complex | 33 | 2.217 | 2.110 | -4.8% | 0.7506 |
| prompt-CoT vs extended-thinking | simple | 60 | 11.966 | 10.526 | -12.0% | 0.0013 **\*** |
| prompt-CoT vs extended-thinking | complex | 31 | 2.210 | 1.838 | -16.9% | 0.2094 |
| standard vs reasoning_effort=high | simple | 58 | 9.393 | 8.439 | -10.2% | 0.1527 |
| standard vs reasoning_effort=high | complex | 29 | 6.199 | 6.320 | +2.0% | 0.7007 |

`*` significant at alpha=0.05.

## 6. Negative binomial rate model

- Reference model: `claude-opus-4-6`
- Exposure offset: `log(resource_count)` -- coefficients are rate ratios **per resource**
- Overdispersion variance/mean = **138.6** (Poisson requires 1, so NB2 is required)
- Rows fitted 999 of 1196; 197 excluded for zero exposure
- Outcome filtering: NONE. All observations retained, including zero-count rows and zero-count scenarios (v1 dropped these).

| model | IRR | 95% CI | p |
|---|---:|---|---:|
| `claude-opus-4-6-cot` | 0.73 | [0.54, 0.99] | 0.0410 **\*** |
| `claude-opus-4-6-thinking` | 0.87 | [0.75, 1.01] | 0.0700 |
| `gemini-3.7-flash` | 1.19 | [0.98, 1.44] | 0.0846 |
| `gpt-5` | 1.23 | [1.02, 1.47] | 0.0280 **\*** |
| `claude-sonnet-4-6` | 1.24 | [0.60, 2.53] | 0.5611 |
| `gpt-5-thinking` | 1.24 | [1.01, 1.53] | 0.0424 **\*** |
| `gemini-3.1-pro` | 1.30 | [1.15, 1.47] | 2.23e-05 **\*** |
| `mistral` | 1.33 | [0.22, 8.22] | 0.7579 |
| `llama3` | 1.46 | [0.97, 2.21] | 0.0694 |
| `gpt-4o` | 1.58 | [0.73, 3.43] | 0.2472 |
| `phi3` | 4.63 | [3.12, 6.87] | 2.44e-14 **\*** |

## 8. Structural divergence from human-authored IaC

Two-sample Kolmogorov-Smirnov, each model against the 634-file human reference corpus.

```
                   model             metric  ks_statistic       p_value  model_mean  human_mean
         claude-opus-4-6          ast_depth      0.259054  1.330522e-05   10.400000    8.940063
         claude-opus-4-6     resource_count      0.291609  5.337639e-07   26.490000    5.309148
         claude-opus-4-6 resource_diversity      0.267918  5.759369e-06   11.940000    3.787066
     claude-opus-4-6-cot          ast_depth      0.309054  8.123172e-08   10.880000    8.940063
     claude-opus-4-6-cot     resource_count      0.334763  4.024898e-09   30.040000    5.309148
     claude-opus-4-6-cot resource_diversity      0.308454  8.634950e-08   13.380000    3.787066
claude-opus-4-6-thinking          ast_depth      0.272791  4.039800e-06   10.101010    8.940063
claude-opus-4-6-thinking     resource_count      0.274002  3.582704e-06   27.323232    5.309148
claude-opus-4-6-thinking resource_diversity      0.263901  9.395876e-06   12.333333    3.787066
       claude-sonnet-4-6          ast_depth      0.321734  3.095894e-08   10.969072    8.940063
       claude-sonnet-4-6     resource_count      0.300660  3.104162e-07   36.206186    5.309148
       claude-sonnet-4-6 resource_diversity      0.306124  1.733639e-07   15.092784    3.787066
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
  "_schema": "geniac-secbench/agreement/v2",
  "n_raters": 3,
  "rater_files": [
    "human_review_R1.csv",
    "human_review_R2.csv",
    "human_review_R3.csv"
  ],
  "n_scenarios_common": 18,
  "note": "Kappa requires complete blocks, so all statistics use the intersection of scenarios scored by every rater.",
  "fleiss_kappa": {
    "architectural_coherence": 0.20975609756097577,
    "real_world_plausibility": 0.3909774436090227,
    "security_test_relevance": 0.05882352941176462,
    "hallucination_flag": 0.26630434782608686
  },
  "human_vs_judge": {
    "architectural_coherence": {
      "exact_agreement": 0.2777777777777778,
      "kappa": 0.17699115044247793,
      "kappa_type": "quadratic_weighted",
      "within_one": 0.6666666666666666
    },
    "real_world_plausibility": {
      "exact_agreement": 0.7222222222222222,
      "kappa": 0.7945205479452055,
      "kappa_type": "quadratic_weighted",
      "within_one": 1.0
    },
    "security_test_relevance": {
      "exact_agreement": 0.6111111111111112,
      "kappa": 0.48908296943231433,
      "kappa_type": "quadratic_weighted",
      "within_one": 0.8888888888888888
    },
    "hallucination_flag": {
      "exact_agreement": 0.9444444444444444,
      "kappa": 0.64,
      "kappa_type": "cohen"
    }
  },
  "consensus_ties_broken": {
    "architectural_coherence": 2,
    "real_world_plausibility": 3,
    "security_test_relevance": 4,
    "hallucination_flag": 0
  },
  "n_scenarios_compared": 18
}
```

## 9. Generation cost and reasoning-token usage

- Reasoning tokens per generation: median **19**, max **1988**, over 137 logged generations.
- Measured against a 16,000-token budget under the fixed-budget configuration: `budget_tokens` is a ceiling the model may underspend, not a target. A small reasoning effect on this task class must not be read as "reasoning does not help" in general.

- Completion tokens logged: **2,401,530** total, median **1,090** per generation.
