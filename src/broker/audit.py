"""
BlastGate Fail-Closed Audit Logging Engine (Rule R6)
Emits structured, append-only immutable audit records to DynamoDB and CloudWatch.
Enforces conditional PutItem: attribute_not_exists(event_id).
Cryptographic SHA-256 hash chaining is maintained per execution context to guarantee
sequential tamper-evidence across events emitted within the broker invocation cycle.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import json

from config import AUDIT_TABLE_NAME
from models import AuditRecord
from errors import AuditWriteError, InternalBrokerError


class AuditStore(ABC):
    """Abstract interface for writing immutable audit events."""

    @abstractmethod
    def append_event(self, record: AuditRecord) -> Dict[str, Any]:
        pass


class MockAuditStore(AuditStore):
    """Deterministic in-memory audit store for testing."""

    def __init__(self, fail_writes: bool = False):
        self.events: List[Dict[str, Any]] = []
        self.fail_writes = fail_writes

    def append_event(self, record: AuditRecord) -> Dict[str, Any]:
        if self.fail_writes:
            raise AuditWriteError("Simulated audit write failure.")

        data = record.to_dict()
        event_id = data["event_id"]
        # Enforce attribute_not_exists(event_id)
        if any(e["event_id"] == event_id for e in self.events):
            raise AuditWriteError(f"Duplicate event_id '{event_id}' detected in audit store.")

        self.events.append(data)
        return data


class DynamoDbAuditStore(AuditStore):
    """Production DynamoDB audit store enforcing conditional PutItem."""

    def __init__(self, dynamodb_client=None, table_name: str = AUDIT_TABLE_NAME):
        self.client = dynamodb_client
        self.table_name = table_name

    def append_event(self, record: AuditRecord) -> Dict[str, Any]:
        if not self.client:
            raise InternalBrokerError("DynamoDB client is not configured for audit store.")

        data = record.to_dict()
        item = {
            "event_id": {"S": data["event_id"]},
            "event_type": {"S": data["event_type"]},
            "incident_id": {"S": data["incident_id"]},
            "decision_id": {"S": data["decision_id"]},
            "actor_type": {"S": data["actor_type"]},
            "requested_action": {"S": data["requested_action"]},
            "authorization_decision": {"S": data["authorization_decision"]},
            "execution_status": {"S": data["execution_status"]},
            "timestamp": {"S": data["timestamp"]},
            "schema_version": {"S": data["schema_version"]},
            "payload_json": {"S": json.dumps(data, sort_keys=True)},
        }

        try:
            self.client.put_item(
                TableName=self.table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(event_id)",
            )
            return data
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "ConditionalCheckFailedException":
                raise AuditWriteError(f"Audit event '{data['event_id']}' already exists.")
            raise AuditWriteError(f"Failed to record mandatory audit event: {e}")


class AuditLogger:
    """Manages structured immutable audit emission with fail-closed semantics."""

    def __init__(self, store: AuditStore, default_actor: str = "LAMBDA_BROKER"):
        self.store = store
        self.default_actor = default_actor
        self._last_event_sha256: Optional[str] = None

    def log_event(
        self,
        event_type: str,
        incident_id: str,
        decision_id: str,
        requested_action: str,
        authorization_decision: str,
        execution_status: str,
        rule_results: Dict[str, bool],
        evidence_references: Optional[List[str]] = None,
        actor_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates, validates, and appends a structured audit event.
        Fails closed on any error.
        """
        record = AuditRecord(
            event_type=event_type,
            incident_id=incident_id,
            decision_id=decision_id,
            actor_type=actor_type or self.default_actor,
            rule_results=rule_results,
            requested_action=requested_action,
            authorization_decision=authorization_decision,
            execution_status=execution_status,
            evidence_references=evidence_references or [],
            previous_event_sha256=self._last_event_sha256,
        )
        data = self.store.append_event(record)
        self._last_event_sha256 = data["integrity"]["event_sha256"]
        return data
