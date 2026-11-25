"""
BlastGate Diagnostics Health Reader
Reads empirical application health evidence.
"""

from typing import Optional, Dict, Any


class HealthStateReader:
    """Reads health telemetry evidence."""

    def __init__(self, telemetry_validator=None, repository=None):
        if telemetry_validator:
            self.validator = telemetry_validator
        elif repository:
            try:
                from telemetry.validator import TelemetryValidator
            except (ImportError, ValueError):
                from ..telemetry.validator import TelemetryValidator
            self.validator = TelemetryValidator(repository=repository)
        else:
            self.validator = None

    def get_health_evidence(self, task_arn: str) -> Dict[str, Any]:
        if not self.validator:
            return {"is_valid_evidence": False, "is_unhealthy": False, "reason": "NO_VALIDATOR"}
        return self.validator.get_validated_evidence(task_arn)
