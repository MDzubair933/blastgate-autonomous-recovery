"""
BlastGate Harness Dispatcher Unit Tests
Covers:
1. Successful dispatch to AgentCore Managed Harness
2. Duplicate event suppression via atomic DynamoDB dispatch lock
3. Invalid incident schema handling
4. Harness invocation failure handling
5. Cooldown budget pre-check
6. Concurrency lock behavior
"""

import json
import time
import pytest
from botocore.exceptions import ClientError

from dispatcher.handler import lambda_handler
from dispatcher.lock import acquire_dispatch_lock, check_cluster_cooldown_active


class MockDynamoDb:
    def __init__(self):
        self.items = {}
        self.put_calls = []
        self.update_calls = []

    def put_item(self, TableName, Item, ConditionExpression=None):
        pk = Item["cluster_id"]["S"]
        self.put_calls.append({"table": TableName, "pk": pk, "item": Item})
        if ConditionExpression and "attribute_not_exists" in ConditionExpression:
            if pk in self.items:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "The conditional request failed"}},
                    "PutItem"
                )
        self.items[pk] = Item

    def get_item(self, TableName, Key, ConsistentRead=False):
        pk = Key["cluster_id"]["S"]
        item = self.items.get(pk)
        return {"Item": item} if item else {}

    def update_item(
        self,
        TableName,
        Key,
        UpdateExpression,
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
        ConditionExpression=None,
    ):
        pk = Key["cluster_id"]["S"]
        self.update_calls.append({
            "table": TableName,
            "pk": pk,
            "update_expr": UpdateExpression,
            "values": ExpressionAttributeValues,
        })
        item = self.items.setdefault(pk, {"cluster_id": {"S": pk}})
        if ConditionExpression and "attempts = :old_att" in ConditionExpression:
            expected_old = ExpressionAttributeValues[":old_att"]["N"]
            curr_attempts = item.get("attempts", {}).get("N", "1")
            if curr_attempts != expected_old:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional check failed"}},
                    "UpdateItem"
                )
        if ExpressionAttributeValues:
            if ":st" in ExpressionAttributeValues:
                item["status"] = ExpressionAttributeValues[":st"]
            if ":att" in ExpressionAttributeValues:
                item["attempts"] = ExpressionAttributeValues[":att"]
            if ":now" in ExpressionAttributeValues:
                item["last_attempt_timestamp"] = ExpressionAttributeValues[":now"]
            if ":sid" in ExpressionAttributeValues:
                item["session_id"] = ExpressionAttributeValues[":sid"]
            if ":err" in ExpressionAttributeValues:
                item["error_message"] = ExpressionAttributeValues[":err"]
        return {"Attributes": item}


class MockAgentCore:
    def __init__(self, should_fail: bool = False, fail_code: str = "ThrottlingException"):
        self.invocations = []
        self.should_fail = should_fail
        self.fail_code = fail_code

    def invoke_harness(self, harnessArn, runtimeSessionId, messages):
        if self.should_fail:
            raise ClientError(
                {"Error": {"Code": self.fail_code, "Message": "Simulated harness invocation error"}},
                "InvokeHarness"
            )
        call_info = {
            "harnessArn": harnessArn,
            "runtimeSessionId": runtimeSessionId,
            "messages": messages,
        }
        self.invocations.append(call_info)
        return {"sessionId": runtimeSessionId, "status": "RUNNING"}


