"""
BlastGate Trusted Inventory & Health Telemetry Tests (Rules R1 & R3)
Verifies ECS membership, active deployment check, and telemetry freshness.
"""

import time
import pytest
from broker.inventory import (
    InventoryValidator,
    MockEcsInventoryProvider,
    MockHealthEvidenceProvider,
    ServiceInventoryState,
    TaskInventoryItem,
    TaskHealthEvidence,
)
from broker.errors import (
    TargetNotAllowlistedError,
    TargetNotUnhealthyError,
    StaleTelemetryError,
)

TARGET_TASK = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8"


@pytest.fixture
def test_setup():
    now = 1700000000.0

    task_item = TaskInventoryItem(
        task_arn=TARGET_TASK,
        cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
        task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
        task_family="blastgate-worker",
        last_status="RUNNING",
        desired_status="RUNNING",
    )

    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        pending_count=0,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks={TARGET_TASK: task_item},
    )

    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider()

    # Configure target as confirmed unhealthy with fresh telemetry (30s old)
    health_provider.set_health(
        TARGET_TASK,
        TaskHealthEvidence(
            task_arn=TARGET_TASK,
            is_unhealthy=True,
            evidence_timestamp=now - 30.0,
            evidence_source="container_health_check",
        )
    )

    validator = InventoryValidator(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        telemetry_freshness_seconds=120,
        current_time_fn=lambda: now,
    )

    return validator, inv_provider, health_provider, now


def test_target_validation_success(test_setup):
    validator, _, _, _ = test_setup
    task = validator.validate_target(TARGET_TASK)
    assert task.task_arn == TARGET_TASK
    assert task.last_status == "RUNNING"

    health = validator.verify_application_health(TARGET_TASK)
    assert health.is_unhealthy is True


def test_target_not_in_inventory_rejected(test_setup):
    validator, _, _, _ = test_setup
    missing_task = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/ff312f8e5727b446f64f30d17061f613"
    with pytest.raises(TargetNotAllowlistedError) as exc:
        validator.validate_target(missing_task)
    assert "does not exist in cluster" in str(exc.value)


def test_target_status_not_running_rejected(test_setup):
    validator, inv_provider, _, _ = test_setup
    inv_provider.service_state.tasks[TARGET_TASK].last_status = "STOPPED"
    with pytest.raises(TargetNotAllowlistedError) as exc:
        validator.validate_target(TARGET_TASK)
    assert "expected 'RUNNING'" in str(exc.value)


def test_active_deployment_in_progress_pauses_remediation(test_setup):
    validator, inv_provider, _, _ = test_setup
    # Add second deployment in progress
    inv_provider.service_state.deployments.append({
        "rolloutState": "IN_PROGRESS",
        "status": "ACTIVE",
    })
    with pytest.raises(TargetNotAllowlistedError) as exc:
        validator.validate_target(TARGET_TASK)
    assert "active rolling deployment in progress" in str(exc.value)


def test_target_healthy_rejected(test_setup):
    validator, _, health_provider, now = test_setup
    # Set task to healthy
    health_provider.set_health(
        TARGET_TASK,
        TaskHealthEvidence(
            task_arn=TARGET_TASK,
            is_unhealthy=False,  # Application is healthy!
            evidence_timestamp=now - 10.0,
            evidence_source="heartbeat",
        )
    )
    with pytest.raises(TargetNotUnhealthyError) as exc:
        validator.verify_application_health(TARGET_TASK)
    assert "reports HEALTHY application state" in str(exc.value)


def test_stale_telemetry_rejected(test_setup):
    validator, _, health_provider, now = test_setup
    # Telemetry is 130s old (> 120s threshold)
    health_provider.set_health(
        TARGET_TASK,
        TaskHealthEvidence(
            task_arn=TARGET_TASK,
            is_unhealthy=True,
            evidence_timestamp=now - 130.0,
            evidence_source="heartbeat",
        )
    )
    with pytest.raises(StaleTelemetryError) as exc:
        validator.verify_application_health(TARGET_TASK)
    assert "is stale" in str(exc.value)


def test_missing_telemetry_fails_closed(test_setup):
    validator, _, health_provider, _ = test_setup
    del health_provider.health_map[TARGET_TASK]
    with pytest.raises(StaleTelemetryError) as exc:
        validator.verify_application_health(TARGET_TASK)
    assert "No health telemetry recorded" in str(exc.value)
