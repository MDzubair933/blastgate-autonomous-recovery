"""
BlastGate Atomic Global Cooldown Budget (Rule R4 & Invariant 2)
Enforces a maximum of one authorized replacement per rolling 600-second window across the protected cluster.
Uses DynamoDB conditional atomic updates.
"""

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

from config import (
    ALLOWED_CLUSTER,
    COOLDOWN_WINDOW_SECONDS,
    STATE_TABLE_NAME,
    CLOCK_SKEW_TOLERANCE_SECONDS,
)
from errors import CooldownActiveError, InternalBrokerError


@dataclass(frozen=True)
class CooldownReservation:
    cluster_id: str
    incident_id: str
    reservation_id: str
    reserved_at: float
    expires_at: float


class StateStoreProvider(ABC):
    """Abstract interface for atomic state coordination in DynamoDB."""

    @abstractmethod
    def reserve_cluster_cooldown(
        self,
        cluster_id: str,
        incident_id: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        pass

    @abstractmethod
    def reserve_atomic_transaction(
        self,
        cluster_id: str,
        incident_id: str,
        idempotency_key: str,
        target_task_arn: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        pass

    @abstractmethod
    def reserve_atomic_transaction(
        self,
        cluster_id: str,
        incident_id: str,
        idempotency_key: str,
        target_task_arn: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        if self.client is None:
            raise InternalBrokerError("DynamoDB client is not configured.")

        b_key = f"BUDGET#{cluster_id}"
        i_key = f"IDEMPOTENCY#{idempotency_key}"
        new_expires_at = int(now_ts + cooldown_window)
        now_int = int(now_ts)

        transact_items = [
            {
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"cluster_id": {"S": b_key}},
                    "UpdateExpression": (
                        "SET last_authorized_timestamp = :now, "
                        "cooldown_expires_at = :expires_at, "
                        "last_reservation_id = :res_id, "
                        "last_incident_id = :inc_id"
                    ),
                    "ConditionExpression": "attribute_not_exists(cluster_id) OR cooldown_expires_at <= :now",
                    "ExpressionAttributeValues": {
                        ":now": {"N": str(now_int)},
                        ":expires_at": {"N": str(new_expires_at)},
                        ":res_id": {"S": reservation_id},
                        ":inc_id": {"S": incident_id},
                    },
                }
            },
            {
                "Put": {
                    "TableName": self.table_name,
                    "Item": {
                        "cluster_id": {"S": i_key},
                        "incident_id": {"S": incident_id},
                        "target_task_arn": {"S": target_task_arn},
                        "status": {"S": "IN_PROGRESS"},
                        "created_at": {"N": str(now_int)},
                    },
                    "ConditionExpression": "attribute_not_exists(cluster_id)",
                }
            },
        ]

        try:
            self.client.transact_write_items(TransactItems=transact_items)
            return CooldownReservation(
                cluster_id=cluster_id,
                incident_id=incident_id,
                reservation_id=reservation_id,
                reserved_at=now_ts,
                expires_at=float(new_expires_at),
            )
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "TransactionCanceledException" or "TransactionCanceledException" in str(e):
                raise CooldownActiveError(
                    f"Atomic transaction canceled for cluster '{cluster_id}' and incident '{incident_id}'. "
                    f"Either cooldown is active or proposal already has active/completed state."
                )
            raise InternalBrokerError(f"DynamoDB atomic transaction failed: {e}")

    def get_cluster_cooldown(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        pass


class MockStateStoreProvider(StateStoreProvider):
    """
    Deterministic in-memory state store for unit testing.
    Replicates DynamoDB conditional update semantics accurately without threading locks.
    """

    def __init__(self):
        self.items: Dict[str, Dict[str, Any]] = {}

    def reserve_cluster_cooldown(
        self,
        cluster_id: str,
        incident_id: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        key = f"BUDGET#{cluster_id}"
        existing = self.items.get(key)
        if existing is not None:
            expires_at = existing.get("cooldown_expires_at", 0)
            # DynamoDB condition: attribute_not_exists OR cooldown_expires_at <= :now
            if expires_at > now_ts:
                remaining = expires_at - now_ts
                raise CooldownActiveError(
                    f"Global cooldown active on cluster '{cluster_id}'. "
                    f"{remaining:.1f}s remaining in 600s window. Active incident: {existing.get('last_incident_id')}"
                )

        new_expires_at = now_ts + cooldown_window
        record = {
            "cluster_id": key,
            "last_authorized_timestamp": now_ts,
            "cooldown_expires_at": new_expires_at,
            "last_reservation_id": reservation_id,
            "last_incident_id": incident_id,
        }
        self.items[key] = record
        return CooldownReservation(
            cluster_id=cluster_id,
            incident_id=incident_id,
            reservation_id=reservation_id,
            reserved_at=now_ts,
            expires_at=new_expires_at,
        )

    def reserve_atomic_transaction(
        self,
        cluster_id: str,
        incident_id: str,
        idempotency_key: str,
        target_task_arn: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        if self.client is None:
            raise InternalBrokerError("DynamoDB client is not configured.")

        b_key = f"BUDGET#{cluster_id}"
        i_key = f"IDEMPOTENCY#{idempotency_key}"
        new_expires_at = int(now_ts + cooldown_window)
        now_int = int(now_ts)

        transact_items = [
            {
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"cluster_id": {"S": b_key}},
                    "UpdateExpression": (
                        "SET last_authorized_timestamp = :now, "
                        "cooldown_expires_at = :expires_at, "
                        "last_reservation_id = :res_id, "
                        "last_incident_id = :inc_id"
                    ),
                    "ConditionExpression": "attribute_not_exists(cluster_id) OR cooldown_expires_at <= :now",
                    "ExpressionAttributeValues": {
                        ":now": {"N": str(now_int)},
                        ":expires_at": {"N": str(new_expires_at)},
                        ":res_id": {"S": reservation_id},
                        ":inc_id": {"S": incident_id},
                    },
                }
            },
            {
                "Put": {
                    "TableName": self.table_name,
                    "Item": {
                        "cluster_id": {"S": i_key},
                        "incident_id": {"S": incident_id},
                        "target_task_arn": {"S": target_task_arn},
                        "status": {"S": "IN_PROGRESS"},
                        "created_at": {"N": str(now_int)},
                    },
                    "ConditionExpression": "attribute_not_exists(cluster_id)",
                }
            },
        ]

        try:
            self.client.transact_write_items(TransactItems=transact_items)
            return CooldownReservation(
                cluster_id=cluster_id,
                incident_id=incident_id,
                reservation_id=reservation_id,
                reserved_at=now_ts,
                expires_at=float(new_expires_at),
            )
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "TransactionCanceledException" or "TransactionCanceledException" in str(e):
                raise CooldownActiveError(
                    f"Atomic transaction canceled for cluster '{cluster_id}' and incident '{incident_id}'. "
                    f"Either cooldown is active or proposal already has active/completed state."
                )
            raise InternalBrokerError(f"DynamoDB atomic transaction failed: {e}")

    def get_cluster_cooldown(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        return self.items.get(f"BUDGET#{cluster_id}")


class DynamoDbStateStoreProvider(StateStoreProvider):
    """Production DynamoDB state store implementing conditional atomic writes."""

    def __init__(self, dynamodb_client=None, table_name: str = STATE_TABLE_NAME):
        self.client = dynamodb_client
        self.table_name = table_name

    def reserve_cluster_cooldown(
        self,
        cluster_id: str,
        incident_id: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        if self.client is None:
            raise InternalBrokerError("DynamoDB client is not configured.")

        key = f"BUDGET#{cluster_id}"
        new_expires_at = int(now_ts + cooldown_window)
        now_int = int(now_ts)

        try:
            # DynamoDB Conditional Atomic Update
            self.client.update_item(
                TableName=self.table_name,
                Key={"cluster_id": {"S": key}},
                UpdateExpression=(
                    "SET last_authorized_timestamp = :now, "
                    "cooldown_expires_at = :expires_at, "
                    "last_reservation_id = :res_id, "
                    "last_incident_id = :inc_id"
                ),
                ConditionExpression=(
                    "attribute_not_exists(cluster_id) OR cooldown_expires_at <= :now"
                ),
                ExpressionAttributeValues={
                    ":now": {"N": str(now_int)},
                    ":expires_at": {"N": str(new_expires_at)},
                    ":res_id": {"S": reservation_id},
                    ":inc_id": {"S": incident_id},
                },
                ReturnValues="ALL_NEW",
            )
            return CooldownReservation(
                cluster_id=cluster_id,
                incident_id=incident_id,
                reservation_id=reservation_id,
                reserved_at=now_ts,
                expires_at=float(new_expires_at),
            )
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "ConditionalCheckFailedException" or "ConditionalCheckFailedException" in str(e):
                raise CooldownActiveError(
                    f"Global cooldown active on cluster '{cluster_id}'. Another remediation holds the 600s reservation."
                )
            raise InternalBrokerError(f"DynamoDB state reservation failed: {e}")

    def reserve_atomic_transaction(
        self,
        cluster_id: str,
        incident_id: str,
        idempotency_key: str,
        target_task_arn: str,
        reservation_id: str,
        now_ts: float,
        cooldown_window: int,
    ) -> CooldownReservation:
        if self.client is None:
            raise InternalBrokerError("DynamoDB client is not configured.")

        b_key = f"BUDGET#{cluster_id}"
        i_key = f"IDEMPOTENCY#{idempotency_key}"
        new_expires_at = int(now_ts + cooldown_window)
        now_int = int(now_ts)

        transact_items = [
            {
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"cluster_id": {"S": b_key}},
                    "UpdateExpression": (
                        "SET last_authorized_timestamp = :now, "
                        "cooldown_expires_at = :expires_at, "
                        "last_reservation_id = :res_id, "
                        "last_incident_id = :inc_id"
                    ),
                    "ConditionExpression": "attribute_not_exists(cluster_id) OR cooldown_expires_at <= :now",
                    "ExpressionAttributeValues": {
                        ":now": {"N": str(now_int)},
                        ":expires_at": {"N": str(new_expires_at)},
                        ":res_id": {"S": reservation_id},
                        ":inc_id": {"S": incident_id},
                    },
                }
            },
            {
                "Put": {
                    "TableName": self.table_name,
                    "Item": {
                        "cluster_id": {"S": i_key},
                        "incident_id": {"S": incident_id},
                        "target_task_arn": {"S": target_task_arn},
                        "status": {"S": "IN_PROGRESS"},
                        "created_at": {"N": str(now_int)},
                    },
                    "ConditionExpression": "attribute_not_exists(cluster_id)",
                }
            },
        ]

        try:
            self.client.transact_write_items(TransactItems=transact_items)
            return CooldownReservation(
                cluster_id=cluster_id,
                incident_id=incident_id,
                reservation_id=reservation_id,
                reserved_at=now_ts,
                expires_at=float(new_expires_at),
            )
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "TransactionCanceledException" or "TransactionCanceledException" in str(e):
                raise CooldownActiveError(
                    f"Atomic transaction canceled for cluster '{cluster_id}' and incident '{incident_id}'. "
                    f"Either cooldown is active or proposal already has active/completed state."
                )
            raise InternalBrokerError(f"DynamoDB atomic transaction failed: {e}")

    def get_cluster_cooldown(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        if self.client is None:
            return None
        key = f"BUDGET#{cluster_id}"
        resp = self.client.get_item(
            TableName=self.table_name,
            Key={"cluster_id": {"S": key}},
            ConsistentRead=True,
        )
        return resp.get("Item")


class CooldownManager:
    """Manages cluster-wide risk budget and atomic temporal throttling."""

    def __init__(
        self,
        state_provider: StateStoreProvider,
        cooldown_window_seconds: int = COOLDOWN_WINDOW_SECONDS,
        current_time_fn=None,
    ):
        self.state_provider = state_provider
        self.cooldown_window_seconds = cooldown_window_seconds
        self.current_time_fn = current_time_fn or time.time

    def reserve_budget(self, cluster_id: str, incident_id: str) -> CooldownReservation:
        """
        Atomically attempts to acquire the single allowable reservation
        for the rolling 600-second window across the cluster.
        Fails closed on any conflict or error.
        """
        now = self.current_time_fn()
        reservation_id = f"res-{uuid.uuid4().hex[:16]}"
        return self.state_provider.reserve_cluster_cooldown(
            cluster_id=cluster_id,
            incident_id=incident_id,
            reservation_id=reservation_id,
            now_ts=now,
            cooldown_window=self.cooldown_window_seconds,
        )
