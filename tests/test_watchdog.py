"""
BlastGate Watchdog Tests (T4-009, T4-010, T4-011)
Tests service inventory evaluation, 0-desired count safety, stalled worker detection, and custom metric emission.
"""

import time
import pytest
from telemetry.models import WorkerHeartbeat
from telemetry.heartbeat_repository import MockHeartbeatRepository
from telemetry.validator import TelemetryValidator
from watchdog.evaluator import WatchdogEvaluator
from watchdog.metrics import WatchdogMetricsEmitter
from watchdog.incidents import WatchdogIncidentDetector
from watchdog.handler import lambda_handler


@pytest.fixture
def repo_with_tasks():
    repo = MockHeartbeatRepository()
    now = time.time()
    # 5 healthy tasks
    for i in range(1, 6):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        repo.save_heartbeat(WorkerHeartbeat(
            task_arn=arn,
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state="HEALTHY",
            is_unhealthy=False,
            timestamp=now,
            processing_age=1.0,
            processed_count=100,
            schema_version="1.0.0",
            details={}
        ))
    # 1 stalled task
    stalled_arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{6:032x}"
    repo.save_heartbeat(WorkerHeartbeat(
        task_arn=stalled_arn,
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        task_family="blastgate-worker",
        processing_state="STALLED",
        is_unhealthy=True,
        timestamp=now,
        processing_age=30.0,
        processed_count=50,
        schema_version="1.0.0",
        details={"reason": "Simulated memory leak"}
    ))
    return repo


def test_watchdog_desired_zero_produces_zero_alarms():
    """T4-010: Desired count == 0 produces 0 confirmed stalls (prevents false positive alarms)."""
    repo = MockHeartbeatRepository()
    validator = TelemetryValidator(repository=repo)
    evaluator = WatchdogEvaluator(telemetry_validator=validator)

    inventory = {
        "desired_count": 0,
        "running_count": 0,
        "task_arns": [],
    }
    result = evaluator.evaluate_service_health(inventory)

    assert result["desired_count"] == 0
    assert result["confirmed_stalled_count"] == 0
    assert result["healthy_count"] == 0
    assert result["unknown_count"] == 0
    assert len(result["stalled_task_arns"]) == 0


def test_watchdog_all_workers_healthy():
    """T4-009: 6 running healthy tasks results in healthy_count == 6 and stalled == 0."""
    repo = MockHeartbeatRepository()
    now = time.time()
    task_arns = []
    for i in range(1, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        task_arns.append(arn)
        repo.save_heartbeat(WorkerHeartbeat(
            task_arn=arn,
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state="HEALTHY",
            is_unhealthy=False,
            timestamp=now,
            processing_age=1.0,
            processed_count=100,
            schema_version="1.0.0",
            details={}
        ))

    validator = TelemetryValidator(repository=repo)
    evaluator = WatchdogEvaluator(telemetry_validator=validator)

    inventory = {
        "desired_count": 6,
        "running_count": 6,
        "task_arns": task_arns,
    }
    result = evaluator.evaluate_service_health(inventory)

    assert result["healthy_count"] == 6
    assert result["confirmed_stalled_count"] == 0
    assert result["unknown_count"] == 0


def test_watchdog_confirmed_stalled_detection(repo_with_tasks):
    """T4-011: Evaluator correctly identifies 1 confirmed stalled task among 6 running tasks."""
    validator = TelemetryValidator(repository=repo_with_tasks)
    evaluator = WatchdogEvaluator(telemetry_validator=validator)

    task_arns = [f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}" for i in range(1, 7)]
    inventory = {
        "desired_count": 6,
        "running_count": 6,
        "task_arns": task_arns,
    }
    result = evaluator.evaluate_service_health(inventory)

    assert result["healthy_count"] == 5
    assert result["confirmed_stalled_count"] == 1
    assert result["unknown_count"] == 0
    assert len(result["stalled_task_arns"]) == 1
    assert result["stalled_task_arns"][0] == f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{6:032x}"


def test_watchdog_unknown_missing_heartbeat():
    """Task in ECS inventory without heartbeat is categorized as unknown, not assumed healthy."""
    repo = MockHeartbeatRepository()
    validator = TelemetryValidator(repository=repo)
    evaluator = WatchdogEvaluator(telemetry_validator=validator)

    inventory = {
        "desired_count": 2,
        "running_count": 2,
        "task_arns": [
            "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/a18d4a943def419acad40567c6c37d0a",
            "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/61ae2fe7a7a3e0108634238d42f34449",
        ],
    }
    result = evaluator.evaluate_service_health(inventory)

    assert result["unknown_count"] == 2
    assert result["healthy_count"] == 0
    assert result["confirmed_stalled_count"] == 0


def test_watchdog_metrics_emission():
    """WatchdogMetricsEmitter records low-cardinality metrics to BlastGate/Workers namespace."""
    emitter = WatchdogMetricsEmitter(cloudwatch_client=None)

    evaluation = {
        "desired_count": 6,
        "healthy_count": 5,
        "confirmed_stalled_count": 1,
        "unknown_count": 0,
    }
    emitter.emit_metrics(evaluation)

    assert len(emitter.emitted_metrics) == 4
    metric_names = {m["MetricName"] for m in emitter.emitted_metrics}
    assert metric_names == {
        "DesiredWorkerCount",
        "HealthyWorkerCount",
        "ConfirmedStalledWorkerCount",
        "UnknownWorkerCount",
    }
    for m in emitter.emitted_metrics:
        assert m["Namespace"] == "BlastGate/Workers"
