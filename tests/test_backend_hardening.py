"""
BlastGate Backend Hardening Verification Tests
Covers Fixes 1-4:
- Fix 1: Rule R1 Exact ECS Service Membership Verification (positive & negative cases).
- Fix 2: Rule R2 Accurate Capacity Quorum & Telemetry Accounting (missing tasks, multiple unhealthy, stale sibling).
- Fix 3: Specific Replacement Verification (distinguish new replacement from existing healthy siblings).
- Fix 4: Audit Failure Transparency & Error Reporting (fail-closed pre-exec, transparent degraded post-exec).
"""

import json
import time
import pytest
from unittest.mock import MagicMock

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
    CapacityQuorumError,
    AuditWriteError,
    StaleTelemetryError,
)
from broker.capacity import CapacityEngine
from broker.recovery import RecoveryVerifier
from broker.executor import BrokerAuthorization, EcsMutationExecutor
from broker.audit import AuditLogger, MockAuditStore
from broker.budget import MockStateStoreProvider
from broker.idempotency import MockIdempotencyStore
from broker.handler import lambda_handler, build_default_authorizer
from broker.models import RemediationRequest, DecisionReceipt


# =====================================================================
# FIX 1: Exact ECS Service Membership Tests (Rule R1)
# =====================================================================

def test_r1_target_in_authorized_service_succeeds():
    """Positive: Target task belonging to authorized service passes R1."""
    now = 1000.0
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    task = TaskInventoryItem(
        task_arn=target_arn,
        cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
        task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
        task_family="blastgate-worker",
        last_status="RUNNING",
        desired_status="RUNNING",
        group="service:blastgate-workers",
    )
    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks={target_arn: task},
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        target_arn: TaskHealthEvidence(task_arn=target_arn, is_unhealthy=True, evidence_timestamp=now - 10.0, evidence_source="telemetry")
    })
    validator = InventoryValidator(inventory_provider=inv_provider, health_provider=health_provider)

    validated = validator.validate_target(target_arn)
    assert validated.task_arn == target_arn
    assert validated.group == "service:blastgate-workers"


def test_r1_target_from_different_service_fails_closed():
    """Negative: Target task belonging to a different service in the same cluster is rejected."""
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002"
    # Service inventory for authorized service blastgate-workers does NOT contain this task
    authorized_task = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    task_auth = TaskInventoryItem(
        task_arn=authorized_task,
        cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
        task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
        task_family="blastgate-worker",
        last_status="RUNNING",
        desired_status="RUNNING",
        group="service:blastgate-workers",
    )
    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks={authorized_task: task_auth},
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    validator = InventoryValidator(inventory_provider=inv_provider, health_provider=MockHealthEvidenceProvider())

    with pytest.raises(TargetNotAllowlistedError) as exc_info:
        validator.validate_target(target_arn)

    assert "does not belong to authorized service" in str(exc_info.value)


def test_r1_target_with_standalone_or_wrong_group_fails_closed():
    """Negative: Task with group='family:blastgate-worker' (standalone task) fails closed."""
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000003"
    standalone_task = TaskInventoryItem(
        task_arn=target_arn,
        cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
        task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
        task_family="blastgate-worker",
        last_status="RUNNING",
        desired_status="RUNNING",
        group="family:blastgate-worker",  # Standalone task, NOT service:blastgate-workers
    )
    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks={target_arn: standalone_task},
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    validator = InventoryValidator(inventory_provider=inv_provider, health_provider=MockHealthEvidenceProvider())

    with pytest.raises(TargetNotAllowlistedError) as exc_info:
        validator.validate_target(target_arn)

    assert "does not match authorized service group" in str(exc_info.value)


# =====================================================================
# FIX 2: Accurate Healthy Capacity & Telemetry Accounting (Rule R2)
# =====================================================================

def test_r2_missing_desired_capacity_fails_closed():
    """R2: If desired_count=6 but only 4 tasks exist in total, missing=2 tasks causes quorum failure."""
    engine = CapacityEngine(min_healthy_tasks=4, max_unavailable_percent=20.0)
    target = "task-target"
    unavailable = {target}

    # Desired = 6, but missing_tasks_count = 2 (only 4 tasks tracked)
    # Total unavailable = |{target}| + 2 = 3. Projected healthy = 6 - 3 = 3 (< 4 threshold).
    with pytest.raises(CapacityQuorumError) as exc_info:
        engine.evaluate_quorum(
            desired_capacity=6,
            currently_unavailable_tasks=unavailable,
            target_task_arn=target,
            missing_tasks_count=2,
        )

    assert "falls below minimum threshold (4)" in str(exc_info.value)


