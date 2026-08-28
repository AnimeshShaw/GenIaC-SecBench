"""
Upload the GenIaC-SecBench dataset to Hugging Face Hub.

Mirrors `download_dataset.py`: whatever this uploads, that script restores into
`data/`, so a third party can reproduce every table and figure by downloading and
running `python -m geniac_secbench.cli --phase analyze`.

Safety properties, in order of importance:

1. **Nothing is uploaded that is not on an explicit allow-list.** The payload is
   built by naming directories to include, never by excluding from a wildcard.
   `data/human_reviews/REVIEWER_KEY_local_only.csv` maps anonymized rater ids
   (R1-R3) to real names, emails, and LinkedIn profiles; it is the only copy of
   that mapping and must never leave the machine. A deny-list would ship it the
   moment someone adds a file the pattern didn't anticipate.
2. **A hard assertion, not just a filter.** Even inside the allow-list, any file
   matching a forbidden pattern aborts the upload. Belt and braces, because the
   failure mode is irreversible: once a secret is pushed to a public repo it
   must be treated as disclosed regardless of later deletion.
3. **Dry-run by default.** `--dry-run` prints the exact manifest and totals so a
   human can inspect it before `--push` sends anything.

Usage:
    python scripts/upload_dataset.py --dry-run
    python scripts/upload_dataset.py --push
"""

import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geniac_secbench.config import PATHS

REPO_ID = "AnimeshShaw/GenIaC-SecBench"

# Explicit allow-list. Order matches the pipeline phases that consume them.
INCLUDE_DIRS = [
    "prompts",                  # Phase 1 input: the 100 benchmark scenarios
    "generated",                # Phase 1 output: 1,196 model-generated artifacts
    "scan_results",             # Phase 3: raw Checkov/Trivy/KICS JSON per scenario
    "human_reference_dataset",  # Phase 4: 634-file human corpus (as fetched)
    "scan_results_human",       # Phase 3b: same scanners over the human corpus
    "summary_reports",          # Phases 3-8: every derived table the paper cites
    "figures",                  # Phase 8: publication figures
]
INCLUDE_FILES = [
    "generation_usage.jsonl",   # per-generation token usage (reasoning-token analysis)
    "batch_jobs.json",          # Message Batches submitted, for provenance
]
# Individually named rater files -- NOT the whole human_reviews directory.
INCLUDE_GLOBS = [
    ("human_reviews", "human_review_R*.csv"),
    ("human_reviews", "grok_judge_answer_key.csv"),
    ("human_reviews", "review_template_blank.csv"),
]

# Any match aborts the upload outright.
FORBIDDEN = ["REVIEWER_KEY", "_local_only", ".env", "id_rsa", "credentials"]

# Excluded by design (not secret, just not part of the release):
#   _archive_v1/  -- pre-remediation artifacts kept locally for provenance.
#                    Publishing them invites citation of superseded numbers.


def collect():
    root = PATHS.data
    files = []
    for d in INCLUDE_DIRS:
        p = root / d
        if not p.is_dir():
            print(f"  WARNING: {d}/ not found, skipping")
            continue
        files += [f for f in p.rglob("*") if f.is_file()]
    for f in INCLUDE_FILES:
        p = root / f
        if p.is_file():
            files.append(p)
    for d, pattern in INCLUDE_GLOBS:
        files += [f for f in (root / d).glob(pattern) if f.is_file()]

    # Transient scanner/provider caches can reappear between runs; never ship them.
    files = [f for f in files
             if ".terraform" not in f.parts and ".git" not in f.parts]
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser(description="Upload GenIaC-SecBench data to Hugging Face.")
    ap.add_argument("--repo-id", default=REPO_ID)
    ap.add_argument("--dry-run", action="store_true", help="Print the manifest, upload nothing.")
    ap.add_argument("--push", action="store_true", help="Actually upload.")
    ap.add_argument("--private", action="store_true", help="Create the repo as private.")
    args = ap.parse_args()

    if not (args.dry_run or args.push):
        ap.error("pass --dry-run to preview or --push to upload")

    files = collect()
    root = PATHS.data

    violations = [f for f in files if any(bad in f.name or bad in str(f) for bad in FORBIDDEN)]
    if violations:
        print("ABORT: forbidden files matched the payload:")
        for v in violations:
            print("   ", v)
        sys.exit(1)

    total = sum(f.stat().st_size for f in files)
    by_dir = {}
    for f in files:
        key = f.relative_to(root).parts[0]
        e = by_dir.setdefault(key, [0, 0])
        e[0] += 1
        e[1] += f.stat().st_size

    print(f"\nRepo:  {args.repo_id}  (dataset)")
    print(f"Files: {len(files):,}    Total: {total/1e6:,.1f} MB\n")
    print(f"  {'path':<28}{'files':>8}{'size':>12}")
    print("  " + "-" * 48)
    for k in sorted(by_dir):
        n, sz = by_dir[k]
        print(f"  {k:<28}{n:>8,}{sz/1e6:>10,.1f} MB")
    print("  " + "-" * 48)
    print(f"  {'TOTAL':<28}{len(files):>8,}{total/1e6:>10,.1f} MB")
    print("\nEXCLUDED by design:")
    print("  data/_archive_v1/                pre-remediation artifacts (provenance only)")
    print("  REVIEWER_KEY_local_only.csv      reviewer identities -- never distributed")
    print("  .terraform/, .git/               transient caches")

    if args.dry_run:
        print("\n[DRY RUN] Nothing uploaded. Re-run with --push to upload.")
        return

    from huggingface_hub import HfApi
    api = HfApi()
    who = api.whoami()
    print(f"\nAuthenticated as: {who['name']}")

    api.create_repo(repo_id=args.repo_id, repo_type="dataset",
                    private=args.private, exist_ok=True)
    print(f"Repo ready: https://huggingface.co/datasets/{args.repo_id}")

    card = PATHS.root / "docs" / "DATASET_CARD.md"
    if card.exists():
        api.upload_file(path_or_fileobj=str(card), path_in_repo="README.md",
                        repo_id=args.repo_id, repo_type="dataset")
        print("Uploaded dataset card -> README.md")

    print("Uploading data/ ...")
    api.upload_folder(
        folder_path=str(root),
        repo_id=args.repo_id,
        repo_type="dataset",
        # allow_patterns mirrors the allow-list above; ignore_patterns is a second
        # barrier so a mistake in either one alone cannot leak the reviewer key.
        allow_patterns=[f"{d}/**" for d in INCLUDE_DIRS]
                       + INCLUDE_FILES
                       + [f"{d}/{p}" for d, p in INCLUDE_GLOBS],
        ignore_patterns=["**/.terraform/**", "**/.git/**", "_archive_v1/**",
                         "**/REVIEWER_KEY*", "**/*_local_only*"],
        commit_message="Add GenIaC-SecBench benchmark data",
    )
    print(f"\nDone: https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
