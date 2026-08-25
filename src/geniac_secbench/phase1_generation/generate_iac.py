"""
InfraSecBench - IaC Code Generation via LLM APIs
=================================================
Prompts frontier LLMs with deployment scenarios and saves the generated
Infrastructure-as-Code (Terraform, CloudFormation, ARM, Kubernetes YAML).

Usage:
    python src/generate_iac.py                    # Run all models, all scenarios
    python src/generate_iac.py --model gpt-5      # Run a single model
    python src/generate_iac.py --dry-run           # Preview prompts without calling APIs
"""

import os
import sys
import json
import argparse
import logging
import re
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

load_dotenv()

try:
    import litellm
    from tqdm import tqdm
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)

# Configure litellm to drop unsupported parameters for newer models
litellm.drop_params = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------
# Each entry maps a short human-readable name to the litellm model string.
# Update these as newer model versions are released or API identifiers change.
# ---------------------------------------------------------------------------
MODEL_REGISTRY = {
    # Frontier
    "gpt-5": "openai/gpt-5",
    "gpt-5-thinking": "openai/gpt-5",
    "claude-opus-4-6": "anthropic/claude-opus-4-6",
    "claude-opus-4-6-thinking": "anthropic/claude-opus-4-6",
    # Upcoming
    "claude-opus-5": "anthropic/claude-opus-5",
    # Gemini
    "gemini-3.7-flash": "gemini/gemini-3.7-flash",
    "gemini-3.1-pro": "gemini/gemini-3.1-pro-preview",
    # Baselines
    "gpt-4o": "openai/gpt-4o",
    "claude-3-5-sonnet": "anthropic/claude-sonnet-4-6",
}

# ---------------------------------------------------------------------------
# Prompt Engineering
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a senior cloud infrastructure engineer. "
    "When asked, you produce production-ready Infrastructure-as-Code. "
    "Return ONLY the raw code inside a single fenced code block "
    "(```hcl, ```yaml, ```json as appropriate). "
    "Do NOT include any explanation, commentary, or markdown outside the code block."
)


def build_user_prompt(scenario: dict) -> str:
    """Construct the user-facing prompt from a scenario entry."""
    tool = scenario["tool"]
    provider = scenario["provider"]
    task = scenario["prompt"]

    tool_hint = {
        "Terraform": "Write Terraform HCL code (.tf)",
        "CloudFormation": "Write an AWS CloudFormation YAML template",
        "ARM": "Write an Azure Resource Manager (ARM) JSON template",
        "Kubernetes": "Write a Kubernetes YAML manifest",
    }.get(tool, f"Write {tool} code")

    provider_hint = f" for {provider}" if provider != "Any" else ""

    return f"{tool_hint}{provider_hint} to: {task}"


# ---------------------------------------------------------------------------
# Code Extraction
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.DOTALL)


def extract_code_block(response_text: str) -> str:
    """Pull the first fenced code block out of an LLM response."""
    match = _CODE_BLOCK_RE.search(response_text)
    if match:
        return match.group(1).strip()
    # Fallback: return the whole response (model didn't use fences)
    return response_text.strip()


# ---------------------------------------------------------------------------
# File Extension Mapping
# ---------------------------------------------------------------------------

TOOL_EXTENSIONS = {
    "Terraform": "tf",
    "CloudFormation": "yaml",
    "ARM": "json",
    "Kubernetes": "yaml",
}


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def generate(
    scenarios: list[dict],
    models: dict[str, str],
    output_root: Path,
    dry_run: bool = False,
    temperature: float = 0.2,
):
    """
    For each (model, scenario) pair, call the LLM and persist the code.

    Already-generated files are skipped so the pipeline is idempotent.
    """
    total = len(models) * len(scenarios)
    logger.info("Starting generation: %d models × %d scenarios = %d calls", len(models), len(scenarios), total)

    for model_label, model_id in models.items():
        logger.info("── Model: %s (%s)", model_label, model_id)
        model_dir = output_root / model_label

        for scenario in tqdm(scenarios, desc=model_label, unit="scenario"):
            sid = scenario["id"]
            ext = TOOL_EXTENSIONS.get(scenario["tool"], "txt")
            out_dir = model_dir / sid
            out_file = out_dir / f"main.{ext}"

            if out_file.exists():
                continue  # idempotent skip

            user_prompt = build_user_prompt(scenario)

            if dry_run:
                logger.info("[DRY-RUN] %s / %s → %s", model_label, sid, user_prompt[:80])
                continue

            is_thinking = model_label.endswith("-thinking")
            kwargs = {"temperature": temperature}
            system_prompt = SYSTEM_PROMPT
            
            if is_thinking:
                if "openai" in model_id:
                    kwargs["reasoning_effort"] = "high"
                else:
                    system_prompt += "\n\nCRITICAL: Think step-by-step and write out your reasoning in detail before outputting the final code block."

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    response = litellm.completion(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        **kwargs
                    )
                    content = response.choices[0].message.content
                    code = extract_code_block(content)

                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(code, encoding="utf-8")
                    break  # Success, exit the retry loop

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning("Attempt %d failed for %s / %s: %s. Retrying in 15s...", attempt + 1, model_label, sid, e)
                        import time
                        time.sleep(15)
                    else:
                        logger.error("FAILED completely %s / %s after %d attempts: %s", model_label, sid, max_retries, e)

    logger.info("Generation complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="InfraSecBench – IaC generation via LLMs")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Run a single model by its short name (e.g. 'gpt-5'). Default: all models.",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default=str(PATHS.prompts / "scenarios.json"),
        help="Path to scenarios JSON file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PATHS.generated),
        help="Root directory for generated code.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for LLM calls.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview prompts without calling APIs.")
    args = parser.parse_args()

    # Load scenarios
    scenarios_path = Path(args.scenarios)
    if not scenarios_path.exists():
        logger.error("Scenarios file not found: %s", scenarios_path)
        sys.exit(1)
    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    logger.info("Loaded %d scenarios from %s", len(scenarios), scenarios_path)

    # Select models
    if args.model:
        if args.model not in MODEL_REGISTRY:
            logger.error("Unknown model '%s'. Available: %s", args.model, list(MODEL_REGISTRY.keys()))
            sys.exit(1)
        models = {args.model: MODEL_REGISTRY[args.model]}
    else:
        models = MODEL_REGISTRY

    # Extract dataset name (e.g., 'scenarios_complex' -> 'complex', 'scenarios' -> 'simple')
    scenarios_path = Path(args.scenarios)
    dataset_name = scenarios_path.stem.replace("scenarios_", "").replace("scenarios", "simple")
    if not dataset_name:
        dataset_name = "simple"
        
    out_dir = Path(args.output) / dataset_name

    generate(
        scenarios=scenarios,
        models=models,
        output_root=out_dir,
        dry_run=args.dry_run,
        temperature=args.temperature,
    )


if __name__ == "__main__":
    main()
