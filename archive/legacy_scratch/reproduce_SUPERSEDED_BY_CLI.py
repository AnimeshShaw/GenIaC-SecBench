import argparse
import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_script(script_path):
    logger.info(f"--- Running {script_path} ---")
    if not Path(script_path).exists():
        logger.error(f"Script {script_path} does not exist.")
        sys.exit(1)
        
    result = subprocess.run([sys.executable, script_path], capture_output=False)
    if result.returncode != 0:
        logger.error(f"Script {script_path} failed with exit code {result.returncode}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="InfraSecBench Reproducibility Pipeline")
    parser.add_argument('--all', action='store_true', help='Run the entire pipeline from generation to statistics')
    parser.add_argument('--analyze-only', action='store_true', help='Skip generation and scanning, just run structural extraction and statistics on existing data')
    
    args = parser.parse_args()
    
    if not args.all and not args.analyze_only:
        parser.print_help()
        sys.exit(1)
        
    if args.all:
        logger.info("Executing Full Pipeline...")
        run_script('src/pipeline/01_generation/orchestrator.py')
        run_script('src/pipeline/02_validation/validate_all.py')
        # Assuming run_scanners.py or similar is the entry point
        # For cross-platform we skip powershell scripts in reproduce.py or wrap them.
        logger.warning("Note: Security scanning (Phase 3) uses custom shell/powershell wrappers located in src/pipeline/03_scanning/. Please run those manually or via Docker.")
        
    if args.all or args.analyze_only:
        logger.info("Executing Analysis Pipeline...")
        run_script('src/analysis/04_structural/extract_metrics.py')
        run_script('src/analysis/04_structural/extract_human_metrics.py')
        run_script('src/analysis/04_structural/ks_test.py')
        run_script('src/analysis/04_structural/ks_test_human.py')
        run_script('src/analysis/05_llm_judge/judge.py')
        run_script('src/analysis/06_statistics/glmm_analysis.py')
        run_script('src/analysis/06_statistics/friedman_test.py')
        
    logger.info("Pipeline Execution Complete!")

if __name__ == '__main__':
    main()
