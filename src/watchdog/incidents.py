"""
BlastGate Watchdog Incident Assessment
Identifies whether empirical conditions justify an operational incident.
"""

from typing import Dict, Any, Optional


class WatchdogIncidentDetector:
    """Evaluates whether an actionable incident exists."""

    def check_for_incident(self, evaluation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Returns incident proposal data if ConfirmedStalledWorkerCount >= 1.
        Otherwise returns None.
        """
        stalled_count = evaluation.get("confirmed_stalled_count", 0)
        stalled_arns = evaluation.get("stalled_task_arns", [])

        if stalled_count >= 1 and stalled_arns:
            return {
                "detected": True,
                "target_task_arn": stalled_arns[0],
                "stalled_count": stalled_count,
                "healthy_count": evaluation.get("healthy_count", 0),
                "desired_count": evaluation.get("desired_count", 0),
            }
        return None
