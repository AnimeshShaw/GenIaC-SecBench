"""
GenIaC-SecBench - Smoke Tests
================================
Not a full test suite -- these exist to catch the specific class of bug
that motivated this project's Aug 2026 remediation: a phase script that
looks fine but silently can't find its own input/output paths once
invoked from somewhere other than the exact directory its author happened
to be sitting in. Every phase script here must import cleanly and resolve
its paths correctly regardless of cwd.

Run with: pytest tests/ -v   (or just `python tests/test_smoke.py`)
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PHASE_MODULES = [
    "geniac_secbench.config",
    "geniac_secbench.cli",
    "geniac_secbench.phase1_generation.generate_iac",
    "geniac_secbench.phase1_generation.orchestrator",
    "geniac_secbench.phase1_generation.slm_orchestrator",
    "geniac_secbench.phase2_validation.validate_iac",
    "geniac_secbench.phase3_scanning.run_scanners",
    "geniac_secbench.phase3_scanning.parse_results",
    "geniac_secbench.phase4_structural.extract_metrics",
    "geniac_secbench.phase4_structural.extract_human_metrics",
    "geniac_secbench.phase4_structural.ks_test",
    "geniac_secbench.phase4_structural.ks_test_human",
    "geniac_secbench.phase6_statistics.build_master_table",
    "geniac_secbench.phase6_statistics.friedman_test",
    "geniac_secbench.phase6_statistics.nb_glmm",
    "geniac_secbench.phase8_reporting.visualize_final",
]


@pytest.mark.parametrize("module_name", PHASE_MODULES)
def test_module_imports_cleanly(module_name):
    """Every phase script must be importable without executing its main()
    logic (i.e. its module-level code must not assume argv or cwd)."""
    importlib.import_module(module_name)


def test_config_resolves_root_from_any_cwd(tmp_path):
    """This is the exact bug class that broke every Phase 4/6 script after
    the src/ reorganization: path resolution silently pointing at the
    wrong directory. Verify PATHS.root is correct when invoked from a
    directory that has nothing to do with the repo."""
    result = subprocess.run(
        [sys.executable, "-m", "geniac_secbench.config"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert str(REPO_ROOT) in result.stdout
    assert "exists=True" in result.stdout


def test_config_paths_point_at_real_directories():
    from geniac_secbench.config import PATHS

    assert PATHS.root == REPO_ROOT
    assert PATHS.data.is_dir()
    assert PATHS.docs.is_dir()
    assert PATHS.prompts.is_dir()


def test_cli_module_is_invocable():
    """`python -m geniac_secbench.cli --help` must not crash -- this is
    the entry point REPRODUCIBILITY.md tells third parties to run."""
    result = subprocess.run(
        [sys.executable, "-m", "geniac_secbench.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--phase" in result.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
