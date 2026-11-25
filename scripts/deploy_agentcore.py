#!/usr/bin/env python3
"""
BlastGate AgentCore & Guardrails Provisioning Utility
Deploys Bedrock Guardrail, AgentCore Policy Engine, AgentCore Gateway, Lambda Targets,
Cedar Policies (bound to actual Gateway ARN), and AgentCore Managed Harness (Amazon Nova Micro).
Defaults to --dry-run unless --confirm is explicitly supplied.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any

import boto3

HACKATHON_ROOT = Path(__file__).resolve().parent.parent
if str(HACKATHON_ROOT) not in sys.path:
    sys.path.insert(0, str(HACKATHON_ROOT))

from agentcore.guardrails.config import get_create_guardrail_payload, GUARDRAIL_NAME
from agentcore.policies.config import (
    get_create_policy_engine_payload,
    POLICY_ENGINE_NAME,
    POLICY_NAME,
    ENFORCEMENT_MODE,
    VALIDATION_MODE,
)
from agentcore.gateway.config import (
    get_create_gateway_payload,
    get_diagnostics_target_payload,
    get_broker_target_payload,
    GATEWAY_NAME,
)
from agentcore.harness.config import get_create_harness_payload, HARNESS_NAME

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"


def render_live_cedar_policies(gateway_arn: str, use_context_input: bool = True) -> list:
    """Renders individual single-statement Cedar policies bound to the real deployed Gateway ARN."""
    ctx_attr = "context.input.action_id" if use_context_input else "context.action_id"
    diag_stmt = f"""permit (
    principal is AgentCore::IamEntity,
    action == AgentCore::Action::"blastgatediag___get_incident_diagnostics",
    resource == AgentCore::Gateway::"{gateway_arn}"
)
when {{
    principal.id like "AROAEXAMPLEPUBLICROLE1*" ||
    principal.id like "arn:aws:*::{ACCOUNT_ID}:*blastgate-agent-role*"
}};""".strip()

    broker_stmt = f"""permit (
    principal is AgentCore::IamEntity,
    action == AgentCore::Action::"blastgatebroker___propose_worker_replacement",
    resource == AgentCore::Gateway::"{gateway_arn}"
)
when {{
    (principal.id like "AROAEXAMPLEPUBLICROLE1*" || principal.id like "arn:aws:*::{ACCOUNT_ID}:*blastgate-agent-role*") &&
    {ctx_attr} == "REPLACE_UNHEALTHY_ECS_WORKER"
}};""".strip()
    return [
        (f"{POLICY_NAME}_diagnostics", diag_stmt, "BlastGate default-deny Cedar policy permitting read-only diagnostics"),
        (POLICY_NAME, broker_stmt, "BlastGate default-deny Cedar policy permitting scoped worker replacement proposal"),
    ]


def ensure_guardrail(bedrock) -> Dict[str, str]:
    existing = bedrock.list_guardrails().get("guardrails", [])
    match = next((g for g in existing if g["name"] == GUARDRAIL_NAME), None)
    if match:
        gid = match["id"]
        garn = match["arn"]
        print(f"[REUSE] Guardrail '{GUARDRAIL_NAME}' -> {garn}")
    else:
        payload = get_create_guardrail_payload()
        resp = bedrock.create_guardrail(**payload)
        gid = resp["guardrailId"]
        garn = resp["guardrailArn"]
        print(f"[CREATED] Guardrail '{GUARDRAIL_NAME}' -> {garn}")

    # Ensure published numeric version
    versions = bedrock.list_guardrails(guardrailIdentifier=gid).get("guardrails", [])
    numeric_versions = [v["version"] for v in versions if v["version"] != "DRAFT"]
    if numeric_versions:
        gver = numeric_versions[-1]
    else:
        ver_resp = bedrock.create_guardrail_version(guardrailIdentifier=gid, description="BlastGate Step 6 live release")
        gver = ver_resp["version"]
        print(f"[PUBLISHED] Guardrail version {gver}")

    return {"guardrailId": gid, "guardrailArn": garn, "guardrailVersion": gver}


def ensure_policy_engine(ctrl) -> Dict[str, str]:
    existing = ctrl.list_policy_engines().get("policyEngines", [])
    match = next((pe for pe in existing if pe["name"] == POLICY_ENGINE_NAME), None)
    if match:
        pe_id = match["policyEngineId"]
        pe_arn = match["policyEngineArn"]
        print(f"[REUSE] PolicyEngine '{POLICY_ENGINE_NAME}' -> {pe_arn}")
    else:
        resp = ctrl.create_policy_engine(**get_create_policy_engine_payload())
        pe_id = resp["policyEngineId"]
        pe_arn = resp["policyEngineArn"]
        print(f"[CREATED] PolicyEngine '{POLICY_ENGINE_NAME}' -> {pe_arn}")

    for _ in range(30):
        status = ctrl.get_policy_engine(policyEngineId=pe_id)["status"]
        if status == "ACTIVE":
            break
        if "FAILED" in status:
            raise RuntimeError(f"PolicyEngine failed: {status}")
        time.sleep(3)

    return {"policyEngineId": pe_id, "policyEngineArn": pe_arn}


def ensure_gateway(ctrl, policy_engine_arn: str) -> Dict[str, str]:
    existing = ctrl.list_gateways().get("items", [])
    match = next((g for g in existing if g["name"] == GATEWAY_NAME), None)
    if match:
        gw_id = match["gatewayId"]
        gw_info = ctrl.get_gateway(gatewayIdentifier=gw_id)
        gw_arn = gw_info["gatewayArn"]
        print(f"[REUSE] Gateway '{GATEWAY_NAME}' -> {gw_arn}")
    else:
        payload = get_create_gateway_payload(policy_engine_arn=policy_engine_arn, enforce_policy=True)
        resp = ctrl.create_gateway(**payload)
        gw_id = resp["gatewayId"]
        gw_arn = resp["gatewayArn"]
        print(f"[CREATED] Gateway '{GATEWAY_NAME}' -> {gw_arn}")

    for _ in range(40):
        gw_info = ctrl.get_gateway(gatewayIdentifier=gw_id)
        status = gw_info["status"]
        if status == "READY":
            break
        if "FAILED" in status:
            raise RuntimeError(f"Gateway failed: {gw_info}")
        time.sleep(4)

    return {"gatewayId": gw_id, "gatewayArn": gw_arn}


def ensure_gateway_targets(ctrl, gateway_id: str):
    existing = ctrl.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
    by_name = {t["name"]: t for t in existing}

    for payload_fn in [get_diagnostics_target_payload, get_broker_target_payload]:
        payload = payload_fn(gateway_identifier=gateway_id)
        tname = payload["name"]
        if tname in by_name:
            tid = by_name[tname]["targetId"]
            print(f"[REUSE] GatewayTarget '{tname}' -> {tid}")
        else:
            resp = ctrl.create_gateway_target(**payload)
            tid = resp["targetId"]
            print(f"[CREATED] GatewayTarget '{tname}' -> {tid}")

        for _ in range(30):
            tinfo = ctrl.get_gateway_target(gatewayIdentifier=gateway_id, targetId=tid)
            if tinfo["status"] == "READY":
                break
            if "FAILED" in tinfo["status"]:
                raise RuntimeError(f"GatewayTarget '{tname}' failed: {tinfo}")
            time.sleep(3)


def ensure_cedar_policy(ctrl, policy_engine_id: str, gateway_arn: str) -> Dict[str, Any]:
    existing = ctrl.list_policies(policyEngineId=policy_engine_id).get("policies", [])
    by_name = {p["name"]: p for p in existing}

    last_pol = None
    for pname, statement, desc in render_live_cedar_policies(gateway_arn=gateway_arn, use_context_input=True):
        if pname in by_name:
            pol = by_name[pname]
            if pol.get("status") == "CREATE_FAILED":
                ctrl.delete_policy(policyEngineId=policy_engine_id, policyId=pol["policyId"])
                print(f"[CLEANUP] Deleted failed policy '{pname}' -> {pol['policyId']}")
            else:
                print(f"[REUSE] Cedar Policy '{pname}' -> {pol['policyId']}")
                last_pol = pol
                continue
        pol = ctrl.create_policy(
            name=pname,
            policyEngineId=policy_engine_id,
            definition={"cedar": {"statement": statement}},
            enforcementMode=ENFORCEMENT_MODE,
            validationMode=VALIDATION_MODE,
            description=desc,
        )
        pid = pol["policyId"]
        for _ in range(30):
            pinfo = ctrl.get_policy(policyEngineId=policy_engine_id, policyId=pid)
            if pinfo["status"] == "ACTIVE":
                pol = pinfo
                break
            if "FAILED" in pinfo["status"]:
                raise RuntimeError(f"Policy '{pname}' failed: {pinfo}")
            time.sleep(2)
        print(f"[CREATED] Cedar Policy '{pname}' -> {pid} (status={pol.get('status')})")
        last_pol = pol
    return last_pol


def ensure_harness(ctrl, gateway_arn: str, guardrail_arn: str, guardrail_version: str) -> Dict[str, Any]:
    existing = ctrl.list_harnesses().get("harnesses", [])
    match = next((h for h in existing if h["harnessName"] == HARNESS_NAME), None)
    if match:
        print(f"[REUSE] Harness '{HARNESS_NAME}' -> {match['arn']}")
        return match

    payload = get_create_harness_payload(
        gateway_arn=gateway_arn,
        guardrail_identifier=guardrail_arn,
        guardrail_version=guardrail_version,
    )
    resp = ctrl.create_harness(**payload)["harness"]
    hid = resp["harnessId"]
    print(f"[CREATED] Harness '{HARNESS_NAME}' -> {resp['arn']}")

    for _ in range(30):
        info = ctrl.get_harness(harnessId=hid)["harness"]
        if info["status"] in ("ACTIVE", "READY"):
            return info
        if "FAILED" in info["status"]:
            raise RuntimeError(f"Harness failed: {info}")
        time.sleep(3)
    return resp


def main():
    parser = argparse.ArgumentParser(description="Provision BlastGate AgentCore & Guardrail resources")
    parser.add_argument("--profile", default="antigravity")
    parser.add_argument("--confirm", action="store_true", help="Actually execute AWS resource creation")
    args = parser.parse_args()

    if not args.confirm:
        print("[DRY-RUN] Previewing AgentCore provisioning order (use --confirm after approval):")
        print("  1. Bedrock Guardrail:", GUARDRAIL_NAME)
        print("  2. AgentCore PolicyEngine:", POLICY_ENGINE_NAME)
        print("  3. AgentCore Gateway:", GATEWAY_NAME)
        print("  4. Gateway Lambda Targets: blastgate-diagnostics-target, blastgate-broker-target")
        print("  5. Cedar Policy:", POLICY_NAME)
        print("  6. AgentCore Harness:", HARNESS_NAME, "(amazon.nova-micro-v1:0)")
        return

    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    sts = session.client("sts")
    ident = sts.get_caller_identity()
    assert ident["Account"] == ACCOUNT_ID, f"Unexpected account: {ident['Account']}"
    print(f"[IDENTITY] {ident['Arn']}")

    bedrock = session.client("bedrock")
    ctrl = session.client("bedrock-agentcore-control")

    gr = ensure_guardrail(bedrock)
    pe = ensure_policy_engine(ctrl)
    gw = ensure_gateway(ctrl, policy_engine_arn=pe["policyEngineArn"])
    ensure_gateway_targets(ctrl, gateway_id=gw["gatewayId"])
    pol = ensure_cedar_policy(ctrl, policy_engine_id=pe["policyEngineId"], gateway_arn=gw["gatewayArn"])
    harness = ensure_harness(
        ctrl,
        gateway_arn=gw["gatewayArn"],
        guardrail_arn=gr["guardrailArn"],
        guardrail_version=gr["guardrailVersion"],
    )

    manifest = {
        "guardrail": gr,
        "policyEngine": pe,
        "gateway": gw,
        "policy": {"policyId": pol.get("policyId"), "policyArn": pol.get("policyArn")},
        "harness": {"harnessId": harness["harnessId"], "arn": harness["arn"], "status": harness["status"]},
    }
    print("\n=== AGENTCORE PROVISIONING MANIFEST ===")
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
