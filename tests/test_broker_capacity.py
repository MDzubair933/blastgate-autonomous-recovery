"""
BlastGate Capacity Quorum Engine Tests (Rule R2 & Invariant 3)
Verifies mathematical quorum guarantees: N - |U union T| >= 4 and 100 * |U union T| / N <= 20%
"""

import pytest
from broker.capacity import CapacityEngine
from broker.errors import CapacityQuorumError


@pytest.fixture
def engine():
    return CapacityEngine(min_healthy_tasks=4, max_unavailable_percent=20.0)


def test_baseline_capacity_success(engine):
    # Desired: 6, currently unavailable: 0, target: task-1
    # Projected unavailable: 1 (16.7%), projected healthy: 5 (>= 4)
    target = "task-1"
    eval_result = engine.evaluate_quorum(
        desired_capacity=6,
        currently_unavailable_tasks=set(),
        target_task_arn=target,
    )
    assert eval_result.is_authorized is True
    assert eval_result.projected_healthy_capacity == 5
    assert abs(eval_result.projected_unavailable_percent - 16.666) < 0.1


def test_quorum_violation_healthy_below_minimum(engine):
    # Desired: 6, currently unavailable: {task-2, task-3}, target: task-1
    # Projected unavailable: 3, projected healthy: 3 (< 4 threshold) -> REJECT
    target = "task-1"
    unavailable = {"task-2", "task-3"}
    with pytest.raises(CapacityQuorumError) as exc:
        engine.evaluate_quorum(
            desired_capacity=6,
            currently_unavailable_tasks=unavailable,
            target_task_arn=target,
        )
    assert "falls below minimum threshold (4)" in str(exc.value)


def test_unavailability_percentage_exceeded(engine):
    # Desired: 5, currently unavailable: 0, target: task-1
    # Projected unavailable: 1 (20.0%), healthy: 4 (>= 4) -> PASS
    eval_result = engine.evaluate_quorum(
        desired_capacity=5,
        currently_unavailable_tasks=set(),
        target_task_arn="task-1",
    )
    assert eval_result.is_authorized is True
    assert eval_result.projected_unavailable_percent == 20.0

    # Desired: 4, currently unavailable: 0, target: task-1
    # Projected unavailable: 1 (25.0% > 20.0%), healthy: 3 (< 4) -> REJECT
    with pytest.raises(CapacityQuorumError) as exc:
        engine.evaluate_quorum(
            desired_capacity=4,
            currently_unavailable_tasks=set(),
            target_task_arn="task-1",
        )
    assert "falls below minimum threshold" in str(exc.value) or "exceeds maximum limit" in str(exc.value)


def test_target_already_in_unavailable_set(engine):
    # If target is already counted as unavailable, |U union T| == |U|
    # Desired: 6, U = {task-1}, T = task-1 -> |U union T| = 1
    eval_result = engine.evaluate_quorum(
        desired_capacity=6,
        currently_unavailable_tasks={"task-1"},
        target_task_arn="task-1",
    )
    assert eval_result.projected_healthy_capacity == 5
    assert eval_result.projected_unavailable_count == 1


def test_zero_desired_capacity_fails_closed(engine):
    with pytest.raises(CapacityQuorumError) as exc:
        engine.evaluate_quorum(
            desired_capacity=0,
            currently_unavailable_tasks=set(),
            target_task_arn="task-1",
        )
    assert "Desired capacity must be positive" in str(exc.value)
