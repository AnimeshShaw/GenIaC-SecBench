---
pretty_name: GenIaC-SecBench
license: cc-by-4.0
task_categories:
  - text-generation
language:
  - en
tags:
  - infrastructure-as-code
  - security
  - terraform
  - cloudformation
  - kubernetes
  - static-analysis
  - llm-evaluation
  - benchmark
size_categories:
  - 1K<n<10K
configs:
  - config_name: master_results
    data_files: summary_reports/master_results.csv
  - config_name: findings
    data_files: summary_reports/findings_raw.csv
  - config_name: human_baseline
    data_files: summary_reports/human_baseline_density.csv
---

# GenIaC-SecBench

A benchmark for evaluating the security of LLM-generated Infrastructure-as-Code
(IaC) **against a size-matched human baseline**.

Paper: *Compared to What? A Human-Anchored Security Benchmark for LLM-Generated
Infrastructure-as-Code* (under review)
Code: https://github.com/AnimeshShaw/GenIaC-SecBench

## Why this dataset exists

Prior evaluations of generated IaC report vulnerability counts **for models
only**. Stating that a model averages eight findings per declared resource
invites the obvious question — *compared to what?* Without a human reference
measured through the same toolchain, such numbers cannot distinguish three very
different situations: models being genuinely careless, models simply emitting
more infrastructure per file, or a scanner ruleset that flags any template
heavily.

This dataset supplies the missing reference point. It contains both the generated
corpus **and** 634 human-authored IaC templates scanned with the identical three
engines, so the comparison is like-for-like.

## What is in it

| | |
|---|---|
| Scenarios | 100 (60 simple, 40 complex) |
| Model configurations | 12, across 4 vendors, open and closed weights |
| Generated artifacts | 1,196 |
| Scanners | Checkov, Trivy, KICS — **100% coverage on all three** |
| Total findings | 38,803 |
| Human reference corpus | 634 templates, same scanners |
| Human expert review | 3 reviewers × 18 scenarios, 4 criteria |
| IaC formats | Terraform, CloudFormation, ARM, Kubernetes |
| Clouds | AWS, Azure, GCP, cloud-agnostic |

### Model configurations

`claude-opus-4-6`, `claude-opus-4-6-cot`, `claude-opus-4-6-thinking`,
`claude-sonnet-4-6`, `gemini-3.1-pro`, `gemini-3.7-flash`, `gpt-4o`, `gpt-5`,
`gpt-5-thinking`, `llama3`, `mistral`, `phi3`

Three of these are reasoning **arms of the same base model**, which is what makes
the reasoning comparison clean:

- `-cot` — prompt-engineered chain-of-thought (a system-prompt instruction)
- `-thinking` — the vendor's own extended-thinking API
- neither suffix — standard generation

These are *different conditions and must not be pooled*. An earlier revision of
this project conflated them; see `THREATS_TO_VALIDITY.md` §1.1.

## Directory layout

```
prompts/                    100 benchmark scenarios (the study's input)
  scenarios.json              60 simple
  scenarios_complex.json      40 complex

generated/                  1,196 model outputs
  {simple,complex}/{model}/{scenario_id}/main.{tf,yaml,json}

scan_results/               raw scanner JSON, one dir per artifact
  {simple,complex}/{model}/{scenario_id}/{checkov,trivy,kics}.json

human_reference_dataset/    634 human-authored templates (as fetched)
scan_results_human/         same three scanners over that corpus

summary_reports/            every derived table the paper cites
figures/                    publication figures
human_reviews/              anonymized expert scores + judge answer key
generation_usage.jsonl      per-generation token usage
batch_jobs.json             Message Batches submitted, for provenance
```

### Key files in `summary_reports/`

| File | Contents |
|---|---|
| `master_results.csv` | **Start here.** One row per (scenario × model): validity, per-scanner counts, resource count, severity. 1,196 rows. |
| `findings_raw.csv` | One row per finding (38,803). |
| `human_baseline_density.csv` | Per-file human density — the comparison anchor. |
| `structural_metrics.csv` | AST depth, resource count, diversity per artifact. |
| `human_reference_metrics.csv` | Same metrics for the 634 human files. |
| `statistical_results.json` | Skillings–Mack omnibus, post-hoc, reasoning contrasts. |
| `nb_glmm_results.json` | Negative binomial GEE with exposure offset. |
| `ks_test_human_baseline.csv` | KS tests vs. the human corpus. |
| `human_agreement_metrics.json` | Fleiss' κ, human-vs-judge agreement. |
| `scan_coverage.csv` | Per-model-per-scanner coverage manifest. |

