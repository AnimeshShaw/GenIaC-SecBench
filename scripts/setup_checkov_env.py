"""
GenIaC-SecBench - Checkov Environment Setup
=============================================
Creates an isolated virtual environment for Checkov at `.venv_checkov/`.

Why isolated: Checkov depends on `bc-python-hcl2`, which installs into the
same `hcl2` import namespace as the vanilla `python-hcl2` package (needed by
this project's structural-metrics scripts, which parse modern Terraform
syntax that bc-python-hcl2's older grammar cannot handle). Installing both
into one environment means whichever was installed most recently silently
shadows the other -- this broke Checkov entirely during development (see
docs/THREATS_TO_VALIDITY.md). Isolating Checkov's dependency tree avoids the
conflict without pinning either package to a version that can't do its job.

This is a local-development convenience only -- the Docker image installs
Checkov directly with no conflicting hcl2 package present, so it does not
need this isolation and `run_scanners.py` falls back to a plain PATH lookup
for `checkov` when `.venv_checkov/` doesn't exist.

Usage:
    python scripts/setup_checkov_env.py
"""

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv_checkov"


def main():
    if VENV_DIR.exists():
        print(f"{VENV_DIR} already exists. Delete it first to recreate.")
    else:
        print(f"Creating venv at {VENV_DIR} ...")
        venv.EnvBuilder(with_pip=True).create(str(VENV_DIR))

    venv_python = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    print("Installing checkov into the isolated venv ...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--quiet", "checkov"], check=True)

    result = subprocess.run(
        [str(venv_python), "-m", "checkov.main", "--version"],
        capture_output=True, text=True, check=True,
    )
    print(f"Checkov {result.stdout.strip()} installed and verified at {venv_python}")
    print(
        "\nNOTE: invoke checkov as `<venv_python> -m checkov.main`, not via the "
        "checkov/checkov.cmd shim -- on Windows that shim searches PATH for a "
        "python interpreter and can silently re-exec against the wrong "
        "environment. run_scanners.py already does this correctly."
    )


if __name__ == "__main__":
    main()
