"""
BlastGate Policy Engine Configuration & Payload Factory
Generates validated Boto3 request payloads for CreatePolicyEngine and CreatePolicy.
"""

from pathlib import Path
from typing import Dict, Any

POLICIES_DIR = Path(__file__).resolve().parent
CEDAR_POLICY_FILE = POLICIES_DIR / "cedar_policies.cedar"

APP_PREFIX = "blastgate"
POLICY_ENGINE_NAME = f"{APP_PREFIX}_policy_engine"
POLICY_NAME = f"{APP_PREFIX}_gateway_cedar_policy"

# Target enforcement mode: ACTIVE (enforcing mode).
# In pre-deployment sandbox testing, validationMode FAIL_ON_ANY_FINDINGS runs
# against the deployed Gateway Cedar schema.
ENFORCEMENT_MODE = "ACTIVE"
VALIDATION_MODE = "FAIL_ON_ANY_FINDINGS"


def load_cedar_policy_text() -> str:
    """Loads raw Cedar policy statements from file."""
    with open(CEDAR_POLICY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_create_policy_engine_payload(
    name: str = POLICY_ENGINE_NAME,
    description: str = "BlastGate Cedar Policy Engine for Gateway authorization",
) -> Dict[str, Any]:
    """Generates validated input dictionary for Boto3 CreatePolicyEngine API."""
    return {
        "name": name,
        "description": description,
        "tags": {
            "Project": "BlastGate",
            "Environment": "sandbox",
            "ManagedBy": "AWS-CDK",
        },
    }


def get_create_policy_payload(
    policy_engine_id: str = "pe-placeholder12",
    policy_name: str = POLICY_NAME,
    enforcement_mode: str = ENFORCEMENT_MODE,
    validation_mode: str = VALIDATION_MODE,
) -> Dict[str, Any]:
    """Generates validated input dictionary for Boto3 CreatePolicy API."""
    return {
        "name": policy_name,
        "policyEngineId": policy_engine_id,
        "definition": {
            "cedar": {
                "statement": load_cedar_policy_text()
            }
        },
        "enforcementMode": enforcement_mode,
        "validationMode": validation_mode,
        "description": "Default-deny Cedar policy permitting only get_incident_diagnostics and scoped propose_worker_replacement",
    }
