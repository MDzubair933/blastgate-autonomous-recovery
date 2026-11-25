"""
BlastGate IAM Policies & Role Segregation Verification Tests
Covers requirements INF-012 through INF-019, and INF-030.
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
def iam_data(iam_template):
    roles = {}
    policies = []
    resources = iam_template.get("Resources", {})
    for res_id, res in resources.items():
        if res.get("Type") == "AWS::IAM::Role":
            props = res.get("Properties", {})
            name = props.get("RoleName", res_id)
            roles[name] = {"logical_id": res_id, "props": props}
        elif res.get("Type") == "AWS::IAM::Policy":
            props = res.get("Properties", {})
            policies.append(props)
    return {"roles": roles, "policies": policies}


def get_statements_for_role(role_name: str, iam_data: dict) -> list:
    statements = []
    role_info = iam_data["roles"].get(role_name, {})
    if not role_info:
        return statements

    logical_id = role_info.get("logical_id", "")
    props = role_info.get("props", {})

    # Check inline statements in role
    for p in props.get("Policies", []):
        doc = p.get("PolicyDocument", {})
        statements.extend(doc.get("Statement", []))

    # Check separate policy objects referencing this role
    for p in iam_data["policies"]:
        roles_attached = p.get("Roles", [])
        for r_ref in roles_attached:
            if isinstance(r_ref, dict) and r_ref.get("Ref") == logical_id:
                statements.extend(p.get("PolicyDocument", {}).get("Statement", []))
            elif isinstance(r_ref, str) and (r_ref == logical_id or r_ref == role_name):
                statements.extend(p.get("PolicyDocument", {}).get("Statement", []))

    return statements


# INF-012: Agent role cannot perform any ECS mutation (ecs:StopTask, ecs:UpdateService, etc.)
def test_inf_012_agent_role_no_ecs_mutation(iam_data):
    agent_stmts = get_statements_for_role("blastgate-agent-role", iam_data)
    assert len(agent_stmts) > 0, "Agent role must have statements defined"
    for s in agent_stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            assert not a.startswith("ecs:"), f"Agent role must not have any ECS permissions! Found: {a}"


# INF-013: Agent role cannot perform IAM administration (iam:*)
def test_inf_013_agent_role_no_iam_admin(iam_data):
    agent_stmts = get_statements_for_role("blastgate-agent-role", iam_data)
    for s in agent_stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            assert not a.startswith("iam:"), f"Agent role must not have IAM permissions! Found: {a}"


# INF-014: Broker role has ecs:StopTask permission scoped with resource/condition to blastgate-sandbox
def test_inf_014_broker_role_scoped_stoptask(iam_data):
    broker_stmts = get_statements_for_role("blastgate-broker-role", iam_data)
    stop_task_stmts = []
    for s in broker_stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "ecs:StopTask" in actions:
            stop_task_stmts.append(s)

    assert len(stop_task_stmts) == 1, f"Broker must have exactly 1 StopTask statement, found {len(stop_task_stmts)}"
    stmt = stop_task_stmts[0]
    assert stmt.get("Effect") == "Allow"

    # Verify condition is scoped to cluster
    cond = stmt.get("Condition", {})
    assert "ArnEquals" in cond or "ArnLike" in cond or "StringEquals" in cond, "StopTask must be condition-scoped"
    cond_vals = cond.get("ArnEquals", {}) or cond.get("ArnLike", {}) or cond.get("StringEquals", {})
    assert any("blastgate-sandbox" in str(v) for v in cond_vals.values()), "StopTask condition must match blastgate-sandbox"


# INF-015: Broker role has conditional UpdateItem on blastgate-state
def test_inf_015_broker_role_update_state(iam_data):
    broker_stmts = get_statements_for_role("blastgate-broker-role", iam_data)
    state_update_stmts = []
    for s in broker_stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "dynamodb:UpdateItem" in actions and s.get("Effect") == "Allow":
            res = s.get("Resource", "")
            if "blastgate-state" in str(res):
                state_update_stmts.append(s)

    assert len(state_update_stmts) >= 1, "Broker must have Allow on dynamodb:UpdateItem for blastgate-state"


# INF-016: Broker role has PutItem on blastgate-audit
def test_inf_016_broker_role_put_audit(iam_data):
    broker_stmts = get_statements_for_role("blastgate-broker-role", iam_data)
    audit_put_stmts = []
    for s in broker_stmts:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "dynamodb:PutItem" in actions and s.get("Effect") == "Allow":
            res = s.get("Resource", "")
            if "blastgate-audit" in str(res):
                audit_put_stmts.append(s)

    assert len(audit_put_stmts) >= 1, "Broker must have Allow on dynamodb:PutItem for blastgate-audit"


# INF-017: Broker role has explicit Deny on DeleteItem and UpdateItem on blastgate-audit
def test_inf_017_broker_role_deny_delete_update_audit(iam_data):
    broker_stmts = get_statements_for_role("blastgate-broker-role", iam_data)
    deny_stmts = []
    for s in broker_stmts:
        if s.get("Effect") == "Deny":
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            res = s.get("Resource", "")
            if "blastgate-audit" in str(res):
                if "dynamodb:DeleteItem" in actions and "dynamodb:UpdateItem" in actions:
                    deny_stmts.append(s)

    assert len(deny_stmts) >= 1, "Broker must have explicit DENY on DeleteItem and UpdateItem for blastgate-audit"


# INF-018: Worker execution role has minimal ECR/Logs pull permissions only
def test_inf_018_worker_execution_role_minimal_ecr_logs(iam_data):
    exec_stmts = get_statements_for_role("blastgate-worker-execution-role", iam_data)
    allowed_prefixes = ("logs:", "ecr:")
    for s in exec_stmts:
        if s.get("Effect") == "Allow":
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            for a in actions:
                assert a.startswith(allowed_prefixes), f"Worker execution role has unpermitted action: {a}"


# INF-019: Diagnostics role has read-only CloudWatch / ECS describe permissions, zero write/mutation permissions
def test_inf_019_diagnostics_role_read_only(iam_data):
    diag_stmts = get_statements_for_role("blastgate-diagnostics-role", iam_data)
    write_verbs = ("put", "create", "delete", "update", "stop", "modify", "terminate")
    for s in diag_stmts:
        if s.get("Effect") == "Allow":
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            for a in actions:
                verb = a.split(":")[-1].lower()
                assert not any(verb.startswith(w) for w in write_verbs), (
                    f"Diagnostics role must be read-only! Found mutating action: {a}"
                )


# INF-030: No wildcard (*) actions on sensitive services in IAM policies
def test_inf_030_no_wildcard_actions_on_sensitive_services(iam_data):
    sensitive_services = ("iam:", "dynamodb:", "ecs:", "lambda:")
    for role_name in iam_data["roles"]:
        stmts = get_statements_for_role(role_name, iam_data)
        for s in stmts:
            if s.get("Effect") == "Allow":
                actions = s.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                for a in actions:
                    assert a != "*", f"Wildcard action '*' is strictly forbidden in {role_name}"
                    for svc in sensitive_services:
                        assert a != f"{svc}*", f"Wildcard '{svc}*' is forbidden in {role_name}"


def test_step6_cfn_exec_and_runtime_boundary_constraints():
    cdk_dir = WORKSPACE_ROOT / "infrastructure" / "cdk"
    cfn_policy_path = cdk_dir / "blastgate-cfn-exec-policy.json"
    boundary_path = cdk_dir / "blastgate-runtime-boundary.json"

    cfn_doc = json.loads(cfn_policy_path.read_text(encoding="utf-8"))
    boundary_doc = json.loads(boundary_path.read_text(encoding="utf-8"))

    cfn_minified = json.dumps(cfn_doc, separators=(",", ":"))
    boundary_minified = json.dumps(boundary_doc, separators=(",", ":"))
    assert len(cfn_minified) <= 6144, f"cfn-exec policy exceeds AWS 6144 char cap: {len(cfn_minified)}"
    assert len(boundary_minified) <= 6144, f"runtime-boundary exceeds AWS 6144 char cap: {len(boundary_minified)}"

    # ec2:CreateTags must never allow Resource='*' and must require ec2:CreateAction + Project=BlastGate
    create_tags_stmts = []
    for s in cfn_doc["Statement"]:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "ec2:CreateTags" in actions and s.get("Effect") == "Allow":
            create_tags_stmts.append(s)

    assert len(create_tags_stmts) == 1
    tag_stmt = create_tags_stmts[0]
    res_list = tag_stmt["Resource"] if isinstance(tag_stmt["Resource"], list) else [tag_stmt["Resource"]]
    assert "*" not in res_list
    assert all(r.startswith("arn:aws:ec2:us-east-1:123456789012:") for r in res_list)
    str_eq = tag_stmt.get("Condition", {}).get("StringEquals", {})
    assert str_eq.get("aws:RequestTag/Project") == "BlastGate"
    assert set(str_eq.get("ec2:CreateAction", [])) >= {
        "CreateVpc",
        "CreateSubnet",
        "CreateRouteTable",
        "CreateInternetGateway",
        "CreateSecurityGroup",
    }

    # Network-mutation EC2 actions must be tag-conditioned to BlastGate-owned resources
    net_mut_actions = {
        "ec2:CreateRoute",
        "ec2:DeleteRoute",
        "ec2:ReplaceRoute",
        "ec2:AttachInternetGateway",
        "ec2:DetachInternetGateway",
        "ec2:AssociateRouteTable",
        "ec2:DisassociateRouteTable",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupEgress",
    }
    for s in cfn_doc["Statement"]:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if net_mut_actions.intersection(set(actions)) and s.get("Effect") == "Allow":
            str_eq = s.get("Condition", {}).get("StringEquals", {})
            assert str_eq.get("ec2:ResourceTag/Project") == "BlastGate", (
                f"Network mutation statement missing ec2:ResourceTag/Project=BlastGate condition: {s}"
            )

    # Boundary must scope CloudWatch logs ARNs instead of using wildcard '*' and allow underscore PolicyEngine ARN
    bdy_resources = json.dumps(boundary_doc)
    assert "policy-engine/blastgate_policy_engine*" in bdy_resources, (
        "Runtime boundary must match underscore policy-engine/blastgate_policy_engine* ARN"
    )
    for s in boundary_doc["Statement"]:
        if s.get("Effect") != "Allow":
            continue
        actions = s.get("Action", []) if isinstance(s.get("Action"), list) else [s.get("Action")]
        if any(a.startswith("logs:") for a in actions):
            assert s.get("Resource") != "*", f"Boundary logs statement cannot use Resource='*': {s}"


def test_step6_iam_stack_boundaries_and_log_arn_patterns(iam_data):
    expected_suffix = ":iam::123456789012:policy/BlastGateRuntimeBoundary"
    for role_name, info in iam_data["roles"].items():
        props = info["props"]
        boundary_serialized = json.dumps(props.get("PermissionsBoundary"))
        assert expected_suffix in boundary_serialized, f"{role_name} missing boundary: {boundary_serialized}"
        assert not props.get("ManagedPolicyArns"), f"{role_name} should not attach managed policies directly"

        stmts = get_statements_for_role(role_name, iam_data)
        for s in stmts:
            if s.get("Effect") != "Allow":
                continue
            actions = s.get("Action", []) if isinstance(s.get("Action"), list) else [s.get("Action")]
            resources = s.get("Resource", []) if isinstance(s.get("Resource"), list) else [s.get("Resource")]
            if any(a in ("logs:CreateLogStream", "logs:PutLogEvents", "logs:GetLogEvents") for a in actions):
                assert "*" not in resources, f"{role_name} has wildcard log stream resource: {s}"
                for r in resources:
                    if isinstance(r, str):
                        assert r.endswith(":log-stream:*") or r.endswith(":*"), (
                            f"{role_name} stream action missing ':log-stream:*': {r}"
                        )
            if "logs:FilterLogEvents" in actions:
                assert "*" not in resources
                for r in resources:
                    assert isinstance(r, str) and ":log-group:/aws/blastgate/" in r and ":log-stream:" not in r