def test_r2_simultaneous_unhealthy_sibling_exceeds_unavailability_limit():
    """R2: If 1 sibling worker is also unhealthy, projected unavailable=2/6 (33.3% > 20%), rejecting proposal."""
    engine = CapacityEngine(min_healthy_tasks=4, max_unavailable_percent=20.0)
    target = "task-target"
    sibling_unhealthy = "task-sibling-broken"
    unavailable = {target, sibling_unhealthy}

    with pytest.raises(CapacityQuorumError) as exc_info:
        engine.evaluate_quorum(
            desired_capacity=6,
            currently_unavailable_tasks=unavailable,
            target_task_arn=target,
            missing_tasks_count=0,
        )

    assert "exceeds maximum limit (20.0%)" in str(exc_info.value)


def test_r2_stale_or_missing_sibling_telemetry_fails_closed_in_authorizer():
    """R2: Authorizer treats running siblings with stale or missing telemetry as unavailable, blocking remediation."""
    now = 1000.0
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    sibling_stale_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002"

    tasks = {
        target_arn: TaskInventoryItem(
            task_arn=target_arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        ),
        sibling_stale_arn: TaskInventoryItem(
            task_arn=sibling_stale_arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        ),
    }
    for i in range(3, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        tasks[arn] = TaskInventoryItem(
            task_arn=arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        )

    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)

    # Health map: target is confirmed unhealthy, sibling_stale raises StaleTelemetryError
    health_provider = MockHealthEvidenceProvider({
        target_arn: TaskHealthEvidence(task_arn=target_arn, is_unhealthy=True, evidence_timestamp=now - 10.0, evidence_source="telemetry"),
    })
    # tasks 3..6 are healthy, but sibling_stale has no health entry -> raises StaleTelemetryError
    for i in range(3, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        health_provider.set_health(arn, TaskHealthEvidence(task_arn=arn, is_unhealthy=False, evidence_timestamp=now - 5.0, evidence_source="telemetry"))

    authorizer = build_default_authorizer(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        state_store=MockStateStoreProvider(),
        idempotency_store=MockIdempotencyStore(),
    )
    authorizer.inventory_validator.current_time_fn = lambda: now

    req = RemediationRequest(
        incident_id="inc-8957da96bae07cee",
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        target_task_arn=target_arn,
    )

    with pytest.raises(CapacityQuorumError) as exc_info:
        authorizer.evaluate_proposal(req)

    # Because sibling_stale failed health lookup, unavailable=2 -> 33.3% > 20%
    assert "exceeds maximum limit" in str(exc_info.value)


# =====================================================================
# FIX 3: Specific Replacement Verification Tests
# =====================================================================

def test_recovery_verifier_requires_genuinely_new_task():
    """Fix 3: Verifier returns is_fully_verified=False when only pre-existing sibling tasks exist."""
    cluster = "blastgate-sandbox"
    service = "blastgate-workers"
    stopped_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    sibling_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002"

    pre_mutation_tasks = {stopped_arn, sibling_arn}

    # Post-mutation state: stopped task is STOPPED, but NO new replacement task has appeared
    tasks = {
        stopped_arn: TaskInventoryItem(
            task_arn=stopped_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="STOPPED",
            desired_status="STOPPED",
        ),
        sibling_arn: TaskInventoryItem(
            task_arn=sibling_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
    }
    service_state = ServiceInventoryState(
        cluster_name=cluster,
        service_name=service,
        status="ACTIVE",
        desired_count=1,
        running_count=1,
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        sibling_arn: TaskHealthEvidence(task_arn=sibling_arn, is_unhealthy=False, evidence_timestamp=1000.0, evidence_source="telemetry")
    })

    verifier = RecoveryVerifier(inventory_provider=inv_provider, health_provider=health_provider)

    result = verifier.verify_recovery(
        cluster=cluster,
        service=service,
        stopped_task_arn=stopped_arn,
        pre_mutation_task_arns=pre_mutation_tasks,
    )

    # Pre-existing sibling task MUST NOT count as replacement
    assert result.target_stopped is True
    assert result.replacement_launched is False
    assert result.replacement_healthy is False
    assert result.is_fully_verified is False


def test_recovery_verifier_verifies_genuine_new_healthy_replacement():
    """Fix 3: Verifier returns is_fully_verified=True when a genuine new task appears and is healthy."""
    cluster = "blastgate-sandbox"
    service = "blastgate-workers"
    stopped_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    sibling_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002"
    new_task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000099"

    pre_mutation_tasks = {stopped_arn, sibling_arn}

    tasks = {
        stopped_arn: TaskInventoryItem(
            task_arn=stopped_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="STOPPED",
            desired_status="STOPPED",
        ),
        sibling_arn: TaskInventoryItem(
            task_arn=sibling_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
        new_task_arn: TaskInventoryItem(
            task_arn=new_task_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            started_at=1010.0,
        ),
    }
    service_state = ServiceInventoryState(
        cluster_name=cluster,
        service_name=service,
        status="ACTIVE",
        desired_count=2,
        running_count=2,
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        sibling_arn: TaskHealthEvidence(task_arn=sibling_arn, is_unhealthy=False, evidence_timestamp=1000.0, evidence_source="telemetry"),
        new_task_arn: TaskHealthEvidence(task_arn=new_task_arn, is_unhealthy=False, evidence_timestamp=1015.0, evidence_source="telemetry"),
    })

    verifier = RecoveryVerifier(inventory_provider=inv_provider, health_provider=health_provider)

    result = verifier.verify_recovery(
        cluster=cluster,
        service=service,
        stopped_task_arn=stopped_arn,
        pre_mutation_task_arns=pre_mutation_tasks,
    )

    assert result.target_stopped is True
    assert result.replacement_launched is True
    assert result.replacement_running is True
    assert result.replacement_healthy is True
    assert result.is_fully_verified is True
    assert result.details["replacementTaskArn"] == new_task_arn


def test_recovery_verifier_fails_when_replacement_is_unhealthy():
    """Fix 3: When a new replacement task appears but fails application health, is_fully_verified=False."""
    cluster = "blastgate-sandbox"
    service = "blastgate-workers"
    stopped_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    new_task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000099"

    pre_mutation_tasks = {stopped_arn}

    tasks = {
        stopped_arn: TaskInventoryItem(
            task_arn=stopped_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="STOPPED",
            desired_status="STOPPED",
        ),
        new_task_arn: TaskInventoryItem(
            task_arn=new_task_arn,
            cluster_arn=f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster}",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
        ),
    }
    service_state = ServiceInventoryState(
        cluster_name=cluster,
        service_name=service,
        status="ACTIVE",
        desired_count=1,
        running_count=1,
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        new_task_arn: TaskHealthEvidence(task_arn=new_task_arn, is_unhealthy=True, evidence_timestamp=1000.0, evidence_source="telemetry"),
    })

    verifier = RecoveryVerifier(inventory_provider=inv_provider, health_provider=health_provider)

    result = verifier.verify_recovery(
        cluster=cluster,
        service=service,
        stopped_task_arn=stopped_arn,
        pre_mutation_task_arns=pre_mutation_tasks,
    )

    assert result.replacement_launched is True
    assert result.replacement_running is True
    assert result.replacement_healthy is False
    assert result.is_fully_verified is False


