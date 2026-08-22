FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    git \
    tar \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Checkov
RUN pip install --no-cache-dir checkov

# Install Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Install KICS
RUN curl -sfL 'https://raw.githubusercontent.com/Checkmarx/kics/master/install.sh' | bash

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

# Set environment variable for execution
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "reproduce.py"]
