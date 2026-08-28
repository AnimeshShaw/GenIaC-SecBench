# GenIaC-SecBench

**Paper:** *Compared to What? A Human-Anchored Security Benchmark for LLM-Generated Infrastructure-as-Code*

This repository contains the evaluation pipeline, statistical analysis code, and LLM-as-a-Judge infrastructure for the GenIaC-SecBench research project.

## Key Finding: LLM-generated IaC is ~3.5x less secure than human-authored IaC

Measured against 634 hand-written IaC templates through an identical toolchain and
**matched on artifact size**, every one of 12 model configurations produces
**3.21x-3.87x** the vulnerability density of human engineers -- across four vendors,
open and closed weights, and three reasoning modes. The gap is **widest on the
simplest tasks** (4.9x at one declared resource, 1.4x at twenty or more).

Vendor extended-thinking modes reduce density modestly but significantly
(-13.2%, p=0.012) and meaningfully outperform prompted chain-of-thought
(-12.0%, p=0.0013), which on its own confers no measurable security benefit.
Instrumenting the API shows why the effect is bounded: extended thinking consumes
**under 1% of the output budget** on this task class.

We also report two negative results: the intuitive "validity-security paradox"
is **not supported** (r=0.158, p=0.625), and complete-case Friedman testing is
**uncomputable** on realistic benchmark designs, motivating Skillings-Mack.

Full results: `docs/findings/RESULTS.md` (generated from data). Interpretation:
`docs/findings/comprehensive_findings.md`. Claim-by-claim evidence:
`docs/findings/claims_and_statistical_evidence.md`. Corrections and limitations:
`docs/THREATS_TO_VALIDITY.md`.

## Repository Architecture

This repository contains the pipeline and analysis **code**. The full dataset (~1,000 generated IaC files, raw JSON security scans from Checkov/Trivy/KICS, human reference corpus, and human review data) is hosted on **Hugging Face Datasets** -- see `REPRODUCIBILITY.md`.

```
GenIaC-SecBench/
├── src/geniac_secbench/       # installable package -- one dir per pipeline phase
│   ├── config.py              #   single source of truth for repo paths
│   ├── cli.py                 #   `python -m geniac_secbench.cli --phase all`
│   ├── phase1_generation/     #   1. LLM API calls -> raw IaC
│   ├── phase2_validation/     #   2. terraform validate / cfn-lint / ARM-TTK / kubeconform
│   ├── phase3_scanning/       #   3. Checkov + Trivy + KICS -> findings_raw.csv
│   ├── phase4_structural/     #   4. AST metrics + KS-test vs. human baseline
│   ├── phase5_llm_judge/      #   5. Grok-4.6 independent scenario judge
│   ├── phase6_statistics/     #   6. Friedman/Wilcoxon + NB-GEE regression
│   ├── phase7_human_review/   #   7. stratified sampling + inter-rater kappa
│   └── phase8_reporting/      #   8. publication figures
├── scripts/                   # standalone utilities (dedup, HF download, checkov venv setup)
├── third_party/               # gitignored: KICS, ARM-TTK binaries (third_party/install.py)
├── data/                      # mostly gitignored -- see REPRODUCIBILITY.md
│   ├── prompts/                #   tracked: the 100 scenario definitions (source of truth)
│   ├── human_reviews/          #   tracked: anonymized (R1/R2/R3) rater CSVs
│   ├── generated/               #   HF-hosted: LLM-generated IaC
│   ├── scan_results/            #   HF-hosted: raw scanner JSON
│   └── summary_reports/         #   HF-hosted: all derived CSV/JSON (master_results.csv etc.)
├── docs/
│   ├── methodology/            # pre-registered study design, human review protocol
│   ├── findings/               # results, claim-to-evidence mapping
│   ├── appendix/               # data dictionary, review guide
│   └── THREATS_TO_VALIDITY.md  # coverage history, design limitations, protocol deviations
├── paper/figures/              # figures as embedded in the manuscript
├── archive/legacy_scratch/     # superseded/one-off scripts, kept for transparency
└── REPRODUCIBILITY.md          # step-by-step setup guide
```

## Quickstart

```bash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd GenIaC-SecBench
pip install -e .
pip install -r requirements.txt
python scripts/download_dataset.py
python -m geniac_secbench.cli --phase analyze                 # re-run all stats/figures on the downloaded data
```

See `REPRODUCIBILITY.md` for the full setup (Docker, individual scanner installs, regenerating the dataset from scratch with your own API keys).

## Reproducibility & Threats to Validity

This benchmark went through a documented remediation pass after an internal
audit found scanner-coverage gaps, a statistical model misspecification, and
several path/tooling bugs that had gone unnoticed. Every issue found, how it
was fixed, and what limitations remain are recorded in
`docs/THREATS_TO_VALIDITY.md` and `CHANGELOG.md` -- read them before citing
specific numbers from an early draft of this work.

## License

- **Code:** MIT License (`LICENSE`)
- **Dataset:** CC-BY-4.0 (`LICENSE-DATA`)

## Citation

See `CITATION.cff`.
