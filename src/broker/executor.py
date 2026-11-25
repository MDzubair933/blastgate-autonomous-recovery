"""
BlastGate Approved ECS Mutation Executor (The Mutation Boundary)
Calls ecs:StopTask strictly for a verified, pre-authorized worker target.
Rejects unvalidated user proposals, multi-task stops, and arbitrary AWS APIs.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

from config import ALLOWED_CLUSTER
from errors import TargetNotAllowlistedError, UnauthorizedActionError, InternalBrokerError


@dataclass(frozen=True)
class BrokerAuthorization:
    decision_id: str
    incident_id: str
    action_id: str
    target_task_arn: str
    cluster_name: str
    reservation_id: str
    authorized_at: float
    pre_mutation_task_arns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ExecutionResult:
    execution_status: str  # SUBMITTED, FAILED, UNKNOWN
    aws_request_id: Optional[str]
    details: Dict[str, Any]


class EcsMutationExecutor:
    """Sovereign executor holding the single scoped ecs:StopTask mutation authority."""

    def __init__(self, ecs_client=None):
        self.ecs_client = ecs_client

    def execute_approved_replacement(
        self,
        authorization: BrokerAuthorization,
        reason: Optional[str] = None
    ) -> ExecutionResult:
        """
        Executes ecs:StopTask on the single approved worker target.
        Strictly requires an in-process verified BrokerAuthorization object produced by the Broker authorizer.
        """
        # 1. Re-validate authorization invariants
        if authorization.cluster_name != ALLOWED_CLUSTER:
            raise TargetNotAllowlistedError(
                f"Executor refusal: Cluster '{authorization.cluster_name}' is not authorized."
            )
        if authorization.action_id != "REPLACE_UNHEALTHY_ECS_WORKER":
            raise UnauthorizedActionError(
                f"Executor refusal: Action '{authorization.action_id}' is not authorized."
            )
        if not authorization.target_task_arn.startswith(f"arn:aws:ecs:"):
            raise TargetNotAllowlistedError("Executor refusal: Invalid task ARN format.")

        stop_reason = reason or f"BlastGate authorized remediation for incident {authorization.incident_id}"

        # 2. Invoke ecs:StopTask via configured client
        if self.ecs_client is None:
            raise InternalBrokerError("ECS client is not configured in executor.")

        try:
            resp = self.ecs_client.stop_task(
                cluster=authorization.cluster_name,
                task=authorization.target_task_arn,
                reason=stop_reason
            )
            # Capture AWS Request ID for provenance
            request_id = resp.get("ResponseMetadata", {}).get("RequestId")
            task_status = resp.get("task", {}).get("desiredStatus", "STOPPED")

            return ExecutionResult(
                execution_status="SUBMITTED",
                aws_request_id=request_id,
                details={
                    "desiredStatus": task_status,
                    "target_task_arn": authorization.target_task_arn,
                    "cluster": authorization.cluster_name,
                    "incident_id": authorization.incident_id,
                }
            )
        except Exception as e:
            # Distinguish between terminal failure and uncertain network state
            err_str = str(e)
            if "EndpointConnectionError" in err_str or "ConnectTimeoutError" in err_str:
                return ExecutionResult(
                    execution_status="UNKNOWN",
                    aws_request_id=None,
                    details={"error": err_str, "state": "NETWORK_TIMEOUT"}
                )
            return ExecutionResult(
                execution_status="FAILED",
                aws_request_id=None,
                details={"error": err_str, "state": "AWS_API_ERROR"}
            )
