"""
GenIaC-SecBench - Third-Party Scanner Setup
==============================================
Fetches the scanner/validator binaries that live under third_party/ but are
gitignored (large, platform-specific, independently versioned upstream):

- KICS (Checkmarx)     -> third_party/kics/
- ARM-TTK (Microsoft)  -> third_party/arm-ttk/

Trivy and Checkov are installed via package managers instead (see
REPRODUCIBILITY.md and scripts/setup_checkov_env.py) -- they're not vendored
here because they have proper cross-platform installers already.

Usage:
    python third_party/install.py
    python third_party/install.py --only kics
"""

import argparse
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent

# Pin exact versions so a fresh install matches what this benchmark's
# results were produced with -- bump deliberately, not by accident.
KICS_VERSION = "v2.1.5"
ARM_TTK_REF = "master"  # Microsoft doesn't tag ARM-TTK releases; pin a commit here if strict reproducibility matters


def install_kics():
    dest = ROOT / "kics"
    if dest.exists():
        print(f"{dest} already exists, skipping.")
        return

    system = platform.system()
    arch = "x86_64" if platform.machine().endswith("64") else platform.machine()
    asset_map = {
        "Windows": f"kics_{KICS_VERSION.lstrip('v')}_windows_x64.zip",
        "Linux": f"kics_{KICS_VERSION.lstrip('v')}_linux_x64.tar.gz",
        "Darwin": f"kics_{KICS_VERSION.lstrip('v')}_darwin_x64.tar.gz",
    }
    if system not in asset_map:
        print(f"Unsupported platform for automated KICS install: {system}. "
              f"Download manually from https://github.com/Checkmarx/kics/releases/{KICS_VERSION}")
        return

    asset = asset_map[system]
    url = f"https://github.com/Checkmarx/kics/releases/download/{KICS_VERSION}/{asset}"
    dest.mkdir(parents=True)
    archive_path = dest / asset
    print(f"Downloading {url} ...")
    urlretrieve(url, archive_path)

    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest)
    else:
        subprocess.run(["tar", "-xzf", str(archive_path), "-C", str(dest)], check=True)
    archive_path.unlink()
    print(f"KICS installed to {dest}")


def install_arm_ttk():
    dest = ROOT / "arm-ttk"
    if dest.exists():
        print(f"{dest} already exists, skipping.")
        return
    print(f"Cloning ARM-TTK ({ARM_TTK_REF}) ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ARM_TTK_REF,
         "https://github.com/Azure/arm-ttk.git", str(dest)],
        check=True,
    )
    # Detach from the upstream .git history -- this must NOT become a
    # tracked submodule/gitlink inside this repo (that was a bug in the
    # pre-remediation state: tools/arm-ttk was a broken gitlink with no
    # .gitmodules entry, which left an empty directory on fresh clone).
    shutil.rmtree(dest / ".git", ignore_errors=True)
    print(f"ARM-TTK installed to {dest}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["kics", "arm-ttk"], default=None)
    args = parser.parse_args()

    if args.only in (None, "kics"):
        install_kics()
    if args.only in (None, "arm-ttk"):
        install_arm_ttk()

    print(
        "\nDone. Trivy and Checkov are not installed by this script -- see "
        "REPRODUCIBILITY.md (Trivy via package manager) and "
        "scripts/setup_checkov_env.py (Checkov, isolated venv)."
    )


if __name__ == "__main__":
    main()
