"""
BlastGate Incident Repository
Persistence interface for incident records in DynamoDB blastgate-incidents or in-memory mock.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
try:
    from .models import IncidentRecord
except (ImportError, ValueError):
    from models import IncidentRecord


class IncidentRepository(ABC):
    """Abstract interface for managing incident records."""

    @abstractmethod
    def save_incident(self, incident: IncidentRecord):
        pass

    @abstractmethod
    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        pass

    @abstractmethod
    def find_open_incident_for_alarm(self, alarm_name: str) -> Optional[IncidentRecord]:
        pass

    def get_active_incident_by_alarm(self, alarm_name: str) -> Optional[IncidentRecord]:
        return self.find_open_incident_for_alarm(alarm_name)


class MockIncidentRepository(IncidentRepository):
    """Deterministic in-memory incident repository for testing."""

    def __init__(self):
        self.incidents: Dict[str, IncidentRecord] = {}

    def save_incident(self, incident: IncidentRecord):
        self.incidents[incident.incident_id] = incident

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        return self.incidents.get(incident_id)

    def find_open_incident_for_alarm(self, alarm_name: str) -> Optional[IncidentRecord]:
        for inc in self.incidents.values():
            if inc.alarm_name == alarm_name and inc.status == "OPEN":
                return inc
        return None

    def list_incidents(self) -> List[IncidentRecord]:
        return list(self.incidents.values())


class DynamoDbIncidentRepository(IncidentRepository):
    """Production DynamoDB incident repository."""

    def __init__(self, dynamodb_client=None, table_name: str = "blastgate-incidents"):
        self.client = dynamodb_client
        self.table_name = table_name

    def save_incident(self, incident: IncidentRecord):
        if not self.client:
            return
        import json
        self.client.put_item(
            TableName=self.table_name,
            Item={
                "incident_id": {"S": incident.incident_id},
                "alarm_name": {"S": incident.alarm_name},
                "cluster_name": {"S": incident.cluster_name},
                "service_name": {"S": incident.service_name},
                "target_task_arn": {"S": incident.target_task_arn or ""},
                "status": {"S": incident.status},
                "state": {"S": incident.state},
                "created_at": {"N": str(incident.created_at)},
                "updated_at": {"N": str(incident.updated_at)},
                "payload_json": {"S": json.dumps(incident.to_dict(), sort_keys=True)},
            }
        )

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        if not self.client:
            return None
        import json
        resp = self.client.get_item(
            TableName=self.table_name,
            Key={"incident_id": {"S": incident_id}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None

        raw = item.get("payload_json", {}).get("S")
        if raw:
            data = json.loads(raw)
            return IncidentRecord(**data)
        return None

    def find_open_incident_for_alarm(self, alarm_name: str) -> Optional[IncidentRecord]:
        if not self.client:
            return None
        import json
        resp = self.client.scan(
            TableName=self.table_name,
            FilterExpression="alarm_name = :a AND #s = :st",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":a": {"S": alarm_name},
                ":st": {"S": "OPEN"},
            },
        )
        items = resp.get("Items", [])
        if not items:
            return None
        # Return most recently updated open incident
        items.sort(key=lambda x: float(x.get("updated_at", {}).get("N", "0")), reverse=True)
        raw = items[0].get("payload_json", {}).get("S")
        if raw:
            return IncidentRecord(**json.loads(raw))
        return None

    def find_latest_stalled_task_arn(
        self,
        heartbeat_table_name: str = "blastgate-heartbeats",
        max_age_seconds: float = 120.0,
    ) -> Optional[str]:
        if not self.client:
            return None
        import time
        resp = self.client.scan(
            TableName=heartbeat_table_name,
            FilterExpression="processing_state = :ps AND is_unhealthy = :u",
            ExpressionAttributeValues={
                ":ps": {"S": "STALLED"},
                ":u": {"BOOL": True},
            },
        )
        now = time.time()
        candidates = []
        for item in resp.get("Items", []):
            arn = item.get("task_arn", {}).get("S", "")
            if not arn.startswith("arn:aws:ecs:"):
                continue
            ts = float(item.get("timestamp", {}).get("N", "0"))
            if (now - ts) <= max_age_seconds:
                candidates.append((ts, arn))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
