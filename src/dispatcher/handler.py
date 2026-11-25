"""
BlastGate Harness Dispatcher Lambda Handler
Triggered by EventBridge BlastGate.IncidentOpened events.
Validates incident schema, acquires atomic dispatch lock, checks cooldown,
and invokes the AgentCore Managed Harness.
"""

import json
import os
import re
import sys
import time
import uuid
from typing import Dict, Any, Optional

try:
    from .config import (
        STATE_TABLE_NAME,
        HARNESS_ARN,
        CLUSTER_NAME,
        AWS_REGION,
        LOCK_TTL_SECONDS,
    )
    from .lock import (
        acquire_dispatch_lock,
        complete_dispatch_lock,
        fail_dispatch_lock,
        check_cluster_cooldown_active,
    )
except (ImportError, ValueError):
    from config import (
        STATE_TABLE_NAME,
        HARNESS_ARN,
        CLUSTER_NAME,
        AWS_REGION,
        LOCK_TTL_SECONDS,
    )
    from lock import (
        acquire_dispatch_lock,
        complete_dispatch_lock,
        fail_dispatch_lock,
        check_cluster_cooldown_active,
    )

INCIDENT_ID_PATTERN = re.compile(r"^inc-[a-f0-9]{8,36}$")


def _is_live_aws_runtime() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))


def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    ddb_client: Any = None,
    agentcore_client: Any = None,
    now_fn=None,
) -> Dict[str, Any]:
    """
    Handles EventBridge BlastGate.IncidentOpened event.
    Dispatches to AgentCore Managed Harness with atomic deduplication.
    """
    now = float(now_fn() if now_fn else time.time())

    # 1. Parse Event Payload
    detail = event.get("detail", event)
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except Exception:
            return {
                "statusCode": 400,
                "dispatched": False,
                "error": "MALFORMED_JSON_DETAIL",
            }

    incident_id = detail.get("incident_id")
    if not incident_id or not INCIDENT_ID_PATTERN.match(str(incident_id)):
        return {
            "statusCode": 400,
            "dispatched": False,
            "error": "INVALID_INCIDENT_ID",
            "incident_id": incident_id,
        }

    cluster_name = detail.get("cluster_name", CLUSTER_NAME)

    # 2. Initialize AWS Clients if in live runtime
    ddb = ddb_client
    agentcore = agentcore_client

    if _is_live_aws_runtime():
        import boto3
        region = os.environ.get("AWS_REGION", AWS_REGION)
        if ddb is None:
            ddb = boto3.client("dynamodb", region_name=region)
        if agentcore is None:
            agentcore = boto3.client("bedrock-agentcore", region_name=region)

    # 3. Atomic Dispatch Lock (Deduplication)
    table_name = os.environ.get("STATE_TABLE_NAME", STATE_TABLE_NAME)
    if ddb is not None:
        lock_acquired = acquire_dispatch_lock(
            ddb_client=ddb,
            table_name=table_name,
            incident_id=incident_id,
            ttl_seconds=LOCK_TTL_SECONDS,
            now_ts=now,
        )
        if not lock_acquired:
            return {
                "statusCode": 200,
                "dispatched": False,
                "reason": "DUPLICATE_DISPATCH_SUPPRESSED",
                "incident_id": incident_id,
            }

    # 4. Cluster Cooldown Pre-check
    if ddb is not None:
        cooldown_active = check_cluster_cooldown_active(
            ddb_client=ddb,
            table_name=table_name,
            cluster_name=cluster_name,
            now_ts=now,
        )
        if cooldown_active:
            return {
                "statusCode": 200,
                "dispatched": False,
                "reason": "COOLDOWN_ACTIVE",
                "incident_id": incident_id,
                "cluster_name": cluster_name,
            }

    # 5. Invoke AgentCore Managed Harness
    harness_arn = os.environ.get("HARNESS_ARN", HARNESS_ARN)
    session_id = f"blastgate-dispatch-{incident_id[:16]}-{uuid.uuid4().hex[:8]}"
    prompt = (
        f"Operational incident opened. Incident ID: {incident_id}. "
        f"Investigate diagnostics and propose recovery if an unhealthy worker is verified."
    )

    if agentcore is not None:
        try:
            resp = agentcore.invoke_harness(
                harnessArn=harness_arn,
                runtimeSessionId=session_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
            # Mark lock as COMPLETED (terminal state, zero further retries allowed)
            if ddb is not None:
                complete_dispatch_lock(
                    ddb_client=ddb,
                    table_name=table_name,
                    incident_id=incident_id,
                    session_id=session_id,
                    now_ts=now,
                )
            return {
                "statusCode": 200,
                "dispatched": True,
                "incident_id": incident_id,
                "session_id": session_id,
                "harness_arn": harness_arn,
            }
        except Exception as e:
            print(f"[ERROR] Harness invocation failed: {e}", file=sys.stderr)
            if ddb is not None:
                fail_dispatch_lock(
                    ddb_client=ddb,
                    table_name=table_name,
                    incident_id=incident_id,
                    error_message=str(e),
                    now_ts=now,
                )
            return {
                "statusCode": 502,
                "dispatched": False,
                "error": "HARNESS_INVOCATION_FAILED",
                "details": str(e),
                "incident_id": incident_id,
                "session_id": session_id,
            }

    # Mock / Offline mode
    if ddb is not None:
        complete_dispatch_lock(
            ddb_client=ddb,
            table_name=table_name,
            incident_id=incident_id,
            session_id=session_id,
            now_ts=now,
        )
    return {
        "statusCode": 200,
        "dispatched": True,
        "incident_id": incident_id,
        "session_id": session_id,
        "harness_arn": harness_arn,
        "mode": "offline_mock",
    }