def test_successful_dispatch_to_managed_harness():
    """Valid IncidentOpened event acquires lock and invokes Managed Harness."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore()
    now_ts = 1795600000.0

    event = {
        "source": "blastgate.incidents",
        "detail-type": "BlastGate.IncidentOpened",
        "detail": {
            "incident_id": "inc-f445801e0cb89926",
            "alarm_name": "blastgate-worker-stalled-alarm",
            "cluster_name": "blastgate-sandbox",
        }
    }

    resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore, now_fn=lambda: now_ts)

    assert resp["statusCode"] == 200
    assert resp["dispatched"] is True
    assert resp["incident_id"] == "inc-f445801e0cb89926"
    assert "session_id" in resp
    assert len(agentcore.invocations) == 1

    # Verify atomic lock persisted in DynamoDB with COMPLETED status
    lock_pk = "LOCK#DISPATCH#inc-f445801e0cb89926"
    assert lock_pk in ddb.items
    assert ddb.items[lock_pk]["status"]["S"] == "COMPLETED"
    assert ddb.items[lock_pk]["session_id"]["S"] == resp["session_id"]


def test_duplicate_event_suppressed_by_dispatch_lock():
    """Duplicate event for the same incident ID is suppressed by the dispatch lock."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore()
    incident_id = "inc-f445801e0cb89926"

    # Pre-seed existing COMPLETED lock
    ddb.items[f"LOCK#DISPATCH#{incident_id}"] = {
        "cluster_id": {"S": f"LOCK#DISPATCH#{incident_id}"},
        "incident_id": {"S": incident_id},
        "status": {"S": "COMPLETED"},
        "attempts": {"N": "1"},
    }

    event = {
        "detail": {
            "incident_id": incident_id,
            "alarm_name": "blastgate-worker-stalled-alarm",
        }
    }

    resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore)

    assert resp["statusCode"] == 200
    assert resp["dispatched"] is False
    assert resp["reason"] == "DUPLICATE_DISPATCH_SUPPRESSED"
    assert resp["incident_id"] == incident_id
    assert len(agentcore.invocations) == 0


def test_invalid_incident_schema_rejected():
    """Malformed or non-hex incident IDs fail closed immediately."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore()

    invalid_ids = [
        "not-an-incident",
        "inc-UPPERCASE_NOT_ALLOWED",
        "inc-short",
        "",
        None,
        "inc-12345!",
    ]

    for bad_id in invalid_ids:
        event = {"detail": {"incident_id": bad_id}}
        resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore)
        assert resp["statusCode"] == 400
        assert resp["dispatched"] is False
        assert resp["error"] == "INVALID_INCIDENT_ID"

    assert len(agentcore.invocations) == 0
    assert len(ddb.put_calls) == 0


def test_cooldown_active_suppresses_dispatch():
    """When cluster cooldown budget is active, dispatch is safely suppressed."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore()
    now_ts = 1795600000.0

    # Seed active cooldown (expires 300s into the future)
    ddb.items["BUDGET#blastgate-sandbox"] = {
        "cluster_id": {"S": "BUDGET#blastgate-sandbox"},
        "cooldown_expires_at": {"N": str(now_ts + 300)},
    }

    event = {
        "detail": {
            "incident_id": "inc-e84b13afb5cfae59",
            "cluster_name": "blastgate-sandbox",
        }
    }

    resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore, now_fn=lambda: now_ts)

    assert resp["statusCode"] == 200
    assert resp["dispatched"] is False
    assert resp["reason"] == "COOLDOWN_ACTIVE"
    assert len(agentcore.invocations) == 0


