"""
BlastGate Diagnostics Response Builder
Assembles structured, bounded diagnostic report with runbook references.
"""

from typing import Dict, Any, Optional


class DiagnosticsResponseBuilder:
    """Constructs the structured diagnostic response for LLM agent consumption."""

    def build_response(
        self,
        incident: Dict[str, Any],
        ecs_state: Optional[Dict[str, Any]],
        health_evidence: Dict[str, Any],
        log_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        task_arn = incident.get("target_task_arn") or (ecs_state.get("task_arn") if ecs_state else None)

        is_stalled = health_evidence.get("processing_state") == "STALLED"
        is_fresh = health_evidence.get("is_valid_evidence", False)

        suggested_action = None
        if is_stalled and is_fresh:
            suggested_action = {
                "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
                "runbook_id": "RB-ECS-001",
                "target_task_arn": task_arn,
                "notes": "Empirical health evidence indicates processing stall. Proposal can be submitted to Broker.",
            }

        return {
            "incident_id": incident.get("incident_id"),
            "alarm_name": incident.get("alarm_name"),
            "status": incident.get("status"),
            "target_task_arn": task_arn,
            "ecs_state": ecs_state,
            "health_evidence": {
                "is_valid": is_fresh,
                "processing_state": health_evidence.get("processing_state", "UNKNOWN"),
                "is_unhealthy": health_evidence.get("is_unhealthy", False),
                "age_seconds": health_evidence.get("age_seconds"),
            },
            "untrusted_log_evidence": log_evidence,
            "suggested_action": suggested_action,
            "authority_notice": "SUGGESTIONS ONLY: Only the sovereign Remediation Broker holds execution authority.",
        }
