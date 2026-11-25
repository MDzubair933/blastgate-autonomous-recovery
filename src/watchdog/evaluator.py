"""
BlastGate Watchdog Health Evaluator
Cross-references running ECS tasks with heartbeat telemetry.
Safety invariant: Desired count == 0 does NOT trigger a false incident.
"""

from typing import Dict, Any, List


class WatchdogEvaluator:
    """Evaluates aggregate worker health for custom metrics."""

    def __init__(self, telemetry_validator):
        self.telemetry_validator = telemetry_validator

    def evaluate_service_health(self, service_inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates:
        - desired_count
        - healthy_count
        - confirmed_stalled_count
        - unknown_count
        - stalled_task_arns (list of confirmed stalled workers)
        """
        desired = service_inventory.get("desired_count", 0)
        running = service_inventory.get("running_count", 0)
        task_arns = service_inventory.get("task_arns", [])

        # Safety rule: Distinguish intentional scale-to-zero from unexpected total outage
        if desired == 0:
            return {
                "desired_count": 0,
                "healthy_count": 0,
                "confirmed_stalled_count": 0,
                "unknown_count": 0,
                "stalled_task_arns": [],
                "is_scaled_to_zero": True,
                "is_total_outage": False,
            }

        if running == 0:
            # Unexpected total service outage: desired > 0 but running == 0!
            # Note: confirmed_stalled is 0 because no tasks are running to stop,
            # but is_total_outage alerts operators to infrastructure failure.
            return {
                "desired_count": desired,
                "healthy_count": 0,
                "confirmed_stalled_count": 0,
                "unknown_count": 0,
                "stalled_task_arns": [],
                "is_scaled_to_zero": False,
                "is_total_outage": True,
                "outage_reason": f"CRITICAL: Desired count is {desired} but 0 tasks are running (unexpected total service outage).",
            }

        healthy = 0
        confirmed_stalled = 0
        unknown = 0
        stalled_arns: List[str] = []

        for arn in task_arns:
            evidence = self.telemetry_validator.get_validated_evidence(arn)
            if not evidence["is_valid_evidence"]:
                unknown += 1
            elif evidence["processing_state"] == "STALLED":
                confirmed_stalled += 1
                stalled_arns.append(arn)
            elif evidence["processing_state"] == "HEALTHY":
                healthy += 1
            else:
                unknown += 1

        return {
            "desired_count": desired,
            "healthy_count": healthy,
            "confirmed_stalled_count": confirmed_stalled,
            "unknown_count": unknown,
            "stalled_task_arns": stalled_arns,
            "is_scaled_to_zero": False,
            "is_total_outage": False,
        }
