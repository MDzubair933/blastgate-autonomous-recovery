"""
BlastGate Capacity Quorum Engine (Rule R2 & Invariant 3)
Calculates projected healthy capacity and enforces the minimum quorum invariant:
N - |U union T| >= 4 and 100 * |U union T| / N <= 20%
"""

from dataclasses import dataclass
from typing import Set

from config import MIN_HEALTHY_TASKS, MAX_UNAVAILABLE_PERCENT
from errors import CapacityQuorumError


@dataclass(frozen=True)
class CapacityEvaluation:
    desired_capacity: int
    unavailable_count: int
    projected_unavailable_count: int
    projected_healthy_capacity: int
    projected_unavailable_percent: float
    is_authorized: bool


class CapacityEngine:
    """Enforces mathematical capacity invariants over trusted live service state."""

    def __init__(
        self,
        min_healthy_tasks: int = MIN_HEALTHY_TASKS,
        max_unavailable_percent: float = MAX_UNAVAILABLE_PERCENT,
    ):
        self.min_healthy_tasks = min_healthy_tasks
        self.max_unavailable_percent = max_unavailable_percent

    def evaluate_quorum(
        self,
        desired_capacity: int,
        currently_unavailable_tasks: Set[str],
        target_task_arn: str,
        missing_tasks_count: int = 0,
    ) -> CapacityEvaluation:
        """
        Evaluates projected service quorum after stopping target_task_arn.
        Definitions:
          N = desired_capacity
          U = currently_unavailable_tasks (stopped, pending, or failing health)
          M = missing_tasks_count (unprovisioned tasks missing from desired capacity)
          T = {target_task_arn}
          Projected Unavailable = |U union T| + M
          Projected Healthy Capacity = max(0, N - Projected Unavailable)
          Projected Unavailable % = 100 * Projected Unavailable / N
        """
        N = desired_capacity
        if N <= 0:
            raise CapacityQuorumError(f"Desired capacity must be positive, got {N}.")

        # Union of current unavailable workers and target worker plus missing tasks
        U = set(currently_unavailable_tasks)
        T = {target_task_arn}
        projected_unavailable_set = U.union(T)
        projected_unavailable_count = len(projected_unavailable_set) + missing_tasks_count

        # Projected healthy capacity
        projected_healthy = N - projected_unavailable_count
        if projected_healthy < 0:
            projected_healthy = 0

        projected_unavailable_pct = (projected_unavailable_count * 100.0) / N

        # Check Invariant 3 Condition 1: Projected Healthy >= Min Healthy Tasks (e.g. 4)
        if projected_healthy < self.min_healthy_tasks:
            raise CapacityQuorumError(
                f"Quorum violation: Projected healthy workers ({projected_healthy}) "
                f"falls below minimum threshold ({self.min_healthy_tasks}). "
                f"Total desired={N}, projected unavailable={projected_unavailable_count}."
            )

        # Check Invariant 3 Condition 2: Projected Unavailable % <= Max Unavailable % (e.g. 20.0%)
        if projected_unavailable_pct > self.max_unavailable_percent:
            raise CapacityQuorumError(
                f"Unavailability threshold exceeded: Projected unavailable percentage "
                f"({projected_unavailable_pct:.1f}%) exceeds maximum limit ({self.max_unavailable_percent:.1f}%)."
            )

        return CapacityEvaluation(
            desired_capacity=N,
            unavailable_count=len(U) + missing_tasks_count,
            projected_unavailable_count=projected_unavailable_count,
            projected_healthy_capacity=projected_healthy,
            projected_unavailable_percent=projected_unavailable_pct,
            is_authorized=True,
        )
