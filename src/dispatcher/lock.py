"""
BlastGate Dispatch Lock & Cooldown Pre-check
Enforces atomic DynamoDB deduplication, bounded retries (max 3), stale lock recovery,
and checks rolling cooldown budget.
"""

import time
from typing import Any, Optional

MAX_DISPATCH_ATTEMPTS = 3
STALE_LOCK_TIMEOUT_SECONDS = 120.0


def acquire_dispatch_lock(
    ddb_client: Any,
    table_name: str,
    incident_id: str,
    ttl_seconds: int = 86400,
    now_ts: Optional[float] = None,
) -> bool:
    """
    Atomically attempts to acquire a dispatch lock for incident_id in DynamoDB.
    Guarantees:
    1. First attempt: acquires with status 'DISPATCHING', attempts=1.
    2. Completed dispatch: status 'COMPLETED' can NEVER be re-dispatched.
    3. Failed dispatch: allows bounded retry if attempts < MAX_DISPATCH_ATTEMPTS.
    4. Stale/crashed lock: allows recovery if last_attempt_timestamp > 120s old and attempts < MAX_DISPATCH_ATTEMPTS.
    5. Exhausted retries: if attempts >= MAX_DISPATCH_ATTEMPTS, returns False.
    """
    if ddb_client is None:
        return True

    now = float(now_ts or time.time())
    now_int = int(now)
    ttl = now_int + ttl_seconds
    lock_key = f"LOCK#DISPATCH#{incident_id}"

    # 1. Try initial lock acquisition
    try:
        ddb_client.put_item(
            TableName=table_name,
            Item={
                "cluster_id": {"S": lock_key},
                "incident_id": {"S": incident_id},
                "status": {"S": "DISPATCHING"},
                "attempts": {"N": "1"},
                "last_attempt_timestamp": {"N": str(now)},
                "ttl": {"N": str(ttl)},
            },
            ConditionExpression="attribute_not_exists(cluster_id)",
        )
        return True
    except Exception as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code != "ConditionalCheckFailedException" and "ConditionalCheckFailed" not in str(e):
            raise

    # 2. Key exists: inspect existing lock item for recovery or retry eligibility
    try:
        resp = ddb_client.get_item(
            TableName=table_name,
            Key={"cluster_id": {"S": lock_key}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            # Race: lock was deleted; abort this turn
            return False

        current_status = item.get("status", {}).get("S", "UNKNOWN")
        current_attempts = int(item.get("attempts", {}).get("N", "1"))
        last_attempt_ts = float(item.get("last_attempt_timestamp", {}).get("N", "0"))

        # Invariant: COMPLETED dispatch must NEVER be re-opened
        if current_status == "COMPLETED":
            return False

        # Invariant: Bounded retry limit
        if current_attempts >= MAX_DISPATCH_ATTEMPTS:
            return False

        # Invariant: Stale lock recovery or retry on recorded failure
        is_stale = (current_status == "DISPATCHING") and ((now - last_attempt_ts) > STALE_LOCK_TIMEOUT_SECONDS)
        is_failed = (current_status == "FAILED")

        if is_stale or is_failed:
            new_attempts = current_attempts + 1
            ddb_client.update_item(
                TableName=table_name,
                Key={"cluster_id": {"S": lock_key}},
                UpdateExpression="SET #st = :st, attempts = :att, last_attempt_timestamp = :now",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":st": {"S": "DISPATCHING"},
                    ":att": {"N": str(new_attempts)},
                    ":now": {"N": str(now)},
                    ":old_att": {"N": str(current_attempts)},
                },
                ConditionExpression="attempts = :old_att",
            )
            return True

        return False
    except Exception as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException" or "ConditionalCheckFailed" in str(e):
            # Concurrent worker updated lock
            return False
        raise


def complete_dispatch_lock(
    ddb_client: Any,
    table_name: str,
    incident_id: str,
    session_id: str,
    now_ts: Optional[float] = None,
) -> None:
    """Marks dispatch lock as COMPLETED (terminal state, zero further retries allowed)."""
    if ddb_client is None:
        return
    now = float(now_ts or time.time())
    lock_key = f"LOCK#DISPATCH#{incident_id}"
    try:
        ddb_client.update_item(
            TableName=table_name,
            Key={"cluster_id": {"S": lock_key}},
            UpdateExpression="SET #st = :st, session_id = :sid, completed_at = :now",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": {"S": "COMPLETED"},
                ":sid": {"S": session_id},
                ":now": {"N": str(now)},
            },
        )
    except Exception as e:
        print(f"[WARN] Failed to mark dispatch lock COMPLETED: {e}")


def fail_dispatch_lock(
    ddb_client: Any,
    table_name: str,
    incident_id: str,
    error_message: str,
    now_ts: Optional[float] = None,
) -> None:
    """Marks dispatch lock as FAILED so bounded retry can proceed if attempts remain."""
    if ddb_client is None:
        return
    now = float(now_ts or time.time())
    lock_key = f"LOCK#DISPATCH#{incident_id}"
    try:
        ddb_client.update_item(
            TableName=table_name,
            Key={"cluster_id": {"S": lock_key}},
            UpdateExpression="SET #st = :st, error_message = :err, failed_at = :now",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":st": {"S": "FAILED"},
                ":err": {"S": error_message[:500]},
                ":now": {"N": str(now)},
            },
        )
    except Exception as e:
        print(f"[WARN] Failed to mark dispatch lock FAILED: {e}")


def check_cluster_cooldown_active(
    ddb_client: Any,
    table_name: str,
    cluster_name: str,
    now_ts: Optional[float] = None,
) -> bool:
    """
    Checks if a cluster-wide remediation cooldown budget is currently active.
    Returns True if cooldown is active (remediation prevented by cooldown).
    Returns False if cooldown has expired or no record exists.
    """
    if ddb_client is None:
        return False

    now = float(now_ts or time.time())
    budget_key = f"BUDGET#{cluster_name}"

    try:
        resp = ddb_client.get_item(
            TableName=table_name,
            Key={"cluster_id": {"S": budget_key}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return False

        expires_at = float(item.get("cooldown_expires_at", {}).get("N", "0"))
        return expires_at > now
    except Exception as e:
        print(f"[WARN] Error reading cluster cooldown: {e}")
        return True
