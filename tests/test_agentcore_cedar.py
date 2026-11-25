"""
BlastGate Step 5 Security Tests — Cedar Policy (S5-012 through S5-016)
Tests default-deny policy model, explicit permits for diagnostics and scoped proposal,
rejection of arbitrary actions, and verification tracking.
"""

import pytest
import botocore.session
from botocore.validate import ParamValidator

from agentcore.policies.config import (
    load_cedar_policy_text,
    get_create_policy_engine_payload,
    get_create_policy_payload,
    ENFORCEMENT_MODE,
    VALIDATION_MODE,
)
from agentcore.simulation.simulator import AgentCoreLocalSimulator


@pytest.fixture(scope="module")
def control_service_model():
    session = botocore.session.get_session()
    return session.get_service_model("bedrock-agentcore-control")


def test_s5_012_intended_policy_follows_default_deny():
    """S5-012: Intended policy has no wildcard permits; unallowlisted actions are denied by default."""
    cedar_text = load_cedar_policy_text()

    # Must NOT contain wildcard permits like permit(principal, action, resource)
    assert "permit(principal, action, resource);" not in cedar_text
    assert "permit(\n    principal,\n    action,\n    resource\n);" not in cedar_text

    # Simulator verifies that unapproved tool is denied under default deny
    sim = AgentCoreLocalSimulator()
    decision, reason = sim.evaluate_cedar_policy("unapproved_tool", {})
    assert decision == "DENY"
    assert "Default Deny" in reason


def test_s5_013_approved_diagnostics_has_explicit_permit():
    """S5-013: Diagnostics tool has an explicit permit in Cedar policy."""
    cedar_text = load_cedar_policy_text()
    assert 'Action::"get_incident_diagnostics"' in cedar_text

    sim = AgentCoreLocalSimulator()
    decision, reason = sim.evaluate_cedar_policy("get_incident_diagnostics", {"incident_id": "inc-4f9f10b304cfe9b2"})
    assert decision == "PERMIT"


def test_s5_014_remediation_proposal_scoped_to_allowlisted_action():
    """S5-014: propose_worker_replacement is permitted ONLY when action_id == REPLACE_UNHEALTHY_ECS_WORKER."""
    cedar_text = load_cedar_policy_text()
    assert 'Action::"propose_worker_replacement"' in cedar_text
    assert 'context.action_id == "REPLACE_UNHEALTHY_ECS_WORKER"' in cedar_text

    sim = AgentCoreLocalSimulator()
    # Matching action_id -> PERMIT
    decision_ok, _ = sim.evaluate_cedar_policy(
        "propose_worker_replacement",
        {"action_id": "REPLACE_UNHEALTHY_ECS_WORKER"}
    )
    assert decision_ok == "PERMIT"

    # Non-matching action_id -> DENY
    decision_bad, _ = sim.evaluate_cedar_policy(
        "propose_worker_replacement",
        {"action_id": "UNAUTHORIZED_ACTION"}
    )
    assert decision_bad == "DENY"


def test_s5_015_unsupported_action_ids_rejected():
    """S5-015: Malicious or arbitrary actions (IAM, EC2, ECS cluster deletion) are rejected by Cedar policy."""
    sim = AgentCoreLocalSimulator()
    for bad_action in ["iam:CreateUser", "ecs:DeleteCluster", "rds:DeleteDBInstance", "shell_exec"]:
        decision, _ = sim.evaluate_cedar_policy(
            "propose_worker_replacement",
            {"action_id": bad_action}
        )
        assert decision == "DENY"


def test_s5_016_policy_engine_boto3_conformance_and_pending_status(control_service_model):
    """S5-016: Policy and Engine payload conform to Boto3; AWS Cedar analyzer validation marked pending."""
    pv = ParamValidator()

    # Engine
    op_eng = control_service_model.operation_model("CreatePolicyEngine")
    eng_payload = get_create_policy_engine_payload()
    err_eng = pv.validate(eng_payload, op_eng.input_shape)
    assert not err_eng.has_errors()

    # Policy
    op_pol = control_service_model.operation_model("CreatePolicy")
    pol_payload = get_create_policy_payload(policy_engine_id="pe-123456789012")
    err_pol = pv.validate(pol_payload, op_pol.input_shape)
    assert not err_pol.has_errors()

    # Modes
    assert pol_payload["enforcementMode"] == ENFORCEMENT_MODE
    assert pol_payload["validationMode"] == VALIDATION_MODE


