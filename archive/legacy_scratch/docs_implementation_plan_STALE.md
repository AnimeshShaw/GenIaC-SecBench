# InfraSecBench: Architecture and Implementation Plan

## 1. Core Research Question
**"How well do frontier, baseline, and local AI models write secure-by-default Infrastructure-as-Code (IaC), and does explicitly enabling 'Thinking' mode reduce infrastructure vulnerabilities?"**

*Note on "Thinking Mode":* Including the "Thinking" mode analysis makes this paper significantly more impactful. Instead of splitting it into a separate paper, we should frame it as a primary section in this paper. The evolution of LLMs is moving toward reasoning/thinking modes, so evaluating if "thinking harder" translates directly to "fewer security misconfigurations" is highly relevant right now.

## 2. What We Have Done So Far
- **Project Structure**: Established the `InfraSecBench` orchestrator codebase (Python) in `D:\Agentic Exps\InfraSecBench`.
- **Generation Pipeline**: Built a `litellm`-based pipeline capable of querying multiple LLMs and extracting raw IaC (Terraform, CloudFormation, ARM, Kubernetes) from their markdown responses.
- **Scanner Orchestration**: Integrated `checkov` to locally scan generated IaC, catching misconfigurations without uploading code to third parties.
- **Data Parsing & Visualization**: Wrote pandas-based aggregation scripts that map Checkov JSON failures to CIS Benchmark categories (Networking, IAM, Data Protection, etc.) and generate Seaborn charts.
- **Initial Run**: Successfully proved the pipeline end-to-end on 60 basic scenarios using GPT-5 and Claude Opus 4.6, identifying 400+ security vulnerabilities.

## 3. What We Will Be Doing Next (The Expanded Plan)

### A. Phase 1: High-Complexity Scenarios
The initial 60 scenarios ("Create an S3 bucket") are too simple to test the limits of frontier models. We will replace or augment them with **40 highly complex, multi-component architectural scenarios**.
*   **Examples of Complex Scenarios:**
    *   *AWS:* "Deploy a secure hub-and-spoke network topology using AWS Transit Gateway, with strict NACLs, isolated private subnets for RDS, and a centralized NAT gateway."
    *   *Azure:* "Provision an Azure Kubernetes Service (AKS) cluster integrated with Azure AD for RBAC, utilizing Azure CNI for networking, and deploying an Istio service mesh with mTLS enabled."
    *   *GCP:* "Create a multi-region Spanner instance accessed by Cloud Run services, enforced by VPC Service Controls and strict least-privilege IAM bindings."
*   **Action Item:** Generate and format these 40 complex prompts into `data/scenarios_complex.json`.

### B. Phase 2: Expanded Model Matrix
We will drastically expand the models evaluated to create a definitive benchmark:
1.  **Frontier Models:** `gpt-5`, `claude-opus-4-6`.
2.  **Gemini Suite:** `gemini-3.7-flash`, `gemini-3.1-pro-preview` (using updated keys).
3.  **Older Baselines:** `gpt-4o`, `claude-3-5-sonnet` (to measure generation-over-generation improvement).
4.  **Local SLMs (Small Language Models):** `llama3` (8B), `mistral` (7B), `phi3` (3.8B).
    *   *Constraint Handling:* We will use Ollama. The Python orchestrator will run them strictly **one-by-one** to remain within the 16GB RAM limit.

### C. Phase 3: "Thinking Mode" Benchmarking
We will duplicate the API calls for capable models (GPT-5, Claude, Gemini) and turn on their respective reasoning features.
*   **Action Item:** Update `generate_iac.py` to support a `-thinking` suffix in the model registry. When detected, the script will pass `reasoning_effort="high"` (OpenAI) or equivalent Anthropic/Google parameters.
*   We will then plot standard output vs. thinking output side-by-side on the CIS Category Heatmap.

### D. Phase 4: Full Pipeline Execution and Paper Drafting
1.  Run the generation pipeline (will take hours given the complexity and local SLM execution).
2.  Run the `checkov` scanner over the hundreds of generated architectures.
3.  Parse results and generate final, high-resolution charts.
4.  Scaffold a LaTeX paper skeleton integrating the hypothesis, methodology, and generated charts.
