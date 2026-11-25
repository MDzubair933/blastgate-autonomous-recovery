"""
BlastGate Diagnostics Incident Reader
Fetches trusted incident record from DynamoDB or injected repository.
"""

import json
import os
from typing import Optional, Dict, Any


class IncidentReader:
    """Reads incident records from repository or live DynamoDB."""

    def __init__(self, incident_repository=None, repository=None, dynamodb_client=None, table_name: str = None):
        self.repository = repository or incident_repository
        self.dynamodb_client = dynamodb_client
        self.table_name = table_name or os.environ.get("INCIDENT_TABLE_NAME", "blastgate-incidents")

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        if self.repository:
            inc = self.repository.get_incident(incident_id)
            return inc.to_dict() if inc else None

        if self.dynamodb_client:
            resp = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={"incident_id": {"S": incident_id}},
                ConsistentRead=True,
            )
            item = resp.get("Item")
            if not item:
                return None
            raw = item.get("payload_json", {}).get("S")
            if raw:
                return json.loads(raw)
            return {
                "incident_id": item.get("incident_id", {}).get("S", incident_id),
                "alarm_name": item.get("alarm_name", {}).get("S", ""),
                "cluster_name": item.get("cluster_name", {}).get("S", "blastgate-sandbox"),
                "service_name": item.get("service_name", {}).get("S", "blastgate-workers"),
                "target_task_arn": item.get("target_task_arn", {}).get("S", ""),
                "status": item.get("status", {}).get("S", "UNKNOWN"),
                "state": item.get("state", {}).get("S", "UNKNOWN"),
            }

        return None
