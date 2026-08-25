# InfraSecBench: Project Status & Phased Roadmap

This document provides a highly organized, comprehensive overview of what has been accomplished, what is left to do, and the exact sequence of operations for the *InfraSecBench* research project.

## Research Objective
To evaluate if frontier LLMs, baselines, and local SLMs produce "secure-by-default" Infrastructure-as-Code (IaC), and to measure whether "Thinking Mode" reduces security misconfigurations. Furthermore, we evaluate across **two axes of complexity** (Simple vs. Complex scenarios) to understand exactly where model reasoning breaks down.

## ✅ Phase 1: Foundation (COMPLETED)
- [x] Initialized Git repository for data safety and frequent commits.
- [x] Built the Python pipeline (`generate_iac.py`, `run_scanners.py`, `parse_results.py`, `visualise.py`).
- [x] Tested with basic scenarios (60 prompts).
- [x] Integrated `checkov` for local security scanning.
- [x] Visualized initial data.

## ✅ Phase 2: Data Maturation (COMPLETED)
- [x] Designed 40 highly complex, multi-component architectural scenarios (`data/scenarios_complex.json`).
- [x] Kept the 60 simple scenarios securely intact (`data/scenarios.json`).
- [x] Established the dual-dataset evaluation methodology.

## ⏳ Phase 3: Comprehensive Evaluation - Complex Scenarios (IN PROGRESS)
We will first run the 40 complex scenarios across all cloud models to establish our ceiling.
- [ ] Run generation for 40 complex scenarios against:
  - `gpt-5`
  - `claude-opus-4-6`
  - `gemini-3.7-flash`
  - `gemini-3.1-pro`
  - `gpt-4o`
  - `claude-3-5-sonnet`
  - `gpt-5-thinking`
  - `claude-opus-4-6-thinking`
- [ ] Run Checkov over the `complex` dataset.
- [ ] Parse and generate intermediate charts.

## ⏸️ Phase 4: Comprehensive Evaluation - Simple Scenarios (PENDING)
Once Phase 3 is completely finished, we will pivot back and run the original 60 simple scenarios against ALL of the above models.
- [ ] Run generation for 60 simple scenarios against all cloud and thinking models.
- [ ] Run Checkov over the `simple` dataset.
- [ ] Parse and generate the comparative "Simple vs. Complex" charts.

## ⏸️ Phase 5: Local SLM Integration (PENDING)
After all cloud APIs are exhausted and evaluated, we move to local evaluation.
- [ ] Build Ollama integration into the pipeline.
- [ ] Evaluate `llama3`, `mistral`, and `phi3` against **both** the complex and simple datasets.
- [ ] Scan, parse, and incorporate into final dataset.

## ⏸️ Phase 6: Reproducibility & Paper Drafting (PENDING)
- [ ] Finalize `README.md` with foolproof instructions, dependency lists, and API key requirements.
- [ ] Generate the LaTeX skeleton for the research paper, embedding our finalized figures and CIS mapping data.
