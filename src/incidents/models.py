"""
BlastGate Incident Models
Structured representation of confirmed operational incidents.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class IncidentRecord:
    incident_id: str
    alarm_name: str
    cluster_name: str = "blastgate-sandbox"
    service_name: str = "blastgate-workers"
    target_task_arn: Optional[str] = None
    status: str = "OPEN"  # OPEN, RESOLVED, UNKNOWN
    state: str = "ALARM"  # ALARM, OK, INSUFFICIENT_DATA
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_timestamp: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    created_timestamp: Optional[float] = None
    updated_timestamp: Optional[float] = None

    def __post_init__(self):
        if self.created_timestamp is not None:
            self.created_at = self.created_timestamp
        else:
            self.created_timestamp = self.created_at

        if self.updated_timestamp is not None:
            self.updated_at = self.updated_timestamp
        else:
            self.updated_timestamp = self.updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "alarm_name": self.alarm_name,
            "state": self.state,
            "cluster_name": self.cluster_name,
            "service_name": self.service_name,
            "target_task_arn": self.target_task_arn,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_timestamp": self.created_timestamp,
            "updated_timestamp": self.updated_timestamp,
            "resolved_timestamp": self.resolved_timestamp,
            "details": self.details,
        }
