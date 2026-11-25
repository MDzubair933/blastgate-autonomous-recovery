"""
BlastGate Telemetry Freshness Engine Tests (T4-005, T4-006)
Tests 120-second threshold, stale heartbeat rejection, and future timestamp clock skew rejection.
"""

import time
import pytest
from telemetry.models import WorkerHeartbeat
from telemetry.freshness import FreshnessEvaluator


@pytest.fixture
def make_heartbeat():
    def _make(timestamp: float, state: str = "HEALTHY"):
        return WorkerHeartbeat(
            task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/11820b5c8c71152eb9613525778941e6",
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state=state,
            is_unhealthy=(state != "HEALTHY"),
            timestamp=timestamp,
            processing_age=2.0,
            processed_count=50,
            schema_version="1.0.0",
            details={}
        )
    return _make


def test_freshness_nominal(make_heartbeat):
    """T4-005: Heartbeat within 120s limit evaluates as FRESH."""
    now = 1000.0
    evaluator = FreshnessEvaluator(freshness_threshold_seconds=120.0, current_time_fn=lambda: now)

    hb = make_heartbeat(timestamp=950.0)  # 50s old
    result = evaluator.evaluate(hb)

    assert result["is_fresh"] is True
    assert result["status"] == "FRESH"
    assert result["age_seconds"] == 50.0


def test_freshness_stale_rejection(make_heartbeat):
    """T4-005: Heartbeat older than 120s evaluates as STALE."""
    now = 1000.0
    evaluator = FreshnessEvaluator(freshness_threshold_seconds=120.0, current_time_fn=lambda: now)

    hb = make_heartbeat(timestamp=850.0)  # 150s old (> 120s)
    result = evaluator.evaluate(hb)

    assert result["is_fresh"] is False
    assert result["status"] == "STALE"
    assert result["age_seconds"] == 150.0
    assert "stale" in result["message"].lower()


def test_freshness_future_clock_skew_rejection(make_heartbeat):
    """T4-006: Heartbeat with future timestamp (skew > 5.0s) rejected as CLOCK_SKEW_FUTURE."""
    now = 1000.0
    evaluator = FreshnessEvaluator(freshness_threshold_seconds=120.0, current_time_fn=lambda: now)

    hb = make_heartbeat(timestamp=1010.0)  # 10s into future
    result = evaluator.evaluate(hb)

    assert result["is_fresh"] is False
    assert result["status"] == "CLOCK_SKEW_FUTURE"
    assert result["age_seconds"] == -10.0
    assert "future" in result["message"].lower()


def test_freshness_acceptable_slight_clock_skew(make_heartbeat):
    """Heartbeat timestamp slightly into future (< 5.0s) is accepted as tolerable skew."""
    now = 1000.0
    evaluator = FreshnessEvaluator(freshness_threshold_seconds=120.0, current_time_fn=lambda: now)

    hb = make_heartbeat(timestamp=1003.0)  # 3s into future (within 5s tolerance)
    result = evaluator.evaluate(hb)

    assert result["is_fresh"] is True
    assert result["status"] == "FRESH"
