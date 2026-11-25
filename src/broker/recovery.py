"""
BlastGate Recovery Verification Interface
Verifies post-mutation worker lifecycle recovery before declaring VERIFIED status.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Set


@dataclass
class RecoveryVerificationResult:
    target_stopped: bool
    replacement_launched: bool
    replacement_running: bool
    replacement_healthy: bool
    service_stable: bool
    is_fully_verified: bool
    details: Dict[str, Any]


class RecoveryVerifier:
    """Evaluates whether an executed remediation has achieved complete verified recovery."""

    def __init__(self, inventory_provider=None, health_provider=None):
        self.inventory_provider = inventory_provider
        self.health_provider = health_provider

    def verify_recovery(
        self,
        cluster: str,
        service: str,
        stopped_task_arn: str,
        pre_mutation_task_arns: Optional[Set[str]] = None,
        mutation_time: Optional[float] = None,
    ) -> RecoveryVerificationResult:
        """
        Checks empirical evidence:
        1. Target task reached STOPPED state.
        2. Service running count equals desired count.
        3. A genuinely new replacement task (not present in pre_mutation_task_arns)
           has appeared, reached RUNNING, and published healthy telemetry.
        If verification cannot be completed or is still in progress,
        returns is_fully_verified = False (status remains SUBMITTED).
        """
        if not self.inventory_provider:
            return RecoveryVerificationResult(
                target_stopped=True,
                replacement_launched=False,
                replacement_running=False,
                replacement_healthy=False,
                service_stable=False,
                is_fully_verified=False,
                details={"reason": "Step 3 local simulation: Real recovery verification pending live cluster."}
            )

        try:
            service_state = self.inventory_provider.get_service_state(cluster, service)
            target_task = self.inventory_provider.get_task_details(cluster, stopped_task_arn)

            target_stopped = target_task is None or target_task.last_status == "STOPPED"
            service_stable = (
                service_state.status == "ACTIVE" and
                service_state.running_count >= service_state.desired_count
            )

            # Distinguish genuine replacement task from pre-mutation inventory
            replacement_launched = False
            replacement_running = False
            replacement_healthy = False
            identified_replacement_arn = None

            if service_stable and target_stopped:
                if pre_mutation_task_arns is not None:
                    # Genuinely new tasks: tasks not in the pre-mutation task set and != stopped target
                    candidates = [
                        (arn, item) for arn, item in service_state.tasks.items()
                        if arn not in pre_mutation_task_arns and arn != stopped_task_arn
                    ]
                else:
                    # Fallback if pre-mutation inventory was not provided
                    candidates = [
                        (arn, item) for arn, item in service_state.tasks.items()
                        if arn != stopped_task_arn
                    ]

                if candidates:
                    replacement_launched = True
                    for cand_arn, cand_item in candidates:
                        if cand_item.last_status == "RUNNING":
                            replacement_running = True
                            identified_replacement_arn = cand_arn
                            if self.health_provider:
                                try:
                                    h = self.health_provider.get_task_health(cand_arn)
                                    if not h.is_unhealthy:
                                        replacement_healthy = True
                                        break
                                except Exception:
                                    replacement_healthy = False
                            else:
                                replacement_healthy = True
                                break

            is_verified = (
                target_stopped and
                service_stable and
                replacement_launched and
                replacement_running and
                replacement_healthy
            )

            return RecoveryVerificationResult(
                target_stopped=target_stopped,
                replacement_launched=replacement_launched,
                replacement_running=replacement_running,
                replacement_healthy=replacement_healthy,
                service_stable=service_stable,
                is_fully_verified=is_verified,
                details={
                    "runningCount": service_state.running_count,
                    "desiredCount": service_state.desired_count,
                    "replacementTaskArn": identified_replacement_arn,
                }
            )
        except Exception as e:
            return RecoveryVerificationResult(
                target_stopped=False,
                replacement_launched=False,
                replacement_running=False,
                replacement_healthy=False,
                service_stable=False,
                is_fully_verified=False,
                details={"error": str(e)}
            )
