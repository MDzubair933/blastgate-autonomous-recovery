"""
BlastGate Telemetry Freshness Engine
Enforces 120-second freshness window and rejects future timestamps.
"""

import time
from typing import Dict, Any
try:
    from .models import WorkerHeartbeat
except (ImportError, ValueError):
    from models import WorkerHeartbeat


class FreshnessEvaluator:
    """Evaluates temporal validity of worker telemetry."""

    def __init__(self, freshness_threshold_seconds: float = 120.0, current_time_fn=None):
        self.freshness_threshold_seconds = freshness_threshold_seconds
        self.current_time_fn = current_time_fn or time.time

    def evaluate(self, heartbeat: WorkerHeartbeat) -> Dict[str, Any]:
        """
        Evaluates age of heartbeat:
        - If age > threshold: STALE
        - If age < -5s (clock skew into future): INVALID_FUTURE
        - Otherwise: FRESH
        """
        now = self.current_time_fn()
        age = now - heartbeat.timestamp

        if age > self.freshness_threshold_seconds:
            return {
                "is_fresh": False,
                "status": "STALE",
                "age_seconds": age,
                "message": f"Heartbeat is stale ({age:.1f}s old > {self.freshness_threshold_seconds}s limit)",
            }

        if age < -5.0:
            return {
                "is_fresh": False,
                "status": "CLOCK_SKEW_FUTURE",
                "age_seconds": age,
                "message": f"Heartbeat timestamp is in the future ({abs(age):.1f}s ahead of system time)",
            }

        return {
            "is_fresh": True,
            "status": "FRESH",
            "age_seconds": age,
            "message": "Telemetry is fresh and temporally valid",
        }
