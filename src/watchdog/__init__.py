"""
BlastGate Watchdog Package
Scheduled health monitoring, custom metric emission, and incident detection.
"""

from .config import CLOUDWATCH_NAMESPACE, CLUSTER_NAME, SERVICE_NAME, STALLED_METRIC_NAME
from .inventory import WatchdogInventoryReader
from .evaluator import WatchdogEvaluator
from .metrics import WatchdogMetricsEmitter
from .incidents import WatchdogIncidentDetector
from .handler import lambda_handler

__all__ = [
    "CLOUDWATCH_NAMESPACE",
    "CLUSTER_NAME",
    "SERVICE_NAME",
    "STALLED_METRIC_NAME",
    "WatchdogInventoryReader",
    "WatchdogEvaluator",
    "WatchdogMetricsEmitter",
    "WatchdogIncidentDetector",
    "lambda_handler",
]
