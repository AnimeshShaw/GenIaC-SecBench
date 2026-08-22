# GenIaC-SecBench

**Paper:** *Valid but Vulnerable: The Security-by-Default Paradox in LLM-Generated Infrastructure*

This repository contains the evaluation pipeline, statistical analysis code, and LLM-as-a-Judge infrastructure for the GenIaC-SecBench research project. 

## 🏆 Key Finding: The Validity-Security Paradox
Our evaluation of 11 frontier Large Language Models reveals a critical paradox: **The models that are most capable of writing functionally deployable Infrastructure-as-Code (IaC) are simultaneously the most prone to severe security vulnerabilities.** Conversely, extended "thinking" modes reduce vulnerability density by up to 95%, but achieve this by generating highly over-engineered, structurally alien code compared to human baselines.

## 🗂️ Repository Architecture (Code vs. Data)
To adhere to open-source best practices, this repository contains **only the logic and pipeline code**. 

The massive dataset (11,000+ generated IaC files, raw JSON security scans from Checkov/Trivy/KICS, and human reviews) is hosted on **Hugging Face Datasets**.

### Directory Structure
\\\	ext
├── src/
│   ├── pipeline/          # 1. Generation, 2. Validation, 3. Security Scanning
│   ├── analysis/          # 4. Structural Metrics, 5. LLM Judge, 6. Statistics
│   └── utilities/         # Helper scripts (including the HF data downloader)
├── docs/                  # Detailed findings, methodology, and data dictionaries
├── data/                  # [Ignored in Git] This is where the HF dataset downloads to
├── reproduce.py           # Master automation script for researchers
└── REPRODUCIBILITY.md     # Step-by-step setup guide
\\\

## 🚀 Quickstart
Please refer to [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for full instructions on setting up Docker, pulling the dataset from Hugging Face, and executing the statistical models.

## 📄 License
*   **Code:** MIT License
*   **Dataset:** CC-BY-4.0
