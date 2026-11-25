"""
BlastGate Durable Request Idempotency Manager (Rule R8)
Guarantees duplicate proposals return the existing decision receipt rather than re-executing.
Coordinates request-level identity in the DynamoDB state store.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

from config import STATE_TABLE_NAME
from errors import CooldownActiveError, InternalBrokerError


@dataclass
class IdempotencyRecord:
    idempotency_key: str
    incident_id: str
    target_task_arn: str
    status: str  # IN_PROGRESS, COMPLETED, FAILED
    created_at: float
    decision_receipt: Optional[Dict[str, Any]] = None


class IdempotencyStore(ABC):
    """Abstract interface for durable request idempotency storage."""

    @abstractmethod
    def get_record(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        pass

    @abstractmethod
    def acquire_lock(self, idempotency_key: str, incident_id: str, target_task_arn: str, now_ts: float) -> bool:
        pass

    @abstractmethod
    def record_completion(self, idempotency_key: str, decision_receipt: Dict[str, Any]):
        pass


class MockIdempotencyStore(IdempotencyStore):
    """Deterministic in-memory idempotency store for unit testing."""

    def __init__(self):
        self.records: Dict[str, IdempotencyRecord] = {}

    def get_record(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        return self.records.get(idempotency_key)

    def acquire_lock(self, idempotency_key: str, incident_id: str, target_task_arn: str, now_ts: float) -> bool:
        if idempotency_key in self.records:
            return False
        self.records[idempotency_key] = IdempotencyRecord(
            idempotency_key=idempotency_key,
            incident_id=incident_id,
            target_task_arn=target_task_arn,
            status="IN_PROGRESS",
            created_at=now_ts,
        )
        return True

    def record_completion(self, idempotency_key: str, decision_receipt: Dict[str, Any]):
        rec = self.records.get(idempotency_key)
        if rec:
            rec.status = "COMPLETED"
            rec.decision_receipt = decision_receipt


class DynamoDbIdempotencyStore(IdempotencyStore):
    """Production DynamoDB request idempotency store."""

    def __init__(self, dynamodb_client=None, table_name: str = STATE_TABLE_NAME):
        self.client = dynamodb_client
        self.table_name = table_name

    def get_record(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        if not self.client:
            return None
        pk = f"IDEMPOTENCY#{idempotency_key}"
        resp = self.client.get_item(
            TableName=self.table_name,
            Key={"cluster_id": {"S": pk}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None

        receipt_str = item.get("decision_receipt", {}).get("S")
        receipt_dict = json.loads(receipt_str) if receipt_str else None

        return IdempotencyRecord(
            idempotency_key=idempotency_key,
            incident_id=item.get("incident_id", {}).get("S", ""),
            target_task_arn=item.get("target_task_arn", {}).get("S", ""),
            status=item.get("status", {}).get("S", "UNKNOWN"),
            created_at=float(item.get("created_at", {}).get("N", "0")),
            decision_receipt=receipt_dict,
        )

    def acquire_lock(self, idempotency_key: str, incident_id: str, target_task_arn: str, now_ts: float) -> bool:
        if not self.client:
            raise InternalBrokerError("DynamoDB client is not configured.")

        pk = f"IDEMPOTENCY#{idempotency_key}"
        try:
            self.client.put_item(
                TableName=self.table_name,
                Item={
                    "cluster_id": {"S": pk},
                    "incident_id": {"S": incident_id},
                    "target_task_arn": {"S": target_task_arn},
                    "status": {"S": "IN_PROGRESS"},
                    "created_at": {"N": str(int(now_ts))},
                },
                ConditionExpression="attribute_not_exists(cluster_id)",
            )
            return True
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "ConditionalCheckFailedException" or "ConditionalCheckFailedException" in str(e):
                return False
            raise InternalBrokerError(f"DynamoDB idempotency check failed: {e}")

    def record_completion(self, idempotency_key: str, decision_receipt: Dict[str, Any]):
        if not self.client:
            return
        pk = f"IDEMPOTENCY#{idempotency_key}"
        receipt_str = json.dumps(decision_receipt, sort_keys=True)
        self.client.update_item(
            TableName=self.table_name,
            Key={"cluster_id": {"S": pk}},
            UpdateExpression="SET #s = :status, decision_receipt = :receipt",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": {"S": "COMPLETED"},
                ":receipt": {"S": receipt_str},
            },
        )


class IdempotencyManager:
    """Orchestrates request identity deduplication."""

    def __init__(self, store: IdempotencyStore, current_time_fn=None):
        self.store = store
        self.current_time_fn = current_time_fn or time.time

    def compute_key(self, incident_id: str, action_id: str, target_task_arn: str) -> str:
        """Computes deterministic idempotency token from canonical request parameters."""
        raw = f"{incident_id}:{action_id}:{target_task_arn}"
        return raw

    def check_or_lock(self, incident_id: str, action_id: str, target_task_arn: str) -> Optional[Dict[str, Any]]:
        """
        If request is a duplicate and completed, returns cached decision receipt.
        If in progress, rejects concurrent execution.
        If fresh, acquires lock and returns None.
        """
        key = self.compute_key(incident_id, action_id, target_task_arn)
        record = self.store.get_record(key)
        if record:
            if record.status == "COMPLETED" and record.decision_receipt:
                return record.decision_receipt
            if record.status == "IN_PROGRESS":
                raise CooldownActiveError(
                    f"Identical remediation proposal for incident '{incident_id}' is already in progress."
                )

        now = self.current_time_fn()
        acquired = self.store.acquire_lock(key, incident_id, target_task_arn, now)
        if not acquired:
            # Race condition: another thread created the record concurrently
            rec = self.store.get_record(key)
            if rec and rec.decision_receipt:
                return rec.decision_receipt
            raise CooldownActiveError(f"Concurrent duplicate proposal detected for incident '{incident_id}'.")

        return None

    def finalize(self, incident_id: str, action_id: str, target_task_arn: str, decision_receipt: Dict[str, Any]):
        key = self.compute_key(incident_id, action_id, target_task_arn)
        self.store.record_completion(key, decision_receipt)
