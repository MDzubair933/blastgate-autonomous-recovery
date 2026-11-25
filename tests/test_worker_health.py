"""
BlastGate Worker Health Supervisor Tests (T4-003, T4-004)
Tests health evaluation, stall detection, threshold timeout, and active supervisor during failure.
"""

import time
import pytest
from worker.processor import WorkProcessor
from worker.health import HealthSupervisor


def test_health_supervisor_nominal_state():
    """T4-004: Supervisor reports HEALTHY when processor is actively running."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.1)
        supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=10.0)
        health = supervisor.evaluate_health()

        assert health["processing_state"] == "HEALTHY"
        assert health["is_unhealthy"] is False
        assert health["processing_age"] < 1.0
        assert health["processed_count"] >= 1
        assert health["details"]["status"] == "Processing loop nominal"
    finally:
        processor.stop()


def test_health_supervisor_detects_controlled_stall():
    """T4-003: Supervisor reports STALLED immediately upon explicit controlled stall."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.1)
        supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=10.0)

        processor.trigger_controlled_stall(reason="Simulated hung request")
        health = supervisor.evaluate_health()

        assert health["processing_state"] == "STALLED"
        assert health["is_unhealthy"] is True
        assert health["details"]["reason"] == "Simulated hung request"
    finally:
        processor.stop()


def test_health_supervisor_detects_threshold_breach():
    """Supervisor reports STALLED when processing age exceeds stall_threshold_seconds."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.08)
        # Low threshold of 0.15s for testing threshold breach
        supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=0.15)
        health_initial = supervisor.evaluate_health()
        assert health_initial["processing_state"] == "HEALTHY"

        # Stop processor without setting stall flag -> age will grow
        processor.stop()
        time.sleep(0.25)

        health_breached = supervisor.evaluate_health()
        assert health_breached["processing_state"] == "STALLED"
        assert health_breached["is_unhealthy"] is True
        assert health_breached["processing_age"] >= 0.20
    finally:
        if processor.is_running:
            processor.stop()


def test_health_supervisor_stays_alive_during_stall():
    """Supervisor continues to return fresh timestamps and evaluations while worker is stalled."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=5.0)
        processor.trigger_controlled_stall(reason="Memory limit reached")

        t1 = supervisor.evaluate_health()["timestamp"]
        time.sleep(0.05)
        t2 = supervisor.evaluate_health()["timestamp"]

        assert t2 > t1, "Health supervisor must continue updating its evaluation timestamps"
    finally:
        processor.stop()
