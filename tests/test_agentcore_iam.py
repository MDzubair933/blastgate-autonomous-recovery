"""
BlastGate Step 5 Security Tests — AgentCore IAM Isolation (S5-017 through S5-021)
Verifies IAM role segregation, absence of direct mutation rights on agent and gateway,
scoped Gateway Lambda targets, and Policy Engine operations.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


@pytest.fixture(scope="module")
def iam_template():
    template_file = CDK_OUT_DIR / "BlastGateIamStack.template.json"
    assert template_file.exists(), f"Missing template file: {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def iam_entities(iam_template):
    roles = {}
    policies = []
    for res_id, res in iam_template.get("Resources", {}).items():
        if res.get("Type") == "AWS::IAM::Role":
            props = res.get("Properties", {})
            name = props.get("RoleName", res_id)
            roles[name] = {"logical_id": res_id, "props": props}
        elif res.get("Type") == "AWS::IAM::Policy":
            policies.append(res.get("Properties", {}))
    return {"roles": roles, "policies": policies}


def get_statements_for_role(role_name: str, iam_entities: dict) -> list:
    statements = []
    role_info = iam_entities["roles"].get(role_name, {})
    if not role_info:
        return statements

    logical_id = role_info.get("logical_id", "")
    for p in role_info.get("props", {}).get("Policies", []):
        statements.extend(p.get("PolicyDocument", {}).get("Statement", []))

    for p in iam_entities["policies"]:
        for r_ref in p.get("Roles", []):
            if isinstance(r_ref, dict) and r_ref.get("Ref") == logical_id:
                statements.extend(p.get("PolicyDocument", {}).get("Statement", []))
            elif isinstance(r_ref, str) and (r_ref == logical_id or r_ref == role_name):
                statements.extend(p.get("PolicyDocument", {}).get("Statement", []))

    return statements


def test_s5_017_agent_role_no_ecs_stoptask(iam_entities):
    """S5-017: Agent/Harness execution role strictly has NO ecs:StopTask permission."""
    stmts = get_statements_for_role("blastgate-agent-role", iam_entities)
    assert len(stmts) > 0
    for s in stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            assert not a.startswith("ecs:"), f"Agent role must not have ECS actions! Found: {a}"
            assert a != "bedrock-agentcore:InvokeAgentRuntimeCommand", (
                "Agent role must NOT have InvokeAgentRuntimeCommand!"
            )


def test_s5_018_gateway_role_no_ecs_stoptask(iam_entities):
    """S5-018: Gateway execution role strictly has NO ecs:StopTask or ECS mutation permissions."""
    stmts = get_statements_for_role("blastgate-gateway-example", iam_entities)
    assert len(stmts) > 0
    for s in stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            assert not a.startswith("ecs:"), f"Gateway role must not have ECS actions! Found: {a}"


def test_s5_019_broker_role_only_authorized_mutation_role(iam_entities):
    """S5-019: Broker role is the ONLY role in the entire stack with ecs:StopTask permission."""
    mutation_roles = []
    for role_name in iam_entities["roles"]:
        stmts = get_statements_for_role(role_name, iam_entities)
        for s in stmts:
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if "ecs:StopTask" in actions and s.get("Effect") == "Allow":
                mutation_roles.append(role_name)

    assert mutation_roles == ["blastgate-broker-role"], (
        f"Only blastgate-broker-role may hold ecs:StopTask! Found: {mutation_roles}"
    )


def test_s5_020_gateway_role_includes_policy_engine_operations(iam_entities):
    """S5-020: Gateway role includes AuthorizeAction, PartiallyAuthorizeActions, and GetPolicyEngine."""
    stmts = get_statements_for_role("blastgate-gateway-example", iam_entities)
    allowed_actions = set()
    for s in stmts:
        if s.get("Effect") == "Allow":
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            allowed_actions.update(actions)

    assert "bedrock-agentcore:AuthorizeAction" in allowed_actions
    assert "bedrock-agentcore:PartiallyAuthorizeActions" in allowed_actions
    assert "bedrock-agentcore:GetPolicyEngine" in allowed_actions
    assert "policy-engine/blastgate_policy_engine*" in json.dumps(stmts), (
        "GatewayRole must scope PolicyEngine operations to underscore policy-engine/blastgate_policy_engine*"
    )


def test_s5_021_agentcore_role_trust_relationships(iam_entities):
    """S5-021: Gateway role trusts bedrock-agentcore.amazonaws.com strictly."""
    gw_role = iam_entities["roles"].get("blastgate-gateway-example", {}).get("props", {})
    assume_policy = gw_role.get("AssumeRolePolicyDocument", {})
    principals = []
    for s in assume_policy.get("Statement", []):
        p = s.get("Principal", {})
        if "Service" in p:
            srv = p["Service"]
            if isinstance(srv, str):
                principals.append(srv)
            elif isinstance(srv, list):
                principals.extend(srv)

    assert "bedrock-agentcore.amazonaws.com" in principals


def test_s5_021b_policy_management_excluded_from_runtime_roles(iam_entities):
    """S5-021B: Gateway mutation and Policy Engine modification are forbidden across all runtime roles."""
    restricted_actions = {
        "bedrock-agentcore:UpdateGateway",
        "bedrock-agentcore:DeleteGateway",
        "bedrock-agentcore:CreatePolicy",
        "bedrock-agentcore:UpdatePolicy",
        "bedrock-agentcore:DeletePolicy",
        "bedrock-agentcore:CreatePolicyEngine",
        "bedrock-agentcore:UpdatePolicyEngine",
        "bedrock-agentcore:DeletePolicyEngine",
    }

    for role_name in iam_entities["roles"]:
        stmts = get_statements_for_role(role_name, iam_entities)
        for s in stmts:
            if s.get("Effect") == "Allow":
                actions = s.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                for a in actions:
                    assert a not in restricted_actions, (
                        f"CRITICAL: Runtime role '{role_name}' must not have management action '{a}'!"
                    )
