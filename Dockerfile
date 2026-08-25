FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    git \
    tar \
    jq \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Checkov is installed into an ISOLATED venv, not the main image environment.
# Reason: checkov depends on bc-python-hcl2, which installs into the same
# `hcl2` import namespace as the vanilla python-hcl2 pinned in
# requirements.txt (needed by the structural-metrics scripts to parse modern
# Terraform syntax that bc-python-hcl2's older grammar rejects). Installing
# both into the same environment means whichever installs LAST silently
# shadows the other's files in site-packages/hcl2/ -- if requirements.txt
# were installed after this step in one shared env, it would overwrite
# checkov's hcl2 dependency and break checkov's Terraform/CloudFormation
# runners at import time. See docs/THREATS_TO_VALIDITY.md and
# scripts/setup_checkov_env.py for the same issue in local dev.
RUN python -m venv /opt/venv_checkov && \
    /opt/venv_checkov/bin/pip install --no-cache-dir checkov

# Install Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Install KICS
RUN curl -sfL 'https://raw.githubusercontent.com/Checkmarx/kics/master/install.sh' | bash

WORKDIR /app

# Install Python requirements into the main image environment (pandas,
# scipy, statsmodels, matplotlib, python-hcl2, etc.) -- deliberately
# separate from /opt/venv_checkov above.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

# Point run_scanners.py at the isolated checkov venv created above (it
# otherwise looks for ./.venv_checkov relative to the repo root, which is
# the local-dev convention set up by scripts/setup_checkov_env.py).
ENV GENIAC_CHECKOV_VENV=/opt/venv_checkov

# Set environment variable for execution
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "geniac_secbench.cli"]
