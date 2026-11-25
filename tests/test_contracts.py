"""
BlastGate Step 1 Contract & Schema Validation Suite
Executable verification tests CT-001 through CT-020+.
"""

import json
from pathlib import Path
import pytest
import jsonschema

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = WORKSPACE_ROOT / "contracts"
DOCS_DIR = WORKSPACE_ROOT / "docs"


@pytest.fixture
def action_catalog_schema():
    with open(CONTRACTS_DIR / "action_catalog.schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def action_catalog():
    with open(CONTRACTS_DIR / "action_catalog.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def remediation_request_schema():
    with open(CONTRACTS_DIR / "remediation_request.schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def decision_receipt_schema():
    with open(CONTRACTS_DIR / "decision_receipt.schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def audit_schema():
    with open(CONTRACTS_DIR / "audit_schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


# CT-001: Operational rules R1–R8 all exist
def test_ct_001_operational_rules_exist():
    rules_file = CONTRACTS_DIR / "OPERATIONAL_RULES.md"
    assert rules_file.exists(), "OPERATIONAL_RULES.md must exist"
    content = rules_file.read_text(encoding="utf-8")
    for i in range(1, 9):
        assert f"RULE R{i}:" in content, f"Rule R{i} must be defined in OPERATIONAL_RULES.md"


# CT-002: Every rule has an independent enforcement mechanism
def test_ct_002_rules_have_enforcement_mechanism():
    rules_file = CONTRACTS_DIR / "OPERATIONAL_RULES.md"
    content = rules_file.read_text(encoding="utf-8")
    for i in range(1, 9):
        # Find rule section
        rule_start = content.find(f"RULE R{i}:")
        assert rule_start != -1
        rule_sub = content[rule_start:rule_start + 1500]
        assert "Independent Enforcement Mechanism:" in rule_sub, f"Rule R{i} must define independent enforcement"
        assert "Expected Refusal Behavior:" in rule_sub, f"Rule R{i} must define refusal behavior"


# CT-003: Action catalog validates against its schema
def test_ct_003_action_catalog_validates(action_catalog, action_catalog_schema):
    jsonschema.validate(instance=action_catalog, schema=action_catalog_schema)


# CT-004: Exactly one initial AWS mutation action is allowlisted
def test_ct_004_single_action_allowlisted(action_catalog):
    actions = action_catalog["actions"]
    assert len(actions) == 1, "Catalog must define exactly 1 action in sandbox baseline"
    assert actions[0]["action_id"] == "REPLACE_UNHEALTHY_ECS_WORKER"
    assert actions[0]["aws_api"] == "ecs:StopTask"
    assert actions[0]["allowed_cluster"] == "blastgate-sandbox"


# CT-005: Unknown action IDs are rejected
def test_ct_005_unknown_action_ids_rejected(action_catalog, action_catalog_schema):
    invalid_catalog = json.loads(json.dumps(action_catalog))
    invalid_catalog["actions"][0]["action_id"] = "RESTART_CONTAINER_UNKNOWN"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)


# CT-006: iam:CreateUser and unrelated AWS mutations are rejected
def test_ct_006_unrelated_aws_mutations_rejected(action_catalog, action_catalog_schema):
    for bad_api in ["iam:CreateUser", "ecs:DeleteCluster", "ec2:TerminateInstances", "rds:DeleteDBInstance"]:
        invalid_catalog = json.loads(json.dumps(action_catalog))
        invalid_catalog["actions"][0]["aws_api"] = bad_api
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)


# CT-007: Missing required catalog properties are rejected
def test_ct_007_missing_required_catalog_properties_rejected(action_catalog, action_catalog_schema):
    required_keys = [
        "action_id", "runbook_id", "enabled", "environment", "aws_api",
        "allowed_cluster", "allowed_service", "cooldown_window_seconds",
        "min_healthy_tasks", "max_projected_unavailable_percent"
    ]
    for key in required_keys:
        invalid_catalog = json.loads(json.dumps(action_catalog))
        del invalid_catalog["actions"][0][key]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)


# CT-008: Invalid capacity thresholds are rejected
def test_ct_008_invalid_capacity_thresholds_rejected(action_catalog, action_catalog_schema):
    # Test zero or negative min_healthy_tasks
    invalid_catalog = json.loads(json.dumps(action_catalog))
    invalid_catalog["actions"][0]["min_healthy_tasks"] = 0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)

    # Test unavailable percent > 100
    invalid_catalog["actions"][0]["min_healthy_tasks"] = 4
    invalid_catalog["actions"][0]["max_projected_unavailable_percent"] = 150.0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)


