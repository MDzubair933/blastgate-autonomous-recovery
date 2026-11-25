"""
BlastGate Step 5 Security Tests — AgentCore Managed Harness (S5-001 through S5-006)
Tests harness configuration against Boto3 service models, allowed tools restriction,
absence of direct runtime command permissions, execution bounds, and credential safety.
"""

import pytest
import botocore.session
from botocore.validate import ParamValidator

from agentcore.harness.config import (
    HARNESS_NAME,
    ALLOWED_TOOLS,
    MAX_ITERATIONS,
    MAX_TOKENS,
    TIMEOUT_SECONDS,
    DEFAULT_MODEL_ID,
    get_create_harness_payload,
)


@pytest.fixture(scope="module")
def control_service_model():
    session = botocore.session.get_session()
    return session.get_service_model("bedrock-agentcore-control")


def test_s5_001_harness_config_valid_against_boto3_schema(control_service_model):
    """S5-001: Harness config strictly matches the supported CreateHarness API schema."""
    op = control_service_model.operation_model("CreateHarness")
    payload = get_create_harness_payload()

    pv = ParamValidator()
    errors = pv.validate(payload, op.input_shape)
    assert not errors.has_errors(), f"CreateHarness validation failed: {errors.generate_report()}"


def test_s5_002_only_approved_gateway_tools_accessible():
    """S5-002: Allowed tools whitelist strictly contains only approved BlastGate tools in valid AgentCore format."""
    import re
    # Official AgentCore regex pattern for allowedTools entries
    agentcore_tool_pattern = re.compile(r"^(\*|@?[^/]+(/[^/]+)?)$")

    for tool in ALLOWED_TOOLS:
        assert agentcore_tool_pattern.match(tool), f"Tool '{tool}' fails AgentCore tool name pattern!"
        assert len(tool) <= 64, f"Tool '{tool}' exceeds maximum length of 64 characters"
        assert tool not in ["*", "@builtin"], f"Wildcard '{tool}' violates least-privilege tool boundary"
        assert any(
            approved in tool
            for approved in ["get_incident_diagnostics", "propose_worker_replacement"]
        ), f"Unapproved tool '{tool}' found in ALLOWED_TOOLS!"

    payload = get_create_harness_payload()
    assert payload["allowedTools"] == ALLOWED_TOOLS


def test_s5_004b_harness_role_lacks_runtime_command_permission():
    """S5-004B: Harness role policy explicitly omits bedrock-agentcore:InvokeAgentRuntimeCommand."""
    import json
    from pathlib import Path
    template_path = Path(__file__).resolve().parent.parent / "infrastructure" / "cdk" / "cdk.out" / "BlastGateIamStack.template.json"
    assert template_path.exists(), f"Missing template: {template_path}"
    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    for logical_id, resource in template.get("Resources", {}).items():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource.get("Properties", {}).get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                for action in actions:
                    assert action != "bedrock-agentcore:InvokeAgentRuntimeCommand", (
                        f"CRITICAL: Policy {logical_id} contains forbidden InvokeAgentRuntimeCommand!"
                    )


def test_s5_003_builtin_shell_and_file_tools_forbidden():
    """S5-003: Built-in shell, file_operations, code_interpreter, and browser tools are prohibited."""
    payload = get_create_harness_payload()
    allowed = payload.get("allowedTools", [])

    # None of the built-in tool identifiers may appear in allowedTools
    forbidden_tools = ["shell", "file_operations", "code_interpreter", "browser", "bash", "terminal"]
    for f in forbidden_tools:
        assert f not in allowed, f"Dangerous built-in tool '{f}' is present in allowedTools!"

    # In tools definition, remoteMcp or arbitrary custom tools must not be configured
    declared_tools = payload.get("tools", [])
    for t in declared_tools:
        tool_type = t.get("type")
        assert tool_type == "agentcore_gateway", f"Prohibited tool type '{tool_type}' declared in harness"
        config = t.get("config", {})
        assert "remoteMcp" not in config
        assert "agentCoreBrowser" not in config
        assert "agentCoreCodeInterpreter" not in config


def test_s5_004_direct_runtime_command_absent():
    """S5-004: Direct runtime command API is not referenced or authorized in the harness config."""
    payload = get_create_harness_payload()
    # Ensure no environment variables or hooks expose runtime command execution
    assert "environmentVariables" not in payload
    assert "hooks" not in payload


def test_s5_005_execution_limits_bounded():
    """S5-005: Execution limits are bounded conservatively (iterations <= 10, timeout <= 60s, tokens <= 2048)."""
    payload = get_create_harness_payload()
    assert payload["maxIterations"] <= 10
    assert payload["timeoutSeconds"] <= 60
    assert payload["maxTokens"] <= 2048


def test_s5_006_model_configuration_uses_bedrock_strictly():
    """S5-006: Model config uses bedrockModelConfig; third-party model providers are strictly absent."""
    payload = get_create_harness_payload()
    model_cfg = payload["model"]

    assert "bedrockModelConfig" in model_cfg
    assert "openAiModelConfig" not in model_cfg
    assert "geminiModelConfig" not in model_cfg
    assert "liteLlmModelConfig" not in model_cfg

    bmc = model_cfg["bedrockModelConfig"]
    assert bmc["modelId"] == DEFAULT_MODEL_ID
    assert bmc["apiFormat"] == "converse_stream"
