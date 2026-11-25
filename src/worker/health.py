"""
BlastGate Worker Health Supervisor
Independently inspects the processor state and computes current health telemetry.
Critical design invariant:
When processing stalls, the supervisor continues reporting fresh, independently observable STALLED state.
"""

import time
from typing import Dict, Any
try:
    from .processor import WorkProcessor
except (ImportError, ValueError):
    from processor import WorkProcessor


class HealthSupervisor:
    """Supervises local worker components and reports objective health evidence."""

    def __init__(self, processor: WorkProcessor, stall_threshold_seconds: float = 15.0):
        self.processor = processor
        self.stall_threshold_seconds = stall_threshold_seconds

    def evaluate_health(self) -> Dict[str, Any]:
        """
        Computes empirical health status:
        - HEALTHY: Processor actively executing work (age < stall_threshold_seconds).
        - STALLED: Processing stopped or explicitly stalled, but container alive.
        """
        now = time.time()
        age = self.processor.processing_age

        if self.processor.is_stalled or age > self.stall_threshold_seconds:
            return {
                "processing_state": "STALLED",
                "is_unhealthy": True,
                "timestamp": now,
                "processing_age": age,
                "processed_count": self.processor.processed_count,
                "details": {"reason": getattr(self.processor, "_stall_reason", "Processing heartbeat timeout")},
            }

        return {
            "processing_state": "HEALTHY",
            "is_unhealthy": False,
            "timestamp": now,
            "processing_age": age,
            "processed_count": self.processor.processed_count,
            "details": {"status": "Processing loop nominal"},
        }
