"""
BlastGate Health Evidence Telemetry Validator
Unified validator combining repository lookup, identity cross-referencing, and freshness evaluation.
"""

from typing import Dict, Any, Optional
try:
    from .models import WorkerHeartbeat
    from .heartbeat_repository import HeartbeatRepository, MockHeartbeatRepository
    from .freshness import FreshnessEvaluator
    from .ecs_identity import EcsIdentityValidator
except (ImportError, ValueError):
    from models import WorkerHeartbeat
    from heartbeat_repository import HeartbeatRepository, MockHeartbeatRepository
    from freshness import FreshnessEvaluator
    from ecs_identity import EcsIdentityValidator


class TelemetryValidator:
    """Produces verified health evidence for broker consumption."""

    def __init__(
        self,
        repository: HeartbeatRepository,
        freshness_evaluator: Optional[FreshnessEvaluator] = None,
        identity_validator: Optional[EcsIdentityValidator] = None,
    ):
        self.repository = repository
        self.freshness = freshness_evaluator or FreshnessEvaluator()
        self.identity = identity_validator or EcsIdentityValidator()

    def get_validated_evidence(self, task_arn: str) -> Dict[str, Any]:
        """
        Fails closed on:
        1. Invalid task ARN or wrong cluster/account.
        2. Missing heartbeat.
        3. Stale heartbeat (> 120s).
        4. Unknown processing state.
        """
        # 1. Identity Validation
        id_check = self.identity.validate_task_arn(task_arn)
        if not id_check["is_valid"]:
            return {
                "is_valid_evidence": False,
                "is_unhealthy": False,
                "reason": "IDENTITY_REJECTED",
                "error": id_check["error"],
            }

        # 2. Repository Lookup
        heartbeat = self.repository.get_heartbeat(task_arn)
        if not heartbeat:
            return {
                "is_valid_evidence": False,
                "is_unhealthy": False,
                "reason": "MISSING_TELEMETRY",
                "error": f"No heartbeat found for task {task_arn}",
            }

        # 3. Freshness Check
        fresh_check = self.freshness.evaluate(heartbeat)
        if not fresh_check["is_fresh"]:
            return {
                "is_valid_evidence": False,
                "is_unhealthy": False,
                "reason": fresh_check["status"],
                "error": fresh_check["message"],
            }

        # 4. Processing State Check
        if heartbeat.processing_state not in ["HEALTHY", "STALLED"]:
            return {
                "is_valid_evidence": False,
                "is_unhealthy": False,
                "reason": "UNKNOWN_STATE",
                "error": f"Invalid processing state: {heartbeat.processing_state}",
            }

        return {
            "is_valid_evidence": True,
            "task_arn": task_arn,
            "processing_state": heartbeat.processing_state,
            "is_unhealthy": heartbeat.is_unhealthy,
            "timestamp": heartbeat.timestamp,
            "age_seconds": fresh_check["age_seconds"],
            "details": heartbeat.details,
        }
