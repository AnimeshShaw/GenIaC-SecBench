"""
GenIaC-SecBench - Phase 0: prompt security-prescriptiveness classification
===========================================================================

Classifies every benchmark scenario by whether its prompt *prescribes a security
state*, and releases the result as a first-class artifact so the classification
is auditable rather than asserted.

Why this exists
---------------
The first release of this benchmark described its prompts as functional-only and
interpreted the resulting scanner findings as model-default security posture.
That description was wrong. An external audit by Lokesh Chauhan (IaC-Guard-V,
QRS 2026) established that the majority of prompts explicitly request a security
state, and that 84.12% of simple-stratum findings come from prompts that
*asked for* the insecure configuration.

The finding reproduced exactly against our own artifacts. For a prompt such as
"Deploy an EC2 instance with a public IP and open SSH port", a resulting
"unrestricted ingress" finding measures instruction-following, not an unprompted
default. That is a different quantity, and conflating the two was a genuine
interpretation error.

Three classes
-------------
- ``insecure_prescriptive`` - the prompt explicitly requests a state that policy
  engines flag (public bucket, open SSH, cluster-admin binding, no resource
  limits, unauthenticated invocation).
- ``secure_prescriptive`` - the prompt explicitly requests a protective control
  (private, encrypted, least-privilege, TLS, CMEK, WAF).
- ``functional_only`` - the prompt specifies topology or functionality without
  prescribing either direction.

Design notes
------------
Classification is **rule-based and deterministic**, not model-assisted: a
model-assigned label would itself need auditing, which defeats the purpose. The
rules are conservative in the direction that *weakens* our own headline: when a
prompt is ambiguous, it is not counted as insecure_prescriptive, so the
insecure class is a lower bound and the "excluding insecure" sensitivity
analysis is not flattered by aggressive labelling.

A prompt matching both directions resolves to ``insecure_prescriptive``, since
an explicitly requested insecure state dominates a co-occurring protective one
for the purposes of interpreting a finding.

Usage:
    python -m geniac_secbench.phase0_prompts.classify_prompts
"""

import re
import sys
import json
import logging
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geniac_secbench.config import PATHS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUT_CSV = PATHS.summary_reports / "prompt_classification.csv"
OUT_JSON = PATHS.summary_reports / "prompt_classification_summary.json"

# Explicit requests for a state that policy engines flag. Each entry is a
# regex plus the control it bears on, so a reader can check the mapping.
INSECURE_PATTERNS = [
    (r"\bpublic\b(?!.*\bprivate\b)",          "public exposure"),
    (r"\bpublicly\b",                          "public exposure"),
    (r"open SSH|open security group|port 22",  "unrestricted ingress"),
    (r"accessible from anywhere|from all networks|exposed to the internet",
                                               "unrestricted ingress"),
    (r"accessible to allUsers|allow(?:ing)? (?:everyone|all)\b",
                                               "unrestricted access"),
    (r"allows? all ingress|all inbound traffic", "unrestricted ingress"),
    (r"unauthenticated|without authorization|without authentication",
                                               "missing authn/authz"),
    (r"AdministratorAccess|cluster-admin|Project Editor|admin user enabled",
                                               "over-privileged identity"),
    (r"\broot\b|privileged|hostNetwork|docker\.sock|host path",
                                               "container privilege"),
    (r"without (?:any )?resource limits|no resource limits",
                                               "missing resource limits"),
    (r"non-HTTPS|HTTP \(non-HTTPS\)|without TLS|no encryption|unencrypted",
                                               "missing encryption/TLS"),
    (r"legacy ABAC|without VNet|without restricting",
                                               "weakened control"),
    (r"0\.0\.0\.0/0|NodePort service on all interfaces",
                                               "unrestricted ingress"),
]

