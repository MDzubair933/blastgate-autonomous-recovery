"""
BlastGate Worker Application Package
Implements background queue worker with independent health supervisor and controlled failure injection.
"""

from .config import (
    CLUSTER_NAME,
    SERVICE_NAME,
    TASK_FAMILY,
    HEARTBEAT_INTERVAL_SECONDS,
    PROCESSOR_INTERVAL_SECONDS,
    STALL_THRESHOLD_SECONDS,
    HEARTBEAT_TABLE_NAME,
)
from .processor import WorkProcessor
from .health import HealthSupervisor
from .heartbeat import HeartbeatPublisher

__all__ = [
    "CLUSTER_NAME",
    "SERVICE_NAME",
    "TASK_FAMILY",
    "HEARTBEAT_INTERVAL_SECONDS",
    "PROCESSOR_INTERVAL_SECONDS",
    "STALL_THRESHOLD_SECONDS",
    "HEARTBEAT_TABLE_NAME",
    "WorkProcessor",
    "HealthSupervisor",
    "HeartbeatPublisher",
]