def test_s5_016b_cedar_syntax_auditor_detects_unconditional_forbid():
    """S5-016B: Cedar syntax auditor flags unconditional 'forbid(principal, action, resource);' as defect."""
    from agentcore.policies.evaluator import CedarPolicySyntaxAuditor

    bad_cedar = """
    forbid(principal, action, resource);
    permit(
        principal == AgentCore::IamEntity::"arn:aws:iam::123456789012:role/blastgate-agent-role",
        action in [AgentCore::Action::"get_incident_diagnostics"],
        resource
    );
    """
    findings = CedarPolicySyntaxAuditor.audit_policy_text(bad_cedar)
    assert any("CRITICAL_DEFECT" in f and "forbid" in f for f in findings)


def test_s5_016c_production_cedar_policy_has_no_unconditional_forbid():
    """S5-016C: Production cedar_policies.cedar contains zero unconditional forbid statements."""
    from agentcore.policies.evaluator import CedarPolicySyntaxAuditor

    cedar_text = load_cedar_policy_text()
    findings = CedarPolicySyntaxAuditor.audit_policy_text(cedar_text)
    critical_findings = [f for f in findings if f.startswith("CRITICAL_DEFECT")]
    assert len(critical_findings) == 0, f"Critical Cedar defects found: {critical_findings}"


def test_s5_016d_cedar_semantic_evaluator_untrusted_principal_denied():
    """S5-016D: Requests from untrusted principals are strictly DENIED under default deny."""
    from agentcore.policies.evaluator import CedarPolicyEvaluator, TRUSTED_RESOURCE

    evaluator = CedarPolicyEvaluator(cedar_policy_text=load_cedar_policy_text())
    result = evaluator.evaluate(
        principal="arn:aws:iam::123456789012:role/attacker-role",
        action="get_incident_diagnostics",
        resource=TRUSTED_RESOURCE,
        context={"incident_id": "inc-00000001"}
    )
    assert result.decision == "DENY"
    assert "Untrusted principal" in result.reason


def test_s5_016e_cedar_semantic_evaluator_unrelated_gateway_denied():
    """S5-016E: Requests targeting an unrelated Gateway ARN are strictly DENIED."""
    from agentcore.policies.evaluator import CedarPolicyEvaluator, TRUSTED_PRINCIPAL

    evaluator = CedarPolicyEvaluator(cedar_policy_text=load_cedar_policy_text())
    result = evaluator.evaluate(
        principal=TRUSTED_PRINCIPAL,
        action="get_incident_diagnostics",
        resource='AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/unrelated-gateway"',
        context={"incident_id": "inc-00000001"}
    )
    assert result.decision == "DENY"
    assert "Unrelated Gateway" in result.reason


def test_s5_016f_cedar_semantic_evaluator_missing_action_id_denied():
    """S5-016F: Remediation proposals without context.action_id are strictly DENIED."""
    from agentcore.policies.evaluator import CedarPolicyEvaluator, TRUSTED_PRINCIPAL, TRUSTED_RESOURCE

    evaluator = CedarPolicyEvaluator(cedar_policy_text=load_cedar_policy_text())
    result = evaluator.evaluate(
        principal=TRUSTED_PRINCIPAL,
        action="propose_worker_replacement",
        resource=TRUSTED_RESOURCE,
        context={}  # Missing action_id
    )
    assert result.decision == "DENY"
    assert "Missing context.action_id" in result.reason


def test_s5_016g_enforcement_mode_vs_gateway_mode_distinction():
    """S5-016G: Policy uses enforcementMode ACTIVE; Gateway uses policyEngineConfiguration.mode ENFORCE."""
    from agentcore.gateway.config import get_create_gateway_payload
    from agentcore.policies.config import get_create_policy_payload

    pol_payload = get_create_policy_payload(policy_engine_id="pe-123456789012")
    gw_payload = get_create_gateway_payload(policy_engine_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:policy-engine/pe-1")

    # Policy resource uses enforcementMode: ACTIVE (enum: ACTIVE, LOG_ONLY)
    assert pol_payload["enforcementMode"] == "ACTIVE"
    # Gateway resource uses policyEngineConfiguration.mode: ENFORCE (enum: ENFORCE, LOG_ONLY)
    assert gw_payload["policyEngineConfiguration"]["mode"] == "ENFORCE"
