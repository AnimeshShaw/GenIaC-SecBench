# Reproducing GenIaC-SecBench

Follow these steps sequentially. If a step doesn't work as documented,
that's a bug -- please open an issue with your OS/Python version and the
exact command (see `CONTRIBUTING.md`).

## Step 1: Environment Setup

### Option A: Docker (recommended)

Security scanners (Checkov, Trivy, KICS) have real cross-platform
dependency friction -- see the note on Checkov below -- so a container is
the path of least resistance.

```bash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd GenIaC-SecBench
docker build -t geniac-secbench .
docker run -v "$(pwd)/data:/app/data" geniac-secbench --phase analyze
```

### Option B: Local Setup

1. Python 3.10+.
2. **Use a dedicated virtual environment** (`python -m venv .venv && .venv/bin/activate` or conda). Installing this project's dependencies into a shared/global Python environment that also has other projects' packages is what caused a real, hard-to-diagnose bug during development -- see the Checkov note below.
3. `pip install -e .` (installs the `geniac_secbench` package) then `pip install -r requirements.txt`.
4. Install [Trivy](https://github.com/aquasecurity/trivy) and add it to your PATH (or set `TRIVY_PATH`).
5. Install KICS and ARM-TTK: `python third_party/install.py`.
6. Install Checkov into an **isolated** environment: `python scripts/setup_checkov_env.py`.

**Why Checkov gets its own environment:** Checkov depends on `bc-python-hcl2`, which installs into the same `hcl2` Python import name as the vanilla `python-hcl2` package this project's structural-metrics scripts need (to parse modern Terraform syntax that `bc-python-hcl2`'s grammar can't handle). Whichever package is installed *last* into a shared environment silently overwrites the other's files -- there is no error until something tries to use the missing half of the API. This broke Checkov entirely at one point during this project's own development (see `docs/THREATS_TO_VALIDITY.md`). `scripts/setup_checkov_env.py` sidesteps the conflict instead of trying to pin around it.

### Tool discovery

Every scanner/validator is located via, in order: an env var override (`CHECKOV_PATH`, `TRIVY_PATH`, `KICS_PATH`, `TERRAFORM_PATH`, `KUBECONFORM_PATH`, `CFN-LINT_PATH`), then `PATH`, then an OS-specific fallback. Set the env var if a tool is installed somewhere non-standard.

---

## Step 2: Download the Dataset from Hugging Face

The generated infrastructure code and raw scanner results are too large for GitHub and are hosted on Hugging Face.

```bash
pip install huggingface_hub  # included in requirements.txt already
python scripts/download_dataset.py --repo-id AnimeshShaw/GenIaC-SecBench
```

Once complete, `data/generated/`, `data/scan_results/`, and `data/summary_reports/` will be populated locally. (`data/prompts/` and `data/human_reviews/` are small enough to ship directly in this git repository and don't need downloading.)

---

## Step 3: Run the Pipeline

Everything goes through one entry point:

```bash
python -m geniac_secbench.cli --phase <phase>
```

### Re-run the statistical analysis only

If you just want to verify the KS-tests, GEE regression, and Friedman/Wilcoxon tests against the dataset you downloaded:

```bash
python -m geniac_secbench.cli --phase analyze
# equivalent to: structural -> judge -> statistics -> report, in that order
```

### Re-run scanning only

If you've already got generated IaC and just want fresh scan results (e.g. after a scanner version bump):

```bash
python -m geniac_secbench.cli --phase scan
```

This is idempotent -- scenarios that already have a given scanner's output are skipped, so re-running after an interruption only fills the gaps. Run `python -m geniac_secbench.phase3_scanning.run_scanners --help` for finer-grained flags (single model, single scanner). After a run, check `data/summary_reports/scan_coverage.csv` -- it lists exactly how many scenarios each (model, scanner) pair covers, so a partial run is visible rather than silent.

### Re-generate the entire benchmark from scratch

This calls GPT-5, Claude, Gemini, etc. to re-generate ~1,000 files from scratch and costs real API spend.

1. Copy `.env.example` to `.env` and fill in your keys (OpenAI, Anthropic, Gemini, xAI for the Phase 5 judge).
2. Local SLMs (llama3, mistral, phi3) run via [Ollama](https://ollama.com) and need no API key -- make sure `ollama` is installed and running first.
3. Run the full pipeline:

```bash
python -m geniac_secbench.cli --phase all
```

---

## Output Expectations

If the pipeline executes successfully, all final metrics land in `data/summary_reports/` as CSV and JSON, and figures land in `data/figures/` + `paper/figures/`. See `docs/appendix/data_dictionary.md` for what every output file contains.

## Known Limitations

Read `docs/THREATS_TO_VALIDITY.md` before treating any single number from this pipeline as ground truth for a claim in a paper. It documents, with specifics: the scanner-coverage history, the statistical model's assumptions and what changed, remaining design imbalances, and protocol deviations from the pre-registered methodology.
