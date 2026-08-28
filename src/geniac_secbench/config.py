"""
GenIaC-SecBench — single source of truth for repository paths.

Every phase script imports PATHS from here instead of re-deriving the
project root with `Path(__file__).resolve().parent.parent.parent`.
That pattern broke silently after the src/ reorganization (scripts moved
one directory deeper, so the old code resolved into src/data instead of
<repo_root>/data) — every downstream statistics script failed to find its
input files. This module exists so that class of bug cannot recur: change
the layout once, here, and every script picks it up.

Resolution order for the repo root:
1. GENIAC_ROOT environment variable, if set (for CI / non-standard layouts)
2. Walk up from this file until a directory containing both `data/` and
   `docs/` is found (works regardless of how deep a script is nested)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _find_repo_root() -> Path:
    env_root = os.environ.get("GENIAC_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if not p.exists():
            raise FileNotFoundError(f"GENIAC_ROOT={env_root} does not exist")
        return p

    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "data").is_dir() and (candidate / "docs").is_dir():
            return candidate

    raise RuntimeError(
        "Could not locate the GenIaC-SecBench repo root (looked for a "
        "directory containing both data/ and docs/). Set GENIAC_ROOT "
        "explicitly if the repo has been relocated or vendored."
    )


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def generated(self) -> Path:
        return self.data / "generated"

    @property
    def scan_results(self) -> Path:
        return self.data / "scan_results"

    @property
    def prompts(self) -> Path:
        return self.data / "prompts"

    @property
    def human_reference_dataset(self) -> Path:
        return self.data / "human_reference_dataset"

    @property
    def human_reviews(self) -> Path:
        return self.data / "human_reviews"

    @property
    def summary_reports(self) -> Path:
        return self.data / "summary_reports"

    @property
    def figures(self) -> Path:
        return self.data / "figures"

    @property
    def paper_figures(self) -> Path:
        return self.root / "paper" / "figures"

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def third_party(self) -> Path:
        return self.root / "third_party"


PATHS = Paths(root=_find_repo_root())


if __name__ == "__main__":
    # Quick sanity check: `python -m geniac_secbench.config`
    print(f"repo root       : {PATHS.root}")
    print(f"data/           : {PATHS.data}  (exists={PATHS.data.exists()})")
    print(f"summary_reports/: {PATHS.summary_reports}  (exists={PATHS.summary_reports.exists()})")
