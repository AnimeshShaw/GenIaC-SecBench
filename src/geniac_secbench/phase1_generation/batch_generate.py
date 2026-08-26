"""
GenIaC-SecBench - Batch generation via the Anthropic Message Batches API
=========================================================================

Same generation contract as `generate_iac.py`, but submitted asynchronously
through the Message Batches API at **50% of standard token cost**. Used for the
expensive arms (complex scenarios on Opus produce ~20k output tokens each), where
latency does not matter and the discount does.

Differences from the synchronous path, all deliberate:

- **Anthropic SDK direct, not litellm.** litellm has no first-class batches
  binding; the batches surface is `client.messages.batches.*`.
- **Results arrive in ANY order.** They are keyed by `custom_id`
  (`"<dataset>__<scenario_id>"`), never by position -- indexing by order silently
  misattributes generated code to the wrong scenario, which would be invisible
  downstream and would corrupt every per-scenario join.
- **Idempotent.** Only scenarios missing an output file are submitted, so a
  half-finished batch (or an exhausted credit balance) is resumed by re-running
  rather than restarted.

Usage:
    python -m geniac_secbench.phase1_generation.batch_generate \
        --model claude-opus-4-6-thinking --scenarios scenarios_complex.json --estimate
    python -m geniac_secbench.phase1_generation.batch_generate \
        --model claude-opus-4-6-thinking --scenarios scenarios_complex.json --submit
    python -m geniac_secbench.phase1_generation.batch_generate --collect <batch_id>
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

from dotenv import load_dotenv
load_dotenv(PATHS.root / ".env")

import anthropic

from geniac_secbench.phase1_generation.generate_iac import (
    MODEL_REGISTRY, SYSTEM_PROMPT, TOOL_EXTENSIONS,
    THINKING_BUDGET_TOKENS, MAX_OUTPUT_TOKENS, REASONING_EFFORT,
    build_user_prompt, extract_code_block, _record_usage,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

BATCH_STATE = PATHS.data / "batch_jobs.json"

# Batch pricing is 50% of standard. Opus 4.6: $5/$25 per MTok -> $2.50/$12.50.
PRICING = {
    "anthropic/claude-opus-4-6":   (5.0, 25.0),
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
}
BATCH_DISCOUNT = 0.5

# Output ceiling for adaptive-thinking batch requests. Must exceed
# (template tokens + reasoning tokens); see build_params for why 32k was too low.
BATCH_THINKING_MAX_TOKENS = 64000


def _strip_provider(model_id: str) -> str:
    """litellm ids are 'anthropic/<model>'; the SDK wants the bare model name."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def dataset_name_from(scenarios_filename: str) -> str:
    stem = Path(scenarios_filename).stem
    return stem.replace("scenarios_", "").replace("scenarios", "simple") or "simple"


def pending_scenarios(model_label: str, scenarios_path: Path):
    """Scenarios with no output file yet -- the idempotency contract."""
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    dataset = dataset_name_from(scenarios_path.name)
    out_root = PATHS.generated / dataset / model_label
    pending = []
    for s in scenarios:
        ext = TOOL_EXTENSIONS.get(s["tool"], "txt")
        if not (out_root / s["id"] / f"main.{ext}").exists():
            pending.append(s)
    return pending, dataset


def build_params(model_label: str, model_id: str, scenario: dict, thinking_mode: str) -> dict:
    """Request params mirroring generate_iac.py's reasoning-mode configuration."""
    is_cot = model_label.endswith("-cot")
    is_thinking = model_label.endswith("-thinking")
    system_prompt = SYSTEM_PROMPT
    params = {
        "model": _strip_provider(model_id),
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": build_user_prompt(scenario)}],
    }

    if is_cot:
        system_prompt += ("\n\nCRITICAL: Think step-by-step and write out your reasoning "
                          "in detail before outputting the final code block.")
        params["temperature"] = 0.2
    elif is_thinking:
        if thinking_mode == "adaptive":
            # Current recommended API for Opus 4.6; budget_tokens is deprecated
            # there. Adaptive lets the model size its own reasoning and
            # auto-enables interleaved thinking.
            #
            # max_tokens must cover the TEMPLATE **plus** the reasoning, because
            # adaptive thinking bills and counts thinking as output. Complex
            # scenarios already run ~20k tokens of Terraform on their own, so the
            # earlier 32k ceiling truncated 12 of 31 complex generations
            # (stop_reason=max_tokens); they were refused rather than written,
            # which then showed up downstream as missing rows. Opus 4.6 allows up
            # to 128k output, and batch requests have no HTTP-timeout pressure,
            # so there is no reason to run this close to the edge.
            params["thinking"] = {"type": "adaptive"}
            params["output_config"] = {"effort": REASONING_EFFORT}
            params["max_tokens"] = BATCH_THINKING_MAX_TOKENS
        else:
            # Transitional escape hatch: fixed ceiling. Requires temperature=1
            # and max_tokens > budget_tokens.
            params["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
            params["temperature"] = 1
            params["max_tokens"] = THINKING_BUDGET_TOKENS + MAX_OUTPUT_TOKENS
    else:
        params["temperature"] = 0.2

    params["system"] = system_prompt
    return params


def estimate(model_id: str, n: int, dataset: str) -> float:
    """Rough cost projection from measured medians (see data/generation_usage.jsonl)."""
    med_out = 19562 if dataset == "complex" else 886
    _, out_rate = PRICING.get(model_id, (5.0, 25.0))
    return n * med_out * (out_rate / 1e6) * BATCH_DISCOUNT


def submit(model_label: str, scenarios_path: Path, thinking_mode: str, dry_run: bool):
    if model_label not in MODEL_REGISTRY:
        logger.error("Unknown model %r. Known: %s", model_label, list(MODEL_REGISTRY))
        sys.exit(1)
    model_id = MODEL_REGISTRY[model_label]
    pending, dataset = pending_scenarios(model_label, scenarios_path)

    if not pending:
        logger.info("Nothing pending for %s / %s -- already complete.", model_label, dataset)
        return None

    cost = estimate(model_id, len(pending), dataset)
    logger.info("%s / %s: %d pending. Estimated batch cost ~$%.2f (50%% of standard).",
                model_label, dataset, len(pending), cost)
    if dry_run:
        logger.info("[ESTIMATE ONLY] Not submitting. Re-run with --submit to send.")
        return None

    requests = [
        {"custom_id": f"{dataset}__{s['id']}",
         # custom_id must match ^[a-zA-Z0-9_-]{1,64}$ -- ':' is rejected by the
         # API, and scenario ids already contain '-', so '__' is the separator.
         "params": build_params(model_label, model_id, s, thinking_mode)}
        for s in pending
    ]

    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)
    logger.info("Submitted batch %s (%d requests, status=%s)",
                batch.id, len(requests), batch.processing_status)

    state = json.loads(BATCH_STATE.read_text(encoding="utf-8")) if BATCH_STATE.exists() else {}
    state[batch.id] = {"model_label": model_label, "dataset": dataset,
                       "n_requests": len(requests), "thinking_mode": thinking_mode,
                       "estimated_cost_usd": round(cost, 2)}
    BATCH_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return batch.id


