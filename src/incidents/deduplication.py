"""
BlastGate Incident Deduplication Manager
Prevents duplicate CloudWatch alarm events from triggering duplicate active incidents.
"""

from typing import Optional, Dict, Any
try:
    from .models import IncidentRecord
    from .repository import IncidentRepository
except (ImportError, ValueError):
    from models import IncidentRecord
    from repository import IncidentRepository


class IncidentDeduplicator:
    """Manages active incident lifecycle and deduplication."""

    def __init__(self, repository: IncidentRepository):
        self.repository = repository

    def process_alarm_transition(
        self,
        alarm_name: str,
        new_state: str,
        target_task_arn: Optional[str],
        timestamp: float,
        cluster_name: str = "blastgate-sandbox",
        service_name: str = "blastgate-workers",
    ) -> IncidentRecord:
        """
        - If new_state == "ALARM":
          - If open incident exists for this alarm, update it (deduplicate).
          - Otherwise create a fresh OPEN incident with a deterministic inc-<hash> ID.
        - If new_state == "OK":
          - Mark existing open incident as RESOLVED.
        """
        existing = self.repository.find_open_incident_for_alarm(alarm_name)

        if new_state == "ALARM":
            if existing:
                existing.updated_at = timestamp
                existing.updated_timestamp = timestamp
                existing.details["last_alarm_event"] = timestamp
                self.repository.save_incident(existing)
                return existing

            # Create deterministic incident ID (e.g. inc-<16 hex chars>)
            import uuid
            incident_id = f"inc-{uuid.uuid4().hex[:16]}"
            new_inc = IncidentRecord(
                incident_id=incident_id,
                alarm_name=alarm_name,
                state="ALARM",
                cluster_name=cluster_name,
                service_name=service_name,
                target_task_arn=target_task_arn,
                status="OPEN",
                created_at=timestamp,
                updated_at=timestamp,
                created_timestamp=timestamp,
                updated_timestamp=timestamp,
                details={"source": "CloudWatch Alarm state-change event"},
            )
            self.repository.save_incident(new_inc)
            return new_inc

        elif new_state == "OK":
            if existing:
                existing.status = "RESOLVED"
                existing.state = "OK"
                existing.updated_at = timestamp
                existing.updated_timestamp = timestamp
                existing.resolved_timestamp = timestamp
                self.repository.save_incident(existing)
                return existing

            import uuid
            resolved_inc = IncidentRecord(
                incident_id=f"inc-{uuid.uuid4().hex[:16]}",
                alarm_name=alarm_name,
                state="OK",
                cluster_name=cluster_name,
                service_name=service_name,
                target_task_arn=target_task_arn,
                status="RESOLVED",
                created_at=timestamp,
                updated_at=timestamp,
                created_timestamp=timestamp,
                updated_timestamp=timestamp,
                resolved_timestamp=timestamp,
                details={"source": "State resolved without active open incident"},
            )
            self.repository.save_incident(resolved_inc)
            return resolved_inc

        return existing