# =====================================================================
# FIX 4: Audit Failure Transparency & Error Handling Tests
# =====================================================================

def test_pre_execution_audit_failure_fails_closed_blocks_mutation():
    """Fix 4: Pre-mutation audit write failure fails closed with 500 ERR_AUDIT_WRITE_FAILED and stops execution."""
    now = 1000.0
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"

    tasks = {
        target_arn: TaskInventoryItem(
            task_arn=target_arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        )
    }
    for i in range(2, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        tasks[arn] = TaskInventoryItem(
            task_arn=arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        )

    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        target_arn: TaskHealthEvidence(task_arn=target_arn, is_unhealthy=True, evidence_timestamp=now - 10.0, evidence_source="telemetry")
    })
    for i in range(2, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        health_provider.set_health(arn, TaskHealthEvidence(task_arn=arn, is_unhealthy=False, evidence_timestamp=now - 5.0, evidence_source="telemetry"))

    authorizer = build_default_authorizer(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        state_store=MockStateStoreProvider(),
        idempotency_store=MockIdempotencyStore(),
    )
    authorizer.inventory_validator.current_time_fn = lambda: now

    # Mock ECS client - should NEVER be called
    mock_ecs = MagicMock()
    executor = EcsMutationExecutor(ecs_client=mock_ecs)

    # Audit store that FAILS on write
    failing_audit_store = MockAuditStore(fail_writes=True)
    audit_logger = AuditLogger(store=failing_audit_store)

    event = {
        "incident_id": "inc-283d5944027c32b9",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": target_arn,
    }
    resp = lambda_handler(
        event=event,
        authorizer=authorizer,
        executor=executor,
        audit_logger=audit_logger,
    )

    assert resp["statusCode"] == 500
    receipt = json.loads(resp["body"])
    assert receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "ERR_AUDIT_WRITE_FAILED"
    assert receipt["execution_status"] == "NOT_STARTED"
    mock_ecs.stop_task.assert_not_called()


def test_post_execution_audit_failure_is_transparent_and_does_not_misreport_mutation(capsys):
    """Fix 4: Post-execution audit failure emits structured warning, flags audit_persisted=False, and preserves mutation status."""
    now = 1000.0
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"

    tasks = {
        target_arn: TaskInventoryItem(
            task_arn=target_arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        )
    }
    for i in range(2, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        tasks[arn] = TaskInventoryItem(
            task_arn=arn,
            cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            task_family="blastgate-worker",
            last_status="RUNNING",
            desired_status="RUNNING",
            group="service:blastgate-workers",
        )

    service_state = ServiceInventoryState(
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        status="ACTIVE",
        desired_count=6,
        running_count=6,
        deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        tasks=tasks,
    )
    inv_provider = MockEcsInventoryProvider(service_state)
    health_provider = MockHealthEvidenceProvider({
        target_arn: TaskHealthEvidence(task_arn=target_arn, is_unhealthy=True, evidence_timestamp=now - 10.0, evidence_source="telemetry")
    })
    for i in range(2, 7):
        arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
        health_provider.set_health(arn, TaskHealthEvidence(task_arn=arn, is_unhealthy=False, evidence_timestamp=now - 5.0, evidence_source="telemetry"))

    authorizer = build_default_authorizer(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        state_store=MockStateStoreProvider(),
        idempotency_store=MockIdempotencyStore(),
    )
    authorizer.inventory_validator.current_time_fn = lambda: now

    # Mock ECS client that SUCCEEDS
    mock_ecs = MagicMock()
    mock_ecs.stop_task.return_value = {
        "ResponseMetadata": {"RequestId": "req-aws-post-audit-test"},
        "task": {"desiredStatus": "STOPPED"}
    }
    executor = EcsMutationExecutor(ecs_client=mock_ecs)

    # Flaky audit store: succeeds on first call (COOLDOWN_RESERVATION), fails on second (MUTATION_EXECUTION)
    call_count = [0]
    real_store = MockAuditStore()

    class FlakyAuditStore:
        def append_event(self, record):
            if record.event_type == "MUTATION_EXECUTION":
                raise AuditWriteError("DynamoDB simulated network disconnect during post-mutation audit write")
            return real_store.append_event(record)

    audit_logger = AuditLogger(store=FlakyAuditStore())

    event = {
        "incident_id": "inc-c1be31f2d0b1308d",
        "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
        "target_task_arn": target_arn,
    }
    resp = lambda_handler(
        event=event,
        authorizer=authorizer,
        executor=executor,
        audit_logger=audit_logger,
    )

    # 1. HTTP 200 returned because mutation DID happen
    assert resp["statusCode"] == 200
    receipt = json.loads(resp["body"])

    # 2. Mutation is NOT misreported
    assert receipt["decision"] == "ALLOW"
    assert receipt["execution_status"] == "SUBMITTED"
    assert receipt["aws_request_id"] == "req-aws-post-audit-test"

    # 3. Incomplete audit state is explicitly flagged
    assert receipt["audit_persisted"] is False
    assert receipt["audit_warning"] == "POST_EXECUTION_AUDIT_WRITE_FAILED"

    # 4. Structured error emitted to stderr
    captured = capsys.readouterr()
    assert "POST_EXECUTION_AUDIT_FAILURE" in captured.err
    assert "POST_EXECUTION_AUDIT_WRITE_FAILED" in captured.err
    assert "MUTATION_SUCCEEDED_AUDIT_DEGRADED" in captured.err
