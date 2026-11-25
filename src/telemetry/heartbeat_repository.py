"""
BlastGate Heartbeat Repository
Interface and implementations for accessing worker heartbeats from DynamoDB or in-memory stores.
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
try:
    from .models import WorkerHeartbeat
except (ImportError, ValueError):
    from models import WorkerHeartbeat


class HeartbeatRepository(ABC):
    """Abstract interface for reading and writing worker heartbeats."""

    @abstractmethod
    def save_heartbeat(self, heartbeat: WorkerHeartbeat):
        pass

    @abstractmethod
    def get_heartbeat(self, task_arn: str) -> Optional[WorkerHeartbeat]:
        pass


class MockHeartbeatRepository(HeartbeatRepository):
    """Deterministic in-memory heartbeat repository for testing."""

    def __init__(self):
        self.heartbeats: Dict[str, WorkerHeartbeat] = {}

    def save_heartbeat(self, heartbeat: WorkerHeartbeat):
        self.heartbeats[heartbeat.task_arn] = heartbeat

    def get_heartbeat(self, task_arn: str) -> Optional[WorkerHeartbeat]:
        return self.heartbeats.get(task_arn)


class DynamoDbHeartbeatRepository(HeartbeatRepository):
    """Production DynamoDB heartbeat repository."""

    def __init__(self, dynamodb_client=None, table_name: str = "blastgate-heartbeats", client=None):
        self.client = client or dynamodb_client
        self.table_name = table_name

    def _to_dynamo_item(self, heartbeat: WorkerHeartbeat) -> Dict[str, Any]:
        return {
            "task_arn": {"S": heartbeat.task_arn},
            "cluster_name": {"S": heartbeat.cluster_name},
            "service_name": {"S": heartbeat.service_name},
            "task_family": {"S": heartbeat.task_family},
            "processing_state": {"S": heartbeat.processing_state},
            "is_unhealthy": {"BOOL": heartbeat.is_unhealthy},
            "timestamp": {"N": str(heartbeat.timestamp)},
            "processed_count": {"N": str(heartbeat.processed_count)},
            "processing_age": {"N": str(heartbeat.processing_age)},
            "payload_json": {"S": json.dumps(heartbeat.to_dict(), sort_keys=True)},
        }

    def _from_dynamo_item(self, item: Dict[str, Any]) -> WorkerHeartbeat:
        raw = item.get("payload_json", {}).get("S")
        if raw:
            return WorkerHeartbeat.from_dict(json.loads(raw))

        return WorkerHeartbeat(
            task_arn=item.get("task_arn", {}).get("S", ""),
            cluster_name=item.get("cluster_name", {}).get("S", "blastgate-sandbox"),
            service_name=item.get("service_name", {}).get("S", "blastgate-workers"),
            task_family=item.get("task_family", {}).get("S", "blastgate-worker"),
            processing_state=item.get("processing_state", {}).get("S", "UNKNOWN"),
            is_unhealthy=item.get("is_unhealthy", {}).get("BOOL", False),
            timestamp=float(item.get("timestamp", {}).get("N", "0")),
            processing_age=float(item.get("processing_age", {}).get("N", "0")),
            processed_count=int(item.get("processed_count", {}).get("N", "0")),
        )

    def save_heartbeat(self, heartbeat: WorkerHeartbeat):
        if not self.client:
            return
        self.client.put_item(
            TableName=self.table_name,
            Item=self._to_dynamo_item(heartbeat)
        )

    def get_heartbeat(self, task_arn: str) -> Optional[WorkerHeartbeat]:
        if not self.client:
            return None
        resp = self.client.get_item(
            TableName=self.table_name,
            Key={"task_arn": {"S": task_arn}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        return self._from_dynamo_item(item)
