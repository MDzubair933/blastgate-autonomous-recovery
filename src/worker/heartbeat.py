"""
BlastGate Worker Heartbeat Publisher
Emits structured telemetry records to DynamoDB or mock transport.
"""

import time
import json
from typing import Dict, Any, Optional
try:
    from .health import HealthSupervisor
    from .config import CLUSTER_NAME, SERVICE_NAME, TASK_FAMILY, HEARTBEAT_TABLE_NAME
except (ImportError, ValueError):
    from health import HealthSupervisor
    from config import CLUSTER_NAME, SERVICE_NAME, TASK_FAMILY, HEARTBEAT_TABLE_NAME


class HeartbeatPublisher:
    """Periodically publishes health telemetry."""

    def __init__(
        self,
        task_arn: str,
        supervisor: HealthSupervisor,
        dynamodb_client=None,
        table_name: str = HEARTBEAT_TABLE_NAME,
    ):
        self.task_arn = task_arn
        self.supervisor = supervisor
        self.client = dynamodb_client
        self.table_name = table_name
        self.last_published_record: Optional[Dict[str, Any]] = None

    def publish_once(self) -> Dict[str, Any]:
        """Evaluates health and writes telemetry record."""
        health = self.supervisor.evaluate_health()
        now = health["timestamp"]

        record = {
            "task_arn": self.task_arn,
            "cluster_name": CLUSTER_NAME,
            "service_name": SERVICE_NAME,
            "task_family": TASK_FAMILY,
            "processing_state": health["processing_state"],
            "is_unhealthy": health["is_unhealthy"],
            "timestamp": now,
            "processing_age": health["processing_age"],
            "processed_count": health["processed_count"],
            "schema_version": "1.0.0",
            "details": health["details"],
        }

        if self.client:
            item = {
                "task_arn": {"S": self.task_arn},
                "cluster_name": {"S": CLUSTER_NAME},
                "service_name": {"S": SERVICE_NAME},
                "task_family": {"S": TASK_FAMILY},
                "processing_state": {"S": health["processing_state"]},
                "is_unhealthy": {"BOOL": health["is_unhealthy"]},
                "timestamp": {"N": str(now)},
                "payload_json": {"S": json.dumps(record, sort_keys=True)},
            }
            self.client.put_item(
                TableName=self.table_name,
                Item=item,
            )

        self.last_published_record = record
        return record
