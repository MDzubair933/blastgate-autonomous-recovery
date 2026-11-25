"""
BlastGate Broker Health Integration Tests (T4-022, T4-023, T4-024)
Tests TelemetryHealthEvidenceAdapter integration with the sovereign Remediation Broker.
Verifies R5 (Target Unhealthy) passes for confirmed stalled workers,
fails for healthy workers, and fails closed on stale telemetry.
"""

import json
import time
from unittest.mock import MagicMock
import pytest
from telemetry.models import WorkerHeartbeat
from telemetry.heartbeat_repository import MockHeartbeatRepository
from telemetry.validator import TelemetryValidator
from broker.inventory import (
    TelemetryHealthEvidenceAdapter,
    MockEcsInventoryProvider,
    ServiceInventoryState,
    TaskInventoryItem,
)
from broker.handler import lambda_handler, build_default_authorizer
from broker.budget import MockStateStoreProvider
from broker.idempotency import MockIdempotencyStore
from broker.executor import EcsMutationExecutor
from broker.audit import AuditLogger, MockAuditStore


@pytest.fixture
def broker_environment():
    cluster = "blastgate-sandbox"
    service = "blastgate-workers"
    task_stalled = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/8a83665f3798727f14f92ad0e6c99fda"
    task_healthy = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/0d6ba19b62531ccb0deb8804313eca28"
    task_stale = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/deb0e38ced1e41de6f92e70e80c418d2"

    now = 1000.0
    repo = MockHeartbeatRepository()

    # 1. Stalled worker with fresh telemetry (30s old)
    repo.save_heartbeat(WorkerHeartbeat(
        task_arn=task_stalled,
        cluster_name=cluster,
        service_name=service,
        task_family="blastgate-worker",
        processing_state="STALLED",
        is_unhealthy=True,
        timestamp=now - 30.0,
        processing_age=45.0,
        processed_count=100,
        schema_version="1.0.0",
        details={"reason": "Simulated thread hang"}
    ))

    # 2. Healthy worker with fresh telemetry (5s old)
    repo.save_heartbeat(WorkerHeartbeat(
        task_arn=task_healthy,
        cluster_name=cluster,
        service_name=service,
        task_family="blastgate-worker",
        processing_state="HEALTHY",
        is_unhealthy=False,
        timestamp=now - 5.0,
        processing_age=1.0,
        processed_count=500,
        schema_version="1.0.0",
        details={}
    ))

    # 3. Worker task_stale: fresh by default in baseline, set stale in stale telemetry test
    repo.save_heartbeat(WorkerHeartbeat(
        task_arn=task_stale,
        cluster_name=cluster,
        service_name=service,
        task_family="blastgate-worker",
        processing_state="HEALTHY",
        is_unhealthy=False,
        timestamp=now - 10.0,
        processing_age=2.0,
        processed_count=150,
        schema_version="1.0.0",
        details={}
    ))

    # ECS Mock state: 6 running tasks
    tasks = {
        task_stalled: TaskInventoryItem(
            task_arn=task_stalled,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
        task_healthy: TaskInventoryItem(
            task_arn=task_healthy,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
        task_stale: TaskInventoryItem(
            task_arn=task_stale,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
    }
    for i in range(4, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        repo.save_heartbeat(WorkerHeartbeat(
            task_arn=arn,
            cluster_name=cluster,
            service_name=service,
            task_family="blastgate-worker",
            processing_state="HEALTHY",
            is_unhealthy=False,
            timestamp=now - 5.0,
            processing_age=1.0,
            processed_count=100,
            schema_version="1.0.0",
            details={},
        ))
        tasks[arn] = TaskInventoryItem(
            task_arn=arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        )

    service_state = ServiceInventoryState(
        cluster_name=cluster,
        service_name=service,
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        pending_count=0,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state=service_state)

    validator = TelemetryValidator(repository=repo)
    validator.freshness.current_time_fn = lambda: now
    health_provider = TelemetryHealthEvidenceAdapter(telemetry_validator=validator)

    state_store = MockStateStoreProvider()
    idemp_store = MockIdempotencyStore()

    authorizer = build_default_authorizer(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        state_store=state_store,
        idempotency_store=idemp_store,
    )
    authorizer.cooldown_manager.current_time_fn = lambda: now
    authorizer.inventory_validator.current_time_fn = lambda: now

    mock_ecs = MagicMock()
    mock_ecs.stop_task.return_value = {
        "ResponseMetadata": {"RequestId": "req-aws-test-health-1"},
        "task": {"desiredStatus": "STOPPED"}
    }
    executor = EcsMutationExecutor(ecs_client=mock_ecs)
    audit_store = MockAuditStore()
    audit_logger = AuditLogger(store=audit_store)

    return {
        "authorizer": authorizer,
        "executor": executor,
        "audit_logger": audit_logger,
        "mock_ecs": mock_ecs,
        "repo": repo,
        "now": now,
        "task_stalled": task_stalled,
        "task_healthy": task_healthy,
        "task_stale": task_stale,
    }


def test_broker_authorizes_confirmed_stalled_worker(broker_environment):
    """T4-022: Fresh confirmed STALLED telemetry authorizes task replacement."""
    event = {
        "incident_id": "inc-4f9f10b304cfe9b2",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": broker_environment["task_stalled"],
    }
    resp = lambda_handler(
        event=event,
        authorizer=broker_environment["authorizer"],
        executor=broker_environment["executor"],
        audit_logger=broker_environment["audit_logger"],
    )

    assert resp["statusCode"] == 200
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "ALLOW"
    assert receipt["reason_code"] == "AUTH_APPROVED"
    assert receipt["execution_status"] == "SUBMITTED"
    assert receipt["rule_results"]["R3_telemetry"] is True
    assert receipt["rule_results"]["R1_allowlist"] is True
    assert receipt["rule_results"]["R2_capacity"] is True
    assert receipt["rule_results"]["R4_cooldown"] is True


def test_broker_rejects_healthy_worker(broker_environment):
    """T4-023: Fresh telemetry showing HEALTHY worker fails R5/unhealthy invariant and is rejected with 403."""
    event = {
        "incident_id": "inc-7b79ce46bcd1919f",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": broker_environment["task_healthy"],
    }
    resp = lambda_handler(
        event=event,
        authorizer=broker_environment["authorizer"],
        executor=broker_environment["executor"],
        audit_logger=broker_environment["audit_logger"],
    )

    assert resp["statusCode"] == 403
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "ERR_TARGET_NOT_UNHEALTHY"


def test_broker_fails_closed_on_stale_telemetry(broker_environment):
    """T4-024: Telemetry older than 120s causes broker to fail closed (403 DENY, fails R3)."""
    # Make task_stale stale in repo (> 120s old)
    now = broker_environment["now"]
    broker_environment["repo"].save_heartbeat(WorkerHeartbeat(
        task_arn=broker_environment["task_stale"],
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        task_family="blastgate-worker",
        processing_state="STALLED",
        is_unhealthy=True,
        timestamp=now - 200.0,
        processing_age=250.0,
        processed_count=50,
        schema_version="1.0.0",
        details={"reason": "Old stall"}
    ))
    event = {
        "incident_id": "inc-068a9f5baa13da8e",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": broker_environment["task_stale"],
    }
    resp = lambda_handler(
        event=event,
        authorizer=broker_environment["authorizer"],
        executor=broker_environment["executor"],
        audit_logger=broker_environment["audit_logger"],
    )

    assert resp["statusCode"] == 403
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "DENY"
    assert receipt["rule_results"]["R3_telemetry"] is False