def test_harness_invocation_failure_handled():
    """When AgentCore returns an error, dispatcher returns 502 without crashing."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore(should_fail=True, fail_code="InternalServerException")

    event = {
        "detail": {
            "incident_id": "inc-e858762716fd8965",
        }
    }

    resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore)

    assert resp["statusCode"] == 502
    assert resp["dispatched"] is False
    assert resp["error"] == "HARNESS_INVOCATION_FAILED"
    assert resp["incident_id"] == "inc-e858762716fd8965"

    # Verify lock was marked FAILED with error message
    lock_pk = "LOCK#DISPATCH#inc-e858762716fd8965"
    assert lock_pk in ddb.items
    assert ddb.items[lock_pk]["status"]["S"] == "FAILED"
    assert "Simulated harness invocation error" in ddb.items[lock_pk]["error_message"]["S"]


def test_bounded_retry_on_failed_lock():
    """When a previous attempt failed and attempts < 3, retry is permitted."""
    ddb = MockDynamoDb()
    inc_id = "inc-retry11223344"
    lock_pk = f"LOCK#DISPATCH#{inc_id}"

    # Pre-seed FAILED lock with attempts=1
    ddb.items[lock_pk] = {
        "cluster_id": {"S": lock_pk},
        "incident_id": {"S": inc_id},
        "status": {"S": "FAILED"},
        "attempts": {"N": "1"},
        "last_attempt_timestamp": {"N": "1000.0"},
    }

    # Attempt retry at now=1010.0
    acquired = acquire_dispatch_lock(ddb, "blastgate-state", inc_id, now_ts=1010.0)
    assert acquired is True
    assert ddb.items[lock_pk]["status"]["S"] == "DISPATCHING"
    assert ddb.items[lock_pk]["attempts"]["N"] == "2"


def test_stale_lock_recovery_after_timeout():
    """A crashed/timed-out invocation (status DISPATCHING > 120s old) can be recovered."""
    ddb = MockDynamoDb()
    inc_id = "inc-stale99887766"
    lock_pk = f"LOCK#DISPATCH#{inc_id}"

    # Pre-seed DISPATCHING lock from 150 seconds ago (exceeds 120s timeout)
    ddb.items[lock_pk] = {
        "cluster_id": {"S": lock_pk},
        "incident_id": {"S": inc_id},
        "status": {"S": "DISPATCHING"},
        "attempts": {"N": "1"},
        "last_attempt_timestamp": {"N": "1000.0"},
    }

    # Attempt at now=1150.0 (150s later)
    acquired = acquire_dispatch_lock(ddb, "blastgate-state", inc_id, now_ts=1150.0)
    assert acquired is True
    assert ddb.items[lock_pk]["status"]["S"] == "DISPATCHING"
    assert ddb.items[lock_pk]["attempts"]["N"] == "2"


def test_fresh_inflight_lock_cannot_be_usurped():
    """An in-flight DISPATCHING lock younger than 120s cannot be acquired by another worker."""
    ddb = MockDynamoDb()
    inc_id = "inc-inflight4455"
    lock_pk = f"LOCK#DISPATCH#{inc_id}"

    ddb.items[lock_pk] = {
        "cluster_id": {"S": lock_pk},
        "incident_id": {"S": inc_id},
        "status": {"S": "DISPATCHING"},
        "attempts": {"N": "1"},
        "last_attempt_timestamp": {"N": "1000.0"},
    }

    # Attempt only 30 seconds later (within 120s window)
    acquired = acquire_dispatch_lock(ddb, "blastgate-state", inc_id, now_ts=1030.0)
    assert acquired is False


def test_lockout_after_max_attempts_exhausted():
    """When attempts reach MAX_DISPATCH_ATTEMPTS (3), neither failure nor timeout permits retry."""
    ddb = MockDynamoDb()
    inc_id = "inc-exhausted33"
    lock_pk = f"LOCK#DISPATCH#{inc_id}"

    # Lock with attempts=3 and status=FAILED
    ddb.items[lock_pk] = {
        "cluster_id": {"S": lock_pk},
        "incident_id": {"S": inc_id},
        "status": {"S": "FAILED"},
        "attempts": {"N": "3"},
        "last_attempt_timestamp": {"N": "1000.0"},
    }

    acquired = acquire_dispatch_lock(ddb, "blastgate-state", inc_id, now_ts=2000.0)
    assert acquired is False


def test_completed_dispatch_terminal_lockout():
    """COMPLETED dispatch can NEVER be re-acquired under any circumstance."""
    ddb = MockDynamoDb()
    inc_id = "inc-completed77"
    lock_pk = f"LOCK#DISPATCH#{inc_id}"

    ddb.items[lock_pk] = {
        "cluster_id": {"S": lock_pk},
        "incident_id": {"S": inc_id},
        "status": {"S": "COMPLETED"},
        "attempts": {"N": "1"},
        "last_attempt_timestamp": {"N": "1000.0"},
    }

    acquired = acquire_dispatch_lock(ddb, "blastgate-state", inc_id, now_ts=5000.0)
    assert acquired is False


def test_eventbridge_json_string_detail():
    """Handles EventBridge detail provided as serialized JSON string."""
    ddb = MockDynamoDb()
    agentcore = MockAgentCore()

    event = {
        "detail": json.dumps({"incident_id": "inc-8e9916c5340c43fa"})
    }

    resp = lambda_handler(event, ddb_client=ddb, agentcore_client=agentcore)
    assert resp["statusCode"] == 200
    assert resp["dispatched"] is True
    assert resp["incident_id"] == "inc-8e9916c5340c43fa"
    assert len(agentcore.invocations) == 1


def test_concurrency_lock_deduplication():
    """Directly tests lock acquisition utility under simulated race."""
    ddb = MockDynamoDb()
    inc_id = "inc-f2b55bcf2e8628d7"

    # First attempt: succeeds
    acq1 = acquire_dispatch_lock(ddb, "blastgate-state", inc_id)
    assert acq1 is True

    # Second attempt: fails
    acq2 = acquire_dispatch_lock(ddb, "blastgate-state", inc_id)
    assert acq2 is False