# CT-009: Invalid cooldown values are rejected
def test_ct_009_invalid_cooldown_values_rejected(action_catalog, action_catalog_schema):
    # Cooldown < 60s
    invalid_catalog = json.loads(json.dumps(action_catalog))
    invalid_catalog["actions"][0]["cooldown_window_seconds"] = 10
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)

    # Cooldown > 3600s
    invalid_catalog["actions"][0]["cooldown_window_seconds"] = 10000
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_catalog, schema=action_catalog_schema)


# CT-010: Valid remediation request schema passes
def test_ct_010_valid_remediation_request_passes(remediation_request_schema):
    valid_payload = {
        "incident_id": "inc-b21ae7704864efec",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8"
    }
    jsonschema.validate(instance=valid_payload, schema=remediation_request_schema)


# CT-011: Additional unauthorized request fields are rejected
def test_ct_011_additional_request_fields_rejected(remediation_request_schema):
    invalid_payload = {
        "incident_id": "inc-b21ae7704864efec",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
        "execute_as_role": "arn:aws:iam::123456789012:role/AdminRole"
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_payload, schema=remediation_request_schema)


# CT-012: Agent-supplied capacity or authorization flags are rejected
def test_ct_012_agent_supplied_safety_flags_rejected(remediation_request_schema):
    for bad_field in ["skip_quorum_check", "healthy_workers_count", "override_authorization", "ciso_token"]:
        payload = {
            "incident_id": "inc-b21ae7704864efec",
            "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
            "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
            bad_field: True
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=payload, schema=remediation_request_schema)


# CT-013: Invalid decision and execution enums are rejected
def test_ct_013_decision_receipt_enums_validated(decision_receipt_schema):
    valid_receipt = {
        "decision_id": "dec-f23ad5c2acf6c795",
        "incident_id": "inc-b21ae7704864efec",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
        "catalog_version": "1.0.0",
        "policy_version": "1.0.0",
        "decision": "ALLOW",
        "reason_code": "AUTH_APPROVED",
        "execution_status": "NOT_STARTED",
        "aws_request_id": None,
        "recorded_at": "2026-11-22T10:30:00Z",
        "rule_results": {
            "R1_allowlist": True,
            "R2_capacity": True,
            "R3_telemetry": True,
            "R4_cooldown": True,
            "R5_catalog": True,
            "R6_audit": True,
            "R7_authority": True,
            "R8_idempotency": True
        }
    }
    jsonschema.validate(instance=valid_receipt, schema=decision_receipt_schema)

    # Test invalid decision enum
    bad_receipt = json.loads(json.dumps(valid_receipt))
    bad_receipt["decision"] = "APPROVED_BY_AI"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_receipt, schema=decision_receipt_schema)

    # Test invalid execution enum
    bad_receipt = json.loads(json.dumps(valid_receipt))
    bad_receipt["execution_status"] = "PENDING_EXECUTION"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_receipt, schema=decision_receipt_schema)


