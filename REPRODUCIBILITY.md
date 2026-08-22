# Reproducing the Benchmark

We have designed this repository to be 100% reproducible with minimal effort. Please follow these steps sequentially.

## Step 1: Environment Setup

### Option A: Docker (Highly Recommended)
Because installing security scanners (Checkov, Trivy, KICS) locally can cause cross-platform dependency issues, we provide a unified Docker container.
\\\ash
git clone https://github.com/AnimeshShaw/GenIaC-SecBench.git
cd CloudSec-LLMBench-Code
docker build -t geniac-secbench .
\\\

### Option B: Local Setup
1. Ensure Python 3.10+ is installed.
2. Run \pip install -r requirements.txt\
3. Install [Checkov](https://github.com/bridgecrewio/checkov), [Trivy](https://github.com/aquasecurity/trivy), and [KICS](https://github.com/Checkmarx/kics) manually and add them to your system PATH.

---

## Step 2: Download the Dataset from Hugging Face
The generated infrastructure code and raw scanner results are too large for GitHub. We host them on Hugging Face.

We provide an automated script to securely fetch the dataset and place it directly into your local \data/\ folder.

\\\ash
# Install the Hugging Face hub client if you haven't already
pip install huggingface_hub

# Run the download script
python src/utilities/download_dataset.py --repo-id AnimeshShaw/GenIaC-SecBench
\\\
*(Once complete, you will see folders like \data/generated/\ and \data/summary_reports/\ appear locally).*

---

## Step 3: Run the Pipeline via \
eproduce.py\

We provide a master automation script called \
eproduce.py\ at the root of the project.

### Workflow A: Re-run the Statistical Analysis Only
If you simply want to verify our KS-Tests, GLMM regressions, and Friedman tests using the existing dataset you downloaded from Hugging Face:
\\\ash
# Locally:
python reproduce.py --analyze-only

# Or via Docker:
docker run -v $(pwd)/data:/app/data geniac-secbench --analyze-only
\\\

### Workflow B: Re-generate the Entire Benchmark from Scratch
If you want to spend the compute tokens to ask GPT-5, Claude, etc., to re-generate the 11,000 files from scratch, you must provide your own API keys.

1. Create a \.env\ file at the root:
   \\\env
   OPENAI_API_KEY=sk-...
   XAI_API_KEY=xai-...
   ANTHROPIC_API_KEY=sk-...
   GEMINI_API_KEY=AIza...
   \\\
2. Run the full generation pipeline:
   \\\ash
   python reproduce.py --all
   \\\

---

## Output Expectations
If the pipeline executes successfully, all final metrics will be outputted to \data/summary_reports/\ as CSV and JSON files, exactly matching the tables presented in the research paper.