Full column definitions: `docs/appendix/data_dictionary.md` in the code repo.

## Quick start

```python
import pandas as pd

M = "hf://datasets/AnimeshShaw/GenIaC-SecBench/summary_reports/"
m = pd.read_csv(M + "master_results.csv")
h = pd.read_csv(M + "human_baseline_density.csv")

m["total"] = m[["checkov_vulns", "trivy_vulns", "kics_vulns"]].fillna(0).sum(axis=1)
m["density"] = m["total"] / m["resource_count"].where(m["resource_count"] > 0)

print(m.groupby("model")["density"].mean().sort_values())
print("human baseline:", h[h.resource_count > 0]["density"].mean())
```

### Reproducing every table and figure

```bash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd GenIaC-SecBench
pip install -e .
python scripts/download_dataset.py           # restores this dataset into data/
python -m geniac_secbench.cli --phase analyze
```

No API keys or scanner binaries are needed for `--phase analyze`; it recomputes
all statistics, figures, and `docs/findings/RESULTS.md` from the released data.

## ⚠️ Read before you compare densities

**Vulnerability density is strongly inverse to artifact size** (Spearman
ρ = −0.546, p < 10⁻⁷⁷). A model that emits 50 resources will show a *lower*
density than one emitting 2, independent of how secure either is.

**Comparing raw densities across groups with different artifact sizes measures
artifact size, not security.** Match on `resource_count` first. The unmatched
comparison in this dataset suggests LLMs are indistinguishable from humans on
complex scenarios; the size-matched comparison shows every configuration at
3.2×–3.9× the human rate. The second is correct.

Two further traps, both documented at length in `THREATS_TO_VALIDITY.md`:

- **Checkov emits no severity tiers** without a commercial subscription, so all
  14,017 Checkov findings carry `severity=UNKNOWN`. Severity analysis reflects
  Trivy + KICS only, and the large "Other" bucket in CIS breakdowns is a tooling
  artifact, not a vulnerability class.
- **`resource_counts.csv` is not authoritative.** The scanner-derived count
  silently degrades to 1 on parse failure. Use `structural_metrics.csv`, which is
  AST-derived.

## Known limitations

- The human corpus is **not a matched control**. Those files were not written
  against these 100 scenarios; many are curated *examples* rather than production
  infrastructure, which may bias the baseline in either direction. The direction
  is unknown, and we do not claim it favours our argument.
- **4 of 1,200 generations are missing** — three complex scenarios exceeded the
  128k output ceiling even at the model maximum. Truncated outputs were discarded
  rather than written, since a truncated template still parses and would deflate
  both validity and finding counts.
- **Extended-thinking arms run at `temperature=1`** (API-mandated) versus 0.2
  elsewhere — a confound that cannot be removed without disabling the feature
  under test.
- **Scanners detect policy deviations, not proven exploitability.** Zero findings
  means only that three rulesets flagged nothing.
- Cross-format densities are **not comparable**; the resource-count denominator
  is parser-dependent. Terraform (836 of 1,196 artifacts) is the reliable subset.

## Human review data and privacy

`human_reviews/` contains scores from three practicing cloud/security engineers,
released under anonymized identifiers `R1`–`R3`. The three consented to be named
in the paper's acknowledgements. **The mapping between identifiers and identities
is retained solely by the author and is not distributed in this dataset or the
code repository.**

Inter-rater agreement is modest by design and reported honestly: Fleiss' κ ranges
from 0.391 (plausibility) down to 0.059 (security-test relevance, near chance).
The low figure is a finding — some evaluation criteria may not be reliably
measurable by humans — not a defect to be adjudicated away.

## Licence and provenance

- **Data produced by this project** (generated IaC, scan results, derived tables,
  figures, review scores): **CC-BY-4.0**.
- **`human_reference_dataset/`** is redistributed from three public repositories
  and remains under each project's original licence:
  [aws-cloudformation-templates](https://github.com/aws-cloudformation/aws-cloudformation-templates),
  [iac-model-evaluation](https://github.com/aws-cloudformation/iac-model-evaluation),
  [iac-eval](https://github.com/autoiac-project/iac-eval).
  It is included to make the human baseline reproducible; consult each upstream
  repository for its terms before redistributing.
- **Code**: MIT (see the GitHub repository).

## Citation

```bibtex
@article{anonymous2026comparedtowhat,
  title         = {Compared to What? A Human-Anchored Security Benchmark for
                   LLM-Generated Infrastructure-as-Code},
  author        = {Anonymous},
  year          = {2026},
}
```