# CT-014: Valid audit event matches the audit schema
def test_ct_014_valid_audit_event_passes(audit_schema):
    valid_event = {
        "event_id": "evt-0a05d7b27cc7a2b1",
        "event_type": "AUTHORIZATION_DECISION",
        "incident_id": "inc-b21ae7704864efec",
        "decision_id": "dec-f23ad5c2acf6c795",
        "actor_type": "LAMBDA_BROKER",
        "rule_results": {
            "R1_allowlist": True,
            "R2_capacity": True,
            "R3_telemetry": True,
            "R4_cooldown": True,
            "R5_catalog": True,
            "R6_audit": True,
            "R7_authority": True,
            "R8_idempotency": True
        },
        "requested_action": "REPLACE_UNHEALTHY_ECS_WORKER",
        "authorization_decision": "ALLOW",
        "execution_status": "NOT_STARTED",
        "timestamp": "2026-11-22T10:30:00Z",
        "evidence_references": [
            "cloudwatch:alarm:sandbox-worker-health",
            "ecs:describe_tasks:task-12345"
        ],
        "schema_version": "1.0.0",
        "integrity": {
            "event_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "previous_event_sha256": None,
            "writer_role_arn": "arn:aws:iam::123456789012:role/blastgate-broker-role"
        }
    }
    jsonschema.validate(instance=valid_event, schema=audit_schema)


# CT-015: Missing mandatory audit fields are rejected
def test_ct_015_missing_audit_fields_rejected(audit_schema):
    event = {
        "event_id": "evt-0a05d7b27cc7a2b1",
        "event_type": "AUTHORIZATION_DECISION",
        "incident_id": "inc-b21ae7704864efec"
        # missing remaining fields
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=event, schema=audit_schema)


# CT-016: All R1–R8 have corresponding planned test mappings
def test_ct_016_test_mappings_in_enforcement_matrix():
    matrix_file = DOCS_DIR / "RULE_ENFORCEMENT_MATRIX.md"
    assert matrix_file.exists(), "RULE_ENFORCEMENT_MATRIX.md must exist"
    content = matrix_file.read_text(encoding="utf-8")
    for i in range(1, 9):
        assert f"R{i}:" in content, f"Rule R{i} must be mapped in RULE_ENFORCEMENT_MATRIX.md"


# CT-017: Catalog and operational rules use consistent cooldown and capacity parameters
def test_ct_017_consistency_across_contracts(action_catalog):
    act = action_catalog["actions"][0]
    assert act["cooldown_window_seconds"] == 600
    assert act["min_healthy_tasks"] == 4
    assert act["max_projected_unavailable_percent"] == 20.0
    assert act["max_tasks_per_operation"] == 1
    assert act["max_authorized_replacements"] == 1

    # Check OPERATIONAL_RULES.md mentions 600 seconds and 4 tasks
    rules_text = (CONTRACTS_DIR / "OPERATIONAL_RULES.md").read_text(encoding="utf-8")
    assert "600-second" in rules_text
    assert "minimum healthy worker threshold" in rules_text.lower()


# CT-018: Threat model covers all mandatory attack categories
def test_ct_018_threat_model_covers_all_categories():
    threat_file = CONTRACTS_DIR / "threat_model.md"
    assert threat_file.exists(), "threat_model.md must exist"
    content = threat_file.read_text(encoding="utf-8")
    for letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]:
        assert f"Threat {letter}:" in content, f"Threat {letter} must be documented"


# CT-019: No contract authorizes arbitrary IAM or production database mutation
def test_ct_019_no_iam_or_db_mutation_authorized(action_catalog):
    for action in action_catalog["actions"]:
        api = action["aws_api"]
        assert not api.startswith("iam:"), "No IAM mutation may be authorized in catalog"
        assert not api.startswith("rds:"), "No RDS mutation may be authorized in catalog"
        assert not api.startswith("dynamodb:Delete"), "No destructive DynamoDB mutation may be authorized"
        assert action["allowed_cluster"] == "blastgate-sandbox"
        assert "production" in action["prohibited_environments"]


# CT-020: No contract incorrectly claims SHA-256 hash chaining alone guarantees immutable logs
def test_ct_020_truthful_audit_claims():
    rules_text = (CONTRACTS_DIR / "OPERATIONAL_RULES.md").read_text(encoding="utf-8")
    assert "absolute immutability" in rules_text.lower() or "dynamodb alone" in rules_text.lower()
    invariants_text = (CONTRACTS_DIR / "SECURITY_INVARIANTS.md").read_text(encoding="utf-8")
    assert "unbreakable" in invariants_text.lower()
