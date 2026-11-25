"""
BlastGate Central Lambda Handler End-to-End Tests
Verifies full request-to-receipt orchestration, HTTP status mapping, and Gateway format compatibility.
"""

import json
from unittest.mock import MagicMock
import pytest

from broker.handler import lambda_handler, build_default_authorizer
from broker.inventory import (
    MockEcsInventoryProvider,
    MockHealthEvidenceProvider,
    ServiceInventoryState,
    TaskInventoryItem,
    TaskHealthEvidence,
)
from broker.budget import MockStateStoreProvider
from broker.idempotency import MockIdempotencyStore
from broker.executor import EcsMutationExecutor
from broker.audit import AuditLogger, MockAuditStore

TARGET_TASK = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8"


@pytest.fixture
def wired_handler():
    now = 1000.0
    task_item = TaskInventoryItem(
        task_arn=TARGET_TASK,
        cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
        task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
        task_family="blastgate-worker",
        last_status="RUNNING",
        desired_status="RUNNING",
    )

    tasks = {TARGET_TASK: task_item}
    health_map = {
        TARGET_TASK: TaskHealthEvidence(
            task_arn=TARGET_TASK,
            is_unhealthy=True,
            evidence_timestamp=now - 20.0,
            evidence_source="health_check",
        )
    }
    for i in range(1, 6):
        sibling_arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/sibling00000000000000000000000{i}"
        tasks[sibling_arn] = TaskInventoryItem(
            task_arn=sibling_arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        )
        health_map[sibling_arn] = TaskHealthEvidence(
            task_arn=sibling_arn,
            is_unhealthy=False,
            evidence_timestamp=now - 15.0,
            evidence_source="health_check",
        )

    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        pending_count=0,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks=tasks,
    )

    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider(health_map)
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
        "ResponseMetadata": {"RequestId": "req-aws-handler-1"},
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
        "now": now,
    }


def test_handler_end_to_end_allow(wired_handler):
    event = {
        "incident_id": "inc-4f9f10b304cfe9b2",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": TARGET_TASK,
    }
    resp = lambda_handler(
        event=event,
        authorizer=wired_handler["authorizer"],
        executor=wired_handler["executor"],
        audit_logger=wired_handler["audit_logger"],
    )

    assert resp["statusCode"] == 200
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "ALLOW"
    assert receipt["reason_code"] == "AUTH_APPROVED"
    assert receipt["execution_status"] == "SUBMITTED"
    assert receipt["aws_request_id"] == "req-aws-handler-1"
    assert receipt["rule_results"]["R1_allowlist"] is True
    assert receipt["rule_results"]["R2_capacity"] is True
    assert receipt["rule_results"]["R3_telemetry"] is True
    assert receipt["rule_results"]["R4_cooldown"] is True


def test_handler_schema_validation_failure(wired_handler):
    # Invalid request (extra field)
    event = {
        "incident_id": "inc-4f9f10b304cfe9b2",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": TARGET_TASK,
        "malicious_extra_param": "danger",
    }
    resp = lambda_handler(
        event=event,
        authorizer=wired_handler["authorizer"],
        executor=wired_handler["executor"],
        audit_logger=wired_handler["audit_logger"],
    )
    assert resp["statusCode"] == 400
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "DENY"


def test_handler_gateway_wrapper_unwrapping(wired_handler):
    event = {
        "body": json.dumps({
            "incident_id": "inc-c1799564f2eefcaf",
            "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
            "target_task_arn": TARGET_TASK,
        })
    }
    resp = lambda_handler(
        event=event,
        authorizer=wired_handler["authorizer"],
        executor=wired_handler["executor"],
        audit_logger=wired_handler["audit_logger"],
    )
    assert resp["statusCode"] == 200
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "ALLOW"
