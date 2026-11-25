"""
BlastGate AgentCore Configuration Validator
Validates all AgentCore Managed Harness, Gateway, Policy, and Guardrail structures
against actual Boto3 service models using botocore.validate.ParamValidator.
"""

import sys
from pathlib import Path

HACKATHON_ROOT = Path(__file__).resolve().parent.parent.parent
if str(HACKATHON_ROOT) not in sys.path:
    sys.path.insert(0, str(HACKATHON_ROOT))

import botocore.session
from botocore.validate import ParamValidator

from agentcore.harness.config import get_create_harness_payload
from agentcore.gateway.config import (
    get_create_gateway_payload,
    get_diagnostics_target_payload,
    get_broker_target_payload,
)
from agentcore.policies.config import (
    get_create_policy_engine_payload,
    get_create_policy_payload,
    load_cedar_policy_text,
)
from agentcore.guardrails.config import get_create_guardrail_payload


def validate_all_agentcore_configurations() -> dict:
    """
    Validates all payload generators against real botocore service definitions.
    Returns dictionary with validation results for each component.
    """
    session = botocore.session.get_session()
    pv = ParamValidator()
    results = {}

    # 1. AgentCore Control Client Model
    ctrl_model = session.get_service_model("bedrock-agentcore-control")

    # Validate CreateHarness
    harness_op = ctrl_model.operation_model("CreateHarness")
    harness_payload = get_create_harness_payload()
    err_harness = pv.validate(harness_payload, harness_op.input_shape)
    results["CreateHarness"] = {
        "valid": not err_harness.has_errors(),
        "errors": err_harness.generate_report() if err_harness.has_errors() else None,
    }

    # Validate CreateGateway
    gw_op = ctrl_model.operation_model("CreateGateway")
    gw_payload = get_create_gateway_payload()
    err_gw = pv.validate(gw_payload, gw_op.input_shape)
    results["CreateGateway"] = {
        "valid": not err_gw.has_errors(),
        "errors": err_gw.generate_report() if err_gw.has_errors() else None,
    }

    # Validate CreateGatewayTarget (Diagnostics)
    tgt_op = ctrl_model.operation_model("CreateGatewayTarget")
    diag_tgt_payload = get_diagnostics_target_payload()
    err_diag_tgt = pv.validate(diag_tgt_payload, tgt_op.input_shape)
    results["CreateGatewayTarget_Diagnostics"] = {
        "valid": not err_diag_tgt.has_errors(),
        "errors": err_diag_tgt.generate_report() if err_diag_tgt.has_errors() else None,
    }

    # Validate CreateGatewayTarget (Remediation Broker)
    broker_tgt_payload = get_broker_target_payload()
    err_broker_tgt = pv.validate(broker_tgt_payload, tgt_op.input_shape)
    results["CreateGatewayTarget_Broker"] = {
        "valid": not err_broker_tgt.has_errors(),
        "errors": err_broker_tgt.generate_report() if err_broker_tgt.has_errors() else None,
    }

    # Validate CreatePolicyEngine
    eng_op = ctrl_model.operation_model("CreatePolicyEngine")
    eng_payload = get_create_policy_engine_payload()
    err_eng = pv.validate(eng_payload, eng_op.input_shape)
    results["CreatePolicyEngine"] = {
        "valid": not err_eng.has_errors(),
        "errors": err_eng.generate_report() if err_eng.has_errors() else None,
    }

    # Validate CreatePolicy
    pol_op = ctrl_model.operation_model("CreatePolicy")
    pol_payload = get_create_policy_payload(policy_engine_id="pe-123456789012")
    err_pol = pv.validate(pol_payload, pol_op.input_shape)
    results["CreatePolicy"] = {
        "valid": not err_pol.has_errors(),
        "errors": err_pol.generate_report() if err_pol.has_errors() else None,
    }

    # 2. Bedrock Guardrail Model
    bedrock_model = session.get_service_model("bedrock")
    gr_op = bedrock_model.operation_model("CreateGuardrail")
    gr_payload = get_create_guardrail_payload()
    err_gr = pv.validate(gr_payload, gr_op.input_shape)
    results["CreateGuardrail"] = {
        "valid": not err_gr.has_errors(),
        "errors": err_gr.generate_report() if err_gr.has_errors() else None,
    }

    # 3. Cedar Policy Source & Syntax Checks
    from agentcore.policies.evaluator import CedarPolicySyntaxAuditor
    cedar_text = load_cedar_policy_text()
    syntax_findings = CedarPolicySyntaxAuditor.audit_policy_text(cedar_text)
    critical_defects = [f for f in syntax_findings if f.startswith("CRITICAL")]

    cedar_valid = (
        len(critical_defects) == 0
        and "permit (" in cedar_text
        and "get_incident_diagnostics" in cedar_text
        and "propose_worker_replacement" in cedar_text
        and 'context.action_id == "REPLACE_UNHEALTHY_ECS_WORKER"' in cedar_text
    )
    results["CedarPolicySource"] = {
        "valid": cedar_valid,
        "details": "Default-deny structure verified without unconditional forbid; scoped permits for diagnostics and proposal.",
        "errors": critical_defects if critical_defects else None,
    }

    return results


if __name__ == "__main__":
    res = validate_all_agentcore_configurations()
    all_ok = True
    print("=" * 60)
    print("BLASTGATE AGENTCORE CONFIGURATION VALIDATION")
    print("=" * 60)
    for name, data in res.items():
        status = "PASS" if data["valid"] else "FAIL"
        print(f"[{status}] {name}")
        if not data["valid"]:
            all_ok = False
            print(f"       Errors: {data.get('errors')}")
    print("=" * 60)
    if all_ok:
        print("[SUCCESS] All AgentCore configurations strictly valid against Boto3 service models!")
        sys.exit(0)
    else:
        print("[FAILURE] One or more configurations failed validation.")
        sys.exit(1)
