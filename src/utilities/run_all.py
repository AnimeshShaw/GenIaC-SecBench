import os
import subprocess
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS = [
    "claude-3-5-sonnet",
    "claude-opus-4-6",
    "claude-opus-4-6-thinking",
    "gemini-3.1-pro",
    "gemini-3.7-flash",
    "gpt-4o",
    "gpt-5",
    "gpt-5-thinking",
    "llama3",
    "mistral",
    "phi3"
]

DATASETS = ["simple", "complex"]
python_exe = "python" # We'll just use the environment's python

def run_cmd(cmd):
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.returncode == 0

for model in MODELS:
    logger.info(f"--- Processing {model} ---")
    
    # 1. Validation
    for ds in DATASETS:
        run_cmd([python_exe, "src/phase2_validation/validate_iac.py", "--model", model, "--dataset", ds])
    
    # 2. Scanning
    for scanner in ["checkov", "trivy", "kics"]:
        run_cmd([python_exe, "src/phase3_scanning/run_scanners.py", "--scanner", scanner, "--model", model])
        
# 3. Structural Metrics
logger.info("--- Extracting Structural Metrics ---")
run_cmd([python_exe, "src/phase4_structural/extract_metrics.py"])

# 3.5 Deduplicate CSVs
logger.info("--- Deduplicating CSVs ---")
run_cmd([python_exe, "dedup.py"])

# 4. Parse Results
logger.info("--- Parsing Results ---")
run_cmd([python_exe, "src/phase3_scanning/parse_results.py"])

# 5. Visualize
logger.info("--- Generating Plots ---")
if os.path.exists("src/phase8_reporting/visualize_final.py"):
    run_cmd([python_exe, "src/phase8_reporting/visualize_final.py"])
else:
    logger.warning("visualize_final.py not found. Skipping plotting.")

logger.info("--- FULL PIPELINE COMPLETE ---")
