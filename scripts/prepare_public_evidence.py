"""Offline, allowlisted evidence projection. Never invokes AWS or edits originals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))
def project():
    unattended = read("evidence/unattended_recovery/unattended_recovery_raw_evidence.json")
    attacks = read("evidence/step7/raw_adversarial_evidence.json")
    hardening = read("evidence/post_hardening/raw_live_verification_evidence.json")
    chain = unattended["autonomous_chain"]
    descriptions = [
        ("Fault injection", "Recorded AWS observation", "fault_injection_timestamp", "Controlled worker stall recorded; the runner later removes the control record."),
        ("Watchdog", "Source wiring; aggregate run evidence", "scripts/run_unattended_recovery_test.py", "The runner can invoke the watchdog to accelerate detection. Scheduled-only detection is not independently established by this run."),
        ("CloudWatch alarm", "Source wiring; aggregate run evidence", "infrastructure/cdk/stacks/monitoring_stack.py", "Confirmed stalled-worker metric drives the alarm; no separate alarm timestamp is retained in the compact evidence."),
        ("Incident", "Recorded AWS observation", "autonomous_chain.incident_opened", "An incident was detected in DynamoDB."),
        ("EventBridge", "Source wiring; aggregate run evidence", "src/incidents/handler.py", "Incident ingestion emits BlastGate.IncidentOpened; the rule targets the dispatcher."),
        ("Dispatcher", "Recorded AWS observation", "autonomous_chain.dispatch_lock", "A dispatch session was observed. The runner does not invoke the harness or broker."),
        ("AgentCore Harness", "Source wiring; aggregate run evidence", "src/dispatcher/handler.py", "The dispatcher invokes the configured Managed Harness. Compact run JSON does not include a model transcript."),
        ("Cedar Gateway", "Source wiring; separate live Gateway test", "step7.scenario_8", "Scoped Gateway enforcement is separately demonstrated by a live MCP denial. No per-tool Gateway trace is retained for this run."),
        ("Broker authorization", "Recorded AWS observation", "autonomous_chain.remediation_broker_execution", "ALLOW with all eight rule flags true. The captured reason_code contains the action ID; it is not normalized to AUTH_APPROVED."),
        ("ECS replacement", "Recorded AWS observation", "autonomous_chain.ecs_remediation", "Target stopped and a distinct replacement task was observed."),
        ("Healthy recovery", "Recorded AWS observation", "autonomous_chain.ecs_remediation.replacement_healthy", "The replacement published HEALTHY telemetry according to the captured run result."),
    ]
    notes = [
        "Live apply_guardrail and harness interception; the blocked payload is not evidence of model compliance.",
        "Direct live broker denied at inventory validation; ERR_TARGET_NOT_UNHEALTHY came from a separate local validator check.",
        "Direct live broker rejected the action. Cedar configuration was inspected; this scenario does not capture an action-denial Gateway trace.",
        "Local CapacityEngine returned ERR_CAPACITY_QUORUM_VIOLATION. Live broker denied earlier with ERR_TARGET_NOT_ALLOWLISTED at zero capacity; no live broker quorum-branch denial was demonstrated in Scenario 4.",
        "Direct live DynamoDB cooldown refusal plus a separate broker schema rejection; not a broker cooldown-branch execution.",
        "Direct live broker returned a cached ALLOW/SUBMITTED receipt; one historical mutation audit event was found, not a new mutation.",
        "Local processing of synthetic poisoned logs plus live apply_guardrail; not a complete CloudWatch-to-harness poisoned-log run.",
        "Live signed Gateway MCP call returned policy denial -32002. The actual caller is the configured developer identity, not the hypothetical attacker-role field.",
    ]
    categories = ["Live Guardrail / Harness", "Direct Lambda + local engine", "Direct Lambda + policy inspection", "Local engine + direct Lambda", "Direct DynamoDB + Lambda", "Direct Lambda / DynamoDB", "Local engine + live Guardrail", "Live Gateway invocation"]
    scenarios=[]
    for i, (key, value) in enumerate(attacks["scenarios"].items()):
        scenarios.append({"id":value["scenario_id"],"name":value["name"],"category":categories[i],"captured_verdict":value["verdict"],"observed_code":value.get("reason_code", value.get("gateway_mcp_error_code", value.get("guardrail_action"))),"scope":notes[i]})
    result={
        "schema_version":"1.0.0", "kind":"sanitized recorded evidence derivative", "region":unattended["aws_region"],
        "redaction":"Account, ARNs, endpoints, role IDs, task IDs, incident IDs, session IDs and request IDs are omitted or replaced with explicit aliases. Outcomes and captured timestamps are preserved. This is an allowlisted projection, not raw AWS output.",
        "unattended":{
            "source":"evidence/unattended_recovery/unattended_recovery_raw_evidence.json (private)",
            "executed_at":unattended["executed_at"],"fault_injected_at":chain["fault_injection_timestamp"],"cleanup_verified_at":unattended["final_safety_status"]["verified_at"],
            "incident_alias":"incident-unattended-01", "session_alias":"session-unattended-01", "target_alias":"worker-original-01", "replacement_alias":"worker-replacement-01",
            "decision":chain["remediation_broker_execution"]["decision"], "captured_reason_code":chain["remediation_broker_execution"]["reason_code"],
            "rule_results":chain["remediation_broker_execution"]["rule_results"], "target_stopped":chain["ecs_remediation"]["target_stopped"], "replacement_healthy":chain["ecs_remediation"]["replacement_healthy"],
            "distinct_replacement":chain["target_task_stalled"]!=chain["ecs_remediation"]["replacement_task_arn"],
            "dispatch_session_observed":bool(chain["dispatch_lock"]["session_id"]),"verdict":unattended["verdict"],"cleanup":unattended["final_safety_status"],
            "stages":[{"name":n,"category":c,"reference":ref,"description":d} for n,c,ref,d in descriptions],
            "limitations":["Intermediate stage timestamps and the complete model/tool transcript are not retained in this compact evidence.","The runner can invoke the watchdog; it does not manually invoke the harness or broker.","The external final report includes additional timing and audit details not independently retained in this JSON. Its signature and cost claims are not adopted.","Cedar policy-engine ACTIVE is captured; Gateway ENFORCE is configuration/other-run evidence, not a captured final-safety field here.","The audit digest is a source fingerprint, not a signature or an independently verified complete chain."],
        },
        "step7":{"executed_at":attacks["executed_at"],"scenarios":scenarios,"limitation":"The historical prose report and saved JSON contain identifiers from different runs. This derivative uses saved JSON outcomes and does not merge request IDs."},
        "post_hardening":{"executed_at":hardening["executed_at"],"verdict":hardening["verdict"],"checks":[{"name":v["name"],"passed":v["passed"],"decision":v.get("decision"),"reason_code":v.get("reason_code")} for v in hardening["tests"].values()]},
        "step6":{"category":"Historical live recovery report","source":"docs/STEP_6_VERIFICATION_REPORT.md (private historical report)","scope":"Reports live harness diagnostics, broker approval, StopTask and healthy replacement. Unlike the later unattended run, automatic dispatch is not established by Step 6 alone."},
    }
    serialized=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    for rel in ["evidence/public/recorded-evidence.json","dashboard/src/data/recorded-evidence.json","dashboard/public/evidence/recorded-evidence.json"]:
        p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(serialized,encoding="utf-8")
    print("Prepared three identical public projections; original evidence unchanged.")
if __name__=="__main__": project()