def collect(batch_id: str, poll_seconds: int = 60, wait: bool = True):
    client = anthropic.Anthropic()
    state = json.loads(BATCH_STATE.read_text(encoding="utf-8")) if BATCH_STATE.exists() else {}
    meta = state.get(batch_id, {})
    model_label = meta.get("model_label")
    dataset = meta.get("dataset")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        logger.info("batch %s status=%s counts=%s", batch_id, batch.processing_status,
                    getattr(batch, "request_counts", None))
        if batch.processing_status == "ended" or not wait:
            break
        time.sleep(poll_seconds)

    if batch.processing_status != "ended":
        logger.info("Batch not finished yet; re-run --collect later.")
        return

    scenarios = {}
    for fname in ("scenarios.json", "scenarios_complex.json"):
        for s in json.loads((PATHS.prompts / fname).read_text(encoding="utf-8")):
            scenarios[s["id"]] = s

    written = failed = 0
    for result in client.messages.batches.results(batch_id):
        # Results arrive in arbitrary order -- always key by custom_id.
        cid = result.custom_id
        ds, sid = cid.split("__", 1)
        rtype = result.result.type
        if rtype != "succeeded":
            logger.error("%s: %s", cid, rtype)
            failed += 1
            continue

        msg = result.result.message
        if getattr(msg, "stop_reason", None) == "max_tokens":
            logger.error("%s: truncated (stop_reason=max_tokens) -- not written", cid)
            failed += 1
            continue

        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        code = extract_code_block(text)
        scenario = scenarios.get(sid)
        if scenario is None:
            logger.error("%s: unknown scenario id", cid)
            failed += 1
            continue

        ext = TOOL_EXTENSIONS.get(scenario["tool"], "txt")
        out_dir = PATHS.generated / (dataset or ds) / model_label / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"main.{ext}").write_text(code, encoding="utf-8")
        _record_usage(model_label, sid, getattr(msg, "usage", None))
        written += 1

    logger.info("Collected batch %s: %d written, %d failed.", batch_id, written, failed)


def main():
    ap = argparse.ArgumentParser(description="Generate IaC via the Message Batches API (50%% cost).")
    ap.add_argument("--model")
    ap.add_argument("--scenarios", default="scenarios_complex.json")
    ap.add_argument("--thinking-mode", choices=["adaptive", "budget"], default="adaptive",
                    help="adaptive = current recommended API for Opus 4.6; "
                         "budget = deprecated fixed budget_tokens ceiling.")
    ap.add_argument("--estimate", action="store_true", help="Show cost, do not submit.")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--collect", metavar="BATCH_ID")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        state = json.loads(BATCH_STATE.read_text(encoding="utf-8")) if BATCH_STATE.exists() else {}
        if not state:
            print("No batches submitted yet.")
        client = anthropic.Anthropic()
        for bid, meta in state.items():
            b = client.messages.batches.retrieve(bid)
            print(f"{bid}  {meta['model_label']}/{meta['dataset']}  "
                  f"n={meta['n_requests']}  status={b.processing_status}  "
                  f"counts={getattr(b,'request_counts',None)}")
        return

    if args.collect:
        collect(args.collect, wait=False)
        return

    if not args.model:
        ap.error("--model is required unless using --collect/--status")

    submit(args.model, PATHS.prompts / args.scenarios, args.thinking_mode,
           dry_run=not args.submit)


if __name__ == "__main__":
    main()
