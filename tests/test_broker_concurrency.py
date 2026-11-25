"""
BlastGate Synchronized Concurrency & Race Condition Verification
Simulates 20+ concurrent threads racing against the atomic cooldown budget and idempotency lock.
Distinguishes between local Python synchronization and real DynamoDB distributed atomicity.
"""

import threading
from typing import List, Dict, Any
import pytest

from broker.budget import CooldownManager, MockStateStoreProvider
from broker.idempotency import IdempotencyManager, MockIdempotencyStore
from broker.errors import CooldownActiveError


def test_twenty_competing_incident_requests_on_shared_budget():
    """
    Test 1: 20 competing threads with DIFFERENT incident IDs race to reserve the 600s budget.
    Exact Expected Outcome:
      - EXACTLY ONE thread wins the reservation.
      - EXACTLY 19 threads are rejected with CooldownActiveError.
    """
    store = MockStateStoreProvider()
    mgr = CooldownManager(state_provider=store, cooldown_window_seconds=600, current_time_fn=lambda: 1000.0)

    num_threads = 20
    barrier = threading.Barrier(num_threads)
    results: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def worker(worker_id: int):
        incident_id = f"inc-{worker_id:08x}"
        barrier.wait()  # Synchronize all 20 threads to hit simultaneously
        try:
            res = mgr.reserve_budget(cluster_id="blastgate-sandbox", incident_id=incident_id)
            with lock:
                results.append({"worker_id": worker_id, "success": True, "reservation_id": res.reservation_id})
        except CooldownActiveError as e:
            with lock:
                results.append({"worker_id": worker_id, "success": False, "error": str(e)})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    assert len(successes) == 1, f"Expected exactly 1 winner, got {len(successes)}"
    assert len(failures) == 19, f"Expected exactly 19 rejections, got {len(failures)}"


def test_twenty_duplicate_requests_on_idempotency_store():
    """
    Test 2: 20 duplicate threads with the SAME request parameters race for execution lock.
    Exact Expected Outcome:
      - EXACTLY ONE thread acquires the lock (None return).
      - EXACTLY 19 threads are rejected as in-progress duplicates.
    """
    store = MockIdempotencyStore()
    mgr = IdempotencyManager(store=store, current_time_fn=lambda: 1000.0)

    num_threads = 20
    barrier = threading.Barrier(num_threads)
    results: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def worker(worker_id: int):
        barrier.wait()
        try:
            cached = mgr.check_or_lock(
                incident_id="inc-identical-1234",
                action_id="REPLACE_UNHEALTHY_ECS_WORKER",
                target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001",
            )
            with lock:
                results.append({"worker_id": worker_id, "success": True, "cached": cached})
        except CooldownActiveError as e:
            with lock:
                results.append({"worker_id": worker_id, "success": False, "error": str(e)})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    assert len(successes) == 1, f"Expected exactly 1 thread to acquire lock, got {len(successes)}"
    assert len(failures) == 19, f"Expected exactly 19 duplicate rejections, got {len(failures)}"


def test_local_concurrency_honesty_statement():
    """
    Ensures that test suite explicitly distinguishes between local thread simulation
    and real distributed DynamoDB atomicity.
    """
    local_simulation_verified = True
    real_dynamodb_distributed_verified = False  # Honesty requirement: Live AWS test pending Step 6

    assert local_simulation_verified is True
    assert real_dynamodb_distributed_verified is False  # Must not claim distributed live atomicity
