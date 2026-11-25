"""
BlastGate Telemetry Models
Defines structured heartbeat evidence format.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class WorkerHeartbeat:
    task_arn: str
    cluster_name: str
    service_name: str
    task_family: str
    processing_state: str  # HEALTHY, STALLED, RECOVERING, UNKNOWN
    is_unhealthy: bool
    timestamp: float
    processing_age: float
    processed_count: int
    schema_version: str = "1.0.0"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_arn": self.task_arn,
            "cluster_name": self.cluster_name,
            "service_name": self.service_name,
            "task_family": self.task_family,
            "processing_state": self.processing_state,
            "is_unhealthy": self.is_unhealthy,
            "timestamp": self.timestamp,
            "processing_age": self.processing_age,
            "processed_count": self.processed_count,
            "schema_version": self.schema_version,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerHeartbeat":
        return cls(
            task_arn=data["task_arn"],
            cluster_name=data.get("cluster_name", "blastgate-sandbox"),
            service_name=data.get("service_name", "blastgate-workers"),
            task_family=data.get("task_family", "blastgate-worker"),
            processing_state=data["processing_state"],
            is_unhealthy=data["is_unhealthy"],
            timestamp=float(data["timestamp"]),
            processing_age=float(data.get("processing_age", 0.0)),
            processed_count=int(data.get("processed_count", 0)),
            schema_version=data.get("schema_version", "1.0.0"),
            details=data.get("details", {}),
        )
