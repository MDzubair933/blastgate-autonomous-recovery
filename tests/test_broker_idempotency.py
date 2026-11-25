"""
BlastGate Broker Idempotency Tests (Rule R8)
Verifies request deduplication, replay handling, and concurrent rejection.
"""

import pytest
from broker.idempotency import IdempotencyManager, MockIdempotencyStore
from broker.errors import CooldownActiveError


def test_fresh_request_acquires_lock():
    store = MockIdempotencyStore()
    mgr = IdempotencyManager(store=store)

    cached = mgr.check_or_lock(
        incident_id="inc-ef797c8118f02dfb",
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        target_task_arn="task-arn-1",
    )
    assert cached is None  # Fresh lock acquired


def test_in_progress_duplicate_rejected():
    store = MockIdempotencyStore()
    mgr = IdempotencyManager(store=store)

    mgr.check_or_lock("inc-ef797c8118f02dfb", "REPLACE_UNHEALTHY_ECS_WORKER", "task-arn-1")

    # Second concurrent call with same key
    with pytest.raises(CooldownActiveError) as exc:
        mgr.check_or_lock("inc-ef797c8118f02dfb", "REPLACE_UNHEALTHY_ECS_WORKER", "task-arn-1")
    assert "already in progress" in str(exc.value)


def test_completed_duplicate_returns_cached_receipt():
    store = MockIdempotencyStore()
    mgr = IdempotencyManager(store=store)

    mgr.check_or_lock("inc-ef797c8118f02dfb", "REPLACE_UNHEALTHY_ECS_WORKER", "task-arn-1")

    mock_receipt = {
        "decision_id": "dec-original",
        "decision": "ALLOW",
        "execution_status": "SUBMITTED",
        "aws_request_id": "req-aws-123",
    }
    mgr.finalize("inc-ef797c8118f02dfb", "REPLACE_UNHEALTHY_ECS_WORKER", "task-arn-1", mock_receipt)

    # Replay request
    cached = mgr.check_or_lock("inc-ef797c8118f02dfb", "REPLACE_UNHEALTHY_ECS_WORKER", "task-arn-1")
    assert cached is not None
    assert cached["decision_id"] == "dec-original"
    assert cached["aws_request_id"] == "req-aws-123"