# Explicit requests for a protective control.
SECURE_PATTERNS = [
    (r"\bprivate\b",                              "private/restricted"),
    (r"encrypt(?:ed|ion)|CMEK|KMS|customer[- ]managed key",
                                                  "encryption"),
    (r"versioning enabled|logging enabled|audit",  "logging/retention"),
    (r"least[- ]privilege|scoped|restricted",      "least privilege"),
    (r"\bTLS\b|\bmTLS\b|HTTPS only",               "transport security"),
    (r"\bWAF\b|firewall|NetworkPolicy restricting", "network control"),
    (r"private endpoint|VPC Service Controls|service endpoint",
                                                  "private networking"),
    (r"\bMFA\b|managed identity|Workload Identity", "strong identity"),
]


def classify(text: str):
    """Return (label, matched_controls). Insecure dominates when both match."""
    ins = sorted({c for p, c in INSECURE_PATTERNS if re.search(p, text, re.I)})
    sec = sorted({c for p, c in SECURE_PATTERNS if re.search(p, text, re.I)})
    if ins:
        return "insecure_prescriptive", ins
    if sec:
        return "secure_prescriptive", sec
    return "functional_only", []


def main():
    rows = []
    for fname, stratum in (("scenarios.json", "simple"),
                           ("scenarios_complex.json", "complex")):
        path = PATHS.prompts / fname
        if not path.exists():
            logger.warning("missing %s - run download_dataset.py first", path)
            continue
        for s in json.loads(path.read_text(encoding="utf-8")):
            label, controls = classify(s["prompt"])
            rows.append({
                "scenario_id": s["id"],
                "stratum": stratum,
                "provider": s.get("provider", ""),
                "tool": s.get("tool", ""),
                "prompt_class": label,
                "matched_controls": "; ".join(controls),
                "prompt": s["prompt"],
            })

    if not rows:
        logger.error("no scenarios found")
        sys.exit(1)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    summary = {
        "_schema": "geniac-secbench/prompt-classification/v1",
        "method": "deterministic rule-based; conservative toward NOT labelling "
                  "insecure, so the insecure class is a lower bound",
        "n_scenarios": len(df),
        "by_class": df.prompt_class.value_counts().to_dict(),
        "by_stratum_class": {
            st: g.prompt_class.value_counts().to_dict()
            for st, g in df.groupby("stratum")
        },
    }

    # Attribute findings to prompt class -- the quantity that matters for
    # interpretation, and the number the external audit reported.
    fpath = PATHS.summary_reports / "findings_raw.csv"
    if fpath.exists():
        f = pd.read_csv(fpath, encoding="utf-8-sig")
        if "status" in f.columns:
            f = f[f.status == "FAILED"]
        cls = dict(zip(df.scenario_id, df.prompt_class))
        f = f.copy()
        f["prompt_class"] = f.scenario_id.map(cls)
        per = {}
        for st, g in f.groupby("dataset_type"):
            counts = g.prompt_class.value_counts().to_dict()
            total = int(sum(counts.values()))
            per[st] = {
                "total_findings": total,
                "by_class": {k: int(v) for k, v in counts.items()},
                "pct_from_insecure_prescriptive": round(
                    100 * counts.get("insecure_prescriptive", 0) / max(total, 1), 2),
            }
        summary["findings_attribution"] = per

    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("Prompt classification (n=%d)", len(df))
    for k, v in df.prompt_class.value_counts().items():
        logger.info("  %-24s %3d", k, v)
    logger.info("")
    for st, g in df.groupby("stratum"):
        logger.info("  [%s]", st)
        for k, v in g.prompt_class.value_counts().items():
            logger.info("     %-22s %3d", k, v)
    if "findings_attribution" in summary:
        logger.info("")
        for st, d in summary["findings_attribution"].items():
            logger.info("  [%s] %d findings, %.2f%% from insecure-prescriptive prompts",
                        st, d["total_findings"], d["pct_from_insecure_prescriptive"])
    logger.info("\nWrote %s and %s", OUT_CSV, OUT_JSON)


if __name__ == "__main__":
    main()
