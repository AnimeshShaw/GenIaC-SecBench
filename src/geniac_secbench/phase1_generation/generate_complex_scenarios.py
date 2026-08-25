import json
import litellm
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

load_dotenv()
litellm.drop_params = True

# NOTE: this is a one-time scenario-authoring script, already run to produce
# the frozen 40-scenario complex set in data/prompts/scenarios_complex.json.
# Re-running it calls the LLM again and OVERWRITES that file with a fresh,
# non-reproducible set of scenarios — do not run this as part of `geniac run`.

prompt = """
Generate exactly 40 highly complex, multi-component Infrastructure-as-Code (IaC) deployment scenarios.
These scenarios should be designed to test the limits of frontier LLMs and their ability to produce secure-by-default architectures.
Avoid simple prompts like "Create an S3 bucket". Instead, focus on multi-tier architectures, zero-trust networking, OIDC integrations, service meshes, and cross-region deployments.

Format your response ONLY as a raw JSON array of objects. Do not wrap in markdown ```json blocks. Each object must follow this exact schema:
[
  {
    "id": "complex-aws-tf-001",
    "provider": "AWS",
    "tool": "Terraform",
    "prompt": "Deploy a secure hub-and-spoke network topology using AWS Transit Gateway, with strict NACLs, isolated private subnets for RDS, and a centralized NAT gateway."
  }
]

Distribute the scenarios across:
- Providers: AWS (10), Azure (10), GCP (10), Any/Kubernetes (10)
- Tools: Terraform, CloudFormation, ARM, Kubernetes
"""

print("Asking Claude Opus 4.6 to design the 40 complex scenarios...")
try:
    response = litellm.completion(
        model="anthropic/claude-opus-4-6",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
except Exception as e:
    print(f"Error calling LLM: {e}")
    sys.exit(1)

content = response.choices[0].message.content.strip()

# Clean up markdown
if content.startswith("```json"):
    content = content[7:]
elif content.startswith("```"):
    content = content[3:]
if content.endswith("```"):
    content = content[:-3]

try:
    scenarios = json.loads(content)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}\nRaw output:\n{content}")
    sys.exit(1)

out_path = PATHS.prompts / "scenarios_complex.json"
with open(out_path, "w") as f:
    json.dump(scenarios, f, indent=2)

print(f"Successfully generated {len(scenarios)} complex scenarios in {out_path}")
