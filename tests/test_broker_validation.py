"""
BlastGate Broker Input Validation Tests
Verifies strict JSON Schema Draft-07 enforcement, parameter rejection, and boundary constraints.
"""

import pytest
from broker.models import RemediationRequest
from broker.errors import RequestValidationError

VALID_INCIDENT_ID = "inc-0940d012dede2291"
VALID_ACTION_ID = "REPLACE_UNHEALTHY_ECS_WORKER"
VALID_TASK_ARN = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8"


def test_valid_request_passes():
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": VALID_ACTION_ID,
        "target_task_arn": VALID_TASK_ARN,
    }
    req = RemediationRequest.from_dict(payload)
    assert req.incident_id == VALID_INCIDENT_ID
    assert req.action_id == VALID_ACTION_ID
    assert req.target_task_arn == VALID_TASK_ARN


@pytest.mark.parametrize("missing_field", ["incident_id", "action_id", "target_task_arn"])
def test_missing_required_fields_rejected(missing_field):
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": VALID_ACTION_ID,
        "target_task_arn": VALID_TASK_ARN,
    }
    del payload[missing_field]
    with pytest.raises(RequestValidationError) as exc:
        RemediationRequest.from_dict(payload)
    assert "Schema validation failed" in str(exc.value)


def test_extra_properties_rejected():
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": VALID_ACTION_ID,
        "target_task_arn": VALID_TASK_ARN,
        "extra_field": "untrusted_value",
    }
    with pytest.raises(RequestValidationError) as exc:
        RemediationRequest.from_dict(payload)
    assert "Schema validation failed" in str(exc.value)


@pytest.mark.parametrize("injected_param", [
    "healthy_count",
    "min_healthy_tasks",
    "is_authorized",
    "approved",
    "cooldown_override",
    "role",
    "assume_role",
    "shell",
    "force"
])
def test_prohibited_injected_parameters_rejected(injected_param):
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": VALID_ACTION_ID,
        "target_task_arn": VALID_TASK_ARN,
        injected_param: True,
    }
    with pytest.raises(RequestValidationError):
        RemediationRequest.from_dict(payload)


def test_invalid_incident_id_pattern():
    payload = {
        "incident_id": "invalid-incident-123",  # Must start with inc- and be hex
        "action_id": VALID_ACTION_ID,
        "target_task_arn": VALID_TASK_ARN,
    }
    with pytest.raises(RequestValidationError):
        RemediationRequest.from_dict(payload)


def test_invalid_action_id_enum():
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": "DESTROY_ENTIRE_CLUSTER",
        "target_task_arn": VALID_TASK_ARN,
    }
    with pytest.raises(RequestValidationError):
        RemediationRequest.from_dict(payload)


def test_invalid_target_task_arn_format():
    # Target in production cluster instead of blastgate-sandbox
    payload = {
        "incident_id": VALID_INCIDENT_ID,
        "action_id": VALID_ACTION_ID,
        "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/production-cluster/1234567890abcdef1234567890abcdef",
    }
    with pytest.raises(RequestValidationError):
        RemediationRequest.from_dict(payload)


def test_non_dict_payload_rejected():
    with pytest.raises(RequestValidationError) as exc:
        RemediationRequest.from_dict(["not", "a", "dict"])
    assert "valid JSON object" in str(exc.value)
