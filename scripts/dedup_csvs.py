import sys
import pandas as pd
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

csvs = {
    PATHS.summary_reports / 'schema_validity.csv': ['dataset', 'model', 'scenario_id', 'tool'],
    PATHS.summary_reports / 'findings_raw.csv': ['dataset_type', 'model', 'scenario_id', 'scanner', 'rule_id'],
    PATHS.summary_reports / 'structural_metrics.csv': ['dataset', 'model', 'scenario_id', 'file_name']
}

for fp, subset in csvs.items():
    if Path(fp).exists():
        try:
            df = pd.read_csv(fp)
            initial = len(df)
            df.drop_duplicates(subset=subset, keep='last', inplace=True)
            final = len(df)
            df.to_csv(fp, index=False)
            logger.info(f"Deduplicated {fp}: {initial} -> {final} rows")
        except Exception as e:
            logger.error(f"Error deduplicating {fp}: {e}")
