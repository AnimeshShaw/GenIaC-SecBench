# GenIaC-SecBench

[![arXiv](https://img.shields.io/badge/arXiv-2608.28021-b31b1b.svg)](https://arxiv.org/abs/2608.28021)
[![Dataset on HF](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-GenIaC--SecBench-yellow)](https://huggingface.co/datasets/AnimeshShaw/GenIaC-SecBench)
[![Code License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Data License: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-19%20passing-brightgreen.svg)](tests/)

**A human-anchored security benchmark for LLM-generated Infrastructure-as-Code.**

> **Paper:** [*Compared to What? A Human-Anchored Security Benchmark for
> LLM-Generated Infrastructure-as-Code*](https://arxiv.org/abs/2608.28021) — arXiv:2608.28021

Prior evaluations of generated IaC report vulnerability counts **for models
only**. Saying a model averages eight findings per resource invites one question —
*compared to what?* This benchmark supplies the missing reference point by
scanning 634 human-authored templates with the identical toolchain.

---

## Headline result

<table>
<tr><td width="55%">

**Every model configuration produces 3.21×–3.87× the vulnerability density of
human engineers**, matched on artifact size — across four vendors, open and
closed weights, and three reasoning modes.

The gap is **widest on the simplest tasks**: 4.9× at one declared resource,
falling to 1.4× at twenty or more. Small generated snippets get the least review
and carry the largest relative penalty.

</td><td>

| | |
|---|---:|
| Scenarios | 100 |
| Configurations | 12 |
| Artifacts | 1,196 |
| Scanners | 3 (100% coverage) |
| Findings | 38,803 |
| Human baseline | 634 files |

</td></tr>
</table>

**Reasoning modes.** Vendor extended thinking reduces density modestly but
significantly (−13.2%, *p*=0.012) and beats prompted chain-of-thought
(−12.0%, *p*=0.0013). Prompted CoT alone confers **no** measurable benefit
(−1.3%, n.s.). Extended thinking spends **under 1%** of its output budget on
reasoning for this task class, which bounds the achievable effect.

**Two negative results, reported as findings.** The intuitive
"validity–security paradox" is **unsupported** (*r*=0.158, *p*=0.625). And
complete-case Friedman testing is **uncomputable** on realistic benchmark
designs — with 12 configurations, no scenario has complete coverage — motivating
the Skillings–Mack statistic.

---

## Quick start

```bash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd GenIaC-SecBench
pip install -e .

python scripts/download_dataset.py            # pull the dataset from Hugging Face
python -m geniac_secbench.cli --phase analyze # regenerate every table and figure
```

`--phase analyze` needs **no API keys and no scanner binaries**. It recomputes
all statistics, figures, and `docs/findings/RESULTS.md` from the released data.

<details>
<summary><b>Running the full pipeline (generation and scanning)</b></summary>

```bash
cp .env.example .env          # add provider API keys
python third_party/install.py # fetch KICS + ARM-TTK
python -m geniac_secbench.cli --phase all
```

| Phase | Requires | Produces |
|---|---|---|
| `generate` | API keys | `data/generated/` |
| `validate` | terraform, cfn-lint, kubeconform, ARM-TTK | `schema_validity.csv` |
| `scan` | checkov, trivy, kics | `findings_raw.csv`, `scan_coverage.csv` |
| `structural` | — | `structural_metrics.csv`, KS results |
| `judge` | API key | `llm_judge_scores.csv` |
| `statistics` | — | `master_results.csv`, omnibus + GLMM results |
| `human_review` | — | `human_agreement_metrics.json` |
| `report` | — | figures, `RESULTS.md` |

</details>

---

## ⚠️ Before you compare densities

**Vulnerability density is strongly inverse to artifact size** (Spearman
ρ = −0.546, *p* < 10⁻⁷⁷). A model emitting 50 resources shows *lower* density
than one emitting 2, regardless of how secure either is.

**Comparing raw densities across groups of different sizes measures size, not
security.** Match on `resource_count` first. In this very dataset the unmatched
comparison suggests LLMs are indistinguishable from humans on complex scenarios;
the size-matched comparison shows every configuration at 3.2×–3.9×. The second is
correct.

Two further traps are documented in [`docs/THREATS_TO_VALIDITY.md`](docs/THREATS_TO_VALIDITY.md):
Checkov emits no severity tiers without a paid subscription (so all 14,017 of its
findings are `UNKNOWN`), and `resource_counts.csv` silently degrades to 1 on parse
failure — use `structural_metrics.csv`.

---

## Repository layout

This repository holds **code**. All data lives on
[Hugging Face](https://huggingface.co/datasets/AnimeshShaw/GenIaC-SecBench),
including the scenario prompts and anonymized reviewer scores — they are inputs
to the benchmark, not source, and splitting them across two hosts let a clone
silently disagree with the published dataset.

```text
src/geniac_secbench/
  config.py              single source of truth for every path
  cli.py                 pipeline entry point
  phase1_generation/     LLM API calls -> raw IaC (sync + batch)
  phase2_validation/     terraform validate / cfn-lint / ARM-TTK / kubeconform
  phase3_scanning/       Checkov + Trivy + KICS, over models AND the human corpus
  phase4_structural/     AST metrics + KS tests vs. the human baseline
  phase5_llm_judge/      independent scenario review by an LLM judge
  phase6_statistics/     master table, Skillings-Mack, NB-GEE rate model
  phase7_human_review/   stratified sampling, inter-rater and judge agreement
  phase8_reporting/      figures and the generated results document

scripts/                 dataset download/upload, environment setup
tests/                   smoke tests
third_party/             scanner binaries (gitignored; install.py fetches them)
```

## Documentation

| Document | What it covers |
|---|---|
| [`docs/CODEBASE.md`](docs/CODEBASE.md) | Per-phase guide and the non-obvious constraints behind each design choice |
| [`docs/THREATS_TO_VALIDITY.md`](docs/THREATS_TO_VALIDITY.md) | Limitations, corrections, and protocol deviations |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Every output file and column |
| [`docs/findings/RESULTS.md`](docs/findings/RESULTS.md) | Results, generated from data — never hand-edited |
| [`docs/findings/claims_and_statistical_evidence.md`](docs/findings/claims_and_statistical_evidence.md) | Claim-by-claim evidence mapping |
| [`docs/methodology/`](docs/methodology/) | Human baseline construction and review protocol |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Step-by-step reproduction |

## Acknowledgements

Three practicing cloud and security engineers independently reviewed the
stratified scenario sample: **Abhishek Pandey**, **Manickam Venkatachalam**, and
**Prajjuwal Varshney**. Their scores ship anonymized as `R1`–`R3`; the mapping to
identities is retained solely by the author and is not distributed.

## Citation

```bibtex
@article{shaw2026comparedtowhat,
  title         = {Compared to What? A Human-Anchored Security Benchmark for
                   LLM-Generated Infrastructure-as-Code},
  author        = {Shaw, Animesh},
  year          = {2026},
  eprint        = {2608.28021},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  url           = {https://arxiv.org/abs/2608.28021}
}
```

## Licence

Code **MIT** ([`LICENSE`](LICENSE)) · Data **CC-BY-4.0** ([`LICENSE-DATA`](LICENSE-DATA)).
The human reference corpus is redistributed from three public repositories and
remains under their original terms — see the
[dataset card](https://huggingface.co/datasets/AnimeshShaw/GenIaC-SecBench).
