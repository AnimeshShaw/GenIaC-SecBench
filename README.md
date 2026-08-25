# GenIaC-SecBench

**Paper:** *Valid but Vulnerable: The Security-by-Default Paradox in LLM-Generated Infrastructure*

This repository contains the evaluation pipeline, statistical analysis code, and LLM-as-a-Judge infrastructure for the GenIaC-SecBench research project.

## Key Finding: The Validity-Security Paradox

Our evaluation of 11 frontier and open-source LLMs across 100 deployment scenarios reveals a critical paradox: **the models most capable of writing functionally deployable Infrastructure-as-Code (IaC) are not the most secure by default**, and the models with the lowest vulnerability counts often achieve that only by failing to generate valid code at all (survivorship bias). Extended "thinking" modes show a large *practical* reduction in vulnerability density, though establishing statistical significance for that effect required closing the scanner-coverage gaps documented in `docs/THREATS_TO_VALIDITY.md`.

Full results: `docs/findings/comprehensive_findings.md`. Claim-by-claim statistical evidence: `docs/findings/claims_and_statistical_evidence.md`.

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
