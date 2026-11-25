"""
BlastGate Step 5 Security Tests — AgentCore Gateway & Tools (S5-007 through S5-011)
Tests Gateway configuration, tool schemas, read-only diagnostics boundary, and mutation prohibition.
"""

import json
from pathlib import Path
import pytest
import botocore.session
from botocore.validate import ParamValidator

from agentcore.gateway.config import (
    GATEWAY_NAME,
    get_create_gateway_payload,
    get_diagnostics_target_payload,
    get_broker_target_payload,
    load_tool_schema,
)

TOOLS_DIR = Path(__file__).resolve().parent.parent / "agentcore" / "gateway" / "tools"


@pytest.fixture(scope="module")
def control_service_model():
    session = botocore.session.get_session()
    return session.get_service_model("bedrock-agentcore-control")


def test_s5_007_exactly_two_approved_tools_exist():
    """S5-007: Exactly two approved Gateway tool schema files exist in the repository."""
    tool_files = list(TOOLS_DIR.glob("*.json"))
    tool_names = [f.stem for f in tool_files]
    assert len(tool_files) == 2, f"Expected exactly 2 tool files, found: {tool_names}"
    assert set(tool_names) == {"diagnostics_tool", "remediation_tool"}


def test_s5_008_diagnostics_tool_is_read_only():
    """S5-008: Diagnostics tool schema accepts only incident_id and exposes zero mutation parameters."""
    schema = load_tool_schema("diagnostics_tool.json")
    assert schema["name"] == "get_incident_diagnostics"
    input_schema = schema["inputSchema"]
    assert input_schema["type"] == "object"
    assert set(input_schema["properties"].keys()) == {"incident_id"}
    assert input_schema["required"] == ["incident_id"]

    # Prohibit any mutation verbs or action parameters
    forbidden_props = ["action", "action_id", "stop", "terminate", "shell", "force", "delete"]
    for f in forbidden_props:
        assert f not in input_schema["properties"]


def test_s5_009_remediation_tool_accepts_only_approved_schema():
    """S5-009: Remediation proposal tool strictly enforces incident_id, action_id, and target_task_arn."""
    schema = load_tool_schema("remediation_tool.json")
    assert schema["name"] == "propose_worker_replacement"
    input_schema = schema["inputSchema"]
    assert input_schema["type"] == "object"
    assert set(input_schema["properties"].keys()) == {"incident_id", "action_id", "target_task_arn"}
    assert set(input_schema["required"]) == {"incident_id", "action_id", "target_task_arn"}

    # Prohibit safety override injection fields
    forbidden_overrides = ["cooldown_override", "min_healthy_tasks", "force", "role", "assume_role", "shell"]
    for fo in forbidden_overrides:
        assert fo not in input_schema["properties"]


def test_s5_010_gateway_and_targets_valid_against_boto3(control_service_model):
    """S5-010: Gateway and both target payloads conform to Boto3 CreateGateway / CreateGatewayTarget."""
    pv = ParamValidator()

    # 1. Gateway
    gw_op = control_service_model.operation_model("CreateGateway")
    gw_payload = get_create_gateway_payload()
    err_gw = pv.validate(gw_payload, gw_op.input_shape)
    assert not err_gw.has_errors(), f"CreateGateway error: {err_gw.generate_report()}"

    # 2. Diagnostics Target
    tgt_op = control_service_model.operation_model("CreateGatewayTarget")
    diag_tgt = get_diagnostics_target_payload()
    err_diag = pv.validate(diag_tgt, tgt_op.input_shape)
    assert not err_diag.has_errors(), f"CreateGatewayTarget (Diag) error: {err_diag.generate_report()}"

    # 3. Broker Target
    broker_tgt = get_broker_target_payload()
    err_broker = pv.validate(broker_tgt, tgt_op.input_shape)
    assert not err_broker.has_errors(), f"CreateGatewayTarget (Broker) error: {err_broker.generate_report()}"


def test_s5_011_arbitrary_aws_apis_impossible_through_tools():
    """S5-011: Gateway tool schemas strictly prevent arbitrary AWS method invocation."""
    diag_schema = load_tool_schema("diagnostics_tool.json")
    rem_schema = load_tool_schema("remediation_tool.json")

    for s in [diag_schema, rem_schema]:
        props = s["inputSchema"]["properties"]
        assert "command" not in props
        assert "api" not in props
        assert "method" not in props
        assert "service" not in props
        assert "parameters" not in props


def test_s5_011b_gateway_inbound_and_outbound_auth():
    """S5-011B: Gateway requires AWS_IAM inbound authorizer and Harness specifies AWS IAM outbound."""
    gw_payload = get_create_gateway_payload()
    assert gw_payload["authorizerType"] == "AWS_IAM"

    from agentcore.harness.config import get_create_harness_payload
    harness_payload = get_create_harness_payload()
    gw_tool = [t for t in harness_payload["tools"] if t.get("type") == "agentcore_gateway"][0]
    outbound = gw_tool["config"]["agentCoreGateway"]["outboundAuth"]
    assert "awsIam" in outbound


def test_s5_011c_tool_schemas_strictly_forbid_additional_properties():
    """S5-011C: Gateway tools conform to Boto3 inputSchema shape; broker schema enforces additionalProperties: false."""
    import json
    diag = load_tool_schema("diagnostics_tool.json")
    rem = load_tool_schema("remediation_tool.json")

    # Boto3 inputSchema shape members
    boto3_allowed_keys = {"type", "properties", "required", "items", "description"}
    assert set(diag["inputSchema"].keys()).issubset(boto3_allowed_keys)
    assert set(rem["inputSchema"].keys()).issubset(boto3_allowed_keys)

    # Underlying broker contract schema enforces additionalProperties: false
    schema_path = Path(__file__).resolve().parent.parent / "contracts" / "remediation_request.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        broker_schema = json.load(f)
    assert broker_schema.get("additionalProperties") is False


def test_s5_011d_gateway_policy_engine_mode_enforce():
    """S5-011D: Gateway configuration targets Policy Engine in ENFORCE mode."""
    gw_payload = get_create_gateway_payload()
    pe_cfg = gw_payload.get("policyEngineConfiguration", {})
    assert pe_cfg.get("mode") == "ENFORCE"
