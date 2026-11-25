"""
BlastGate Worker Processing & Loop Tests (T4-001, T4-002)
Tests nominal processing, controlled stall simulation, recovery, and heartbeat publisher.
"""

import time
import pytest
from worker.processor import WorkProcessor
from worker.health import HealthSupervisor
from worker.heartbeat import HeartbeatPublisher
from worker.config import CLUSTER_NAME, SERVICE_NAME, TASK_FAMILY


def test_worker_nominal_processing():
    """T4-001: Worker processes simulated work and increments count."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.15)
        assert processor.is_running is True
        assert processor.processed_count >= 2
        assert processor.is_stalled is False
        assert processor.processing_age < 1.0
    finally:
        processor.stop()


def test_worker_controlled_stall_simulation():
    """T4-002: trigger_controlled_stall stops processing while container stays alive."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.1)
        initial_count = processor.processed_count
        assert initial_count >= 1

        # Trigger controlled stall
        processor.trigger_controlled_stall(reason="Simulated worker lockup")
        assert processor.is_stalled is True

        time.sleep(0.15)
        # Processed count must not advance while stalled
        assert processor.processed_count == initial_count
        # Thread/process remains running
        assert processor.is_running is True
    finally:
        processor.stop()


def test_worker_stall_recovery():
    """Worker resumes processing after reset_stall is invoked."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        processor.trigger_controlled_stall()
        time.sleep(0.1)
        stalled_count = processor.processed_count

        processor.reset_stall()
        assert processor.is_stalled is False

        time.sleep(0.15)
        assert processor.processed_count > stalled_count
    finally:
        processor.stop()


def test_worker_heartbeat_publisher_record_structure():
    """HeartbeatPublisher emits correctly formatted v1.0.0 telemetry record."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    try:
        time.sleep(0.08)
        supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=5.0)
        task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/5e06f3f870daa3e77006ba0c895029cb"

        publisher = HeartbeatPublisher(task_arn=task_arn, supervisor=supervisor)
        record = publisher.publish_once()

        assert record["task_arn"] == task_arn
        assert record["cluster_name"] == CLUSTER_NAME
        assert record["service_name"] == SERVICE_NAME
        assert record["task_family"] == TASK_FAMILY
        assert record["processing_state"] == "HEALTHY"
        assert record["is_unhealthy"] is False
        assert record["schema_version"] == "1.0.0"
        assert record["processed_count"] >= 1
        assert "timestamp" in record
    finally:
        processor.stop()


def test_worker_graceful_shutdown():
    """Worker terminates thread cleanly on stop()."""
    processor = WorkProcessor(interval_seconds=0.05)
    processor.start()
    assert processor.is_running is True
    processor.stop()
    assert processor.is_running is False
    assert processor._thread.is_alive() is False
