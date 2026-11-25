"""
BlastGate Broker Models & Strict Schema Validation
Implements type-safe data structures and strict JSON Schema Draft-07 validation.
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
import jsonschema

from config import (
    REMEDIATION_REQUEST_SCHEMA_PATH,
    DECISION_RECEIPT_SCHEMA_PATH,
    AUDIT_SCHEMA_PATH,
    CATALOG_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    BROKER_ROLE_ARN,
)
from errors import RequestValidationError

# Load schemas once at module import
with open(REMEDIATION_REQUEST_SCHEMA_PATH, "r", encoding="utf-8") as f:
    REMEDIATION_REQUEST_SCHEMA = json.load(f)
jsonschema.Draft7Validator.check_schema(REMEDIATION_REQUEST_SCHEMA)
_REQUEST_VALIDATOR = jsonschema.Draft7Validator(REMEDIATION_REQUEST_SCHEMA)

with open(DECISION_RECEIPT_SCHEMA_PATH, "r", encoding="utf-8") as f:
    DECISION_RECEIPT_SCHEMA = json.load(f)
jsonschema.Draft7Validator.check_schema(DECISION_RECEIPT_SCHEMA)
_RECEIPT_VALIDATOR = jsonschema.Draft7Validator(DECISION_RECEIPT_SCHEMA)

with open(AUDIT_SCHEMA_PATH, "r", encoding="utf-8") as f:
    AUDIT_SCHEMA = json.load(f)
jsonschema.Draft7Validator.check_schema(AUDIT_SCHEMA)
_AUDIT_VALIDATOR = jsonschema.Draft7Validator(AUDIT_SCHEMA)


@dataclass(frozen=True)
class RuleResults:
    R1_allowlist: bool = False
    R2_capacity: bool = False
    R3_telemetry: bool = False
    R4_cooldown: bool = False
    R5_catalog: bool = False
    R6_audit: bool = False
    R7_authority: bool = False
    R8_idempotency: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class RemediationRequest:
    incident_id: str
    action_id: str
    target_task_arn: str

    @classmethod
    def from_dict(cls, data: Any) -> "RemediationRequest":
        if not isinstance(data, dict):
            raise RequestValidationError("Payload must be a valid JSON object.")

        # Strict JSON Schema validation (Draft-07)
        errors = list(_REQUEST_VALIDATOR.iter_errors(data))
        if errors:
            first_err = errors[0]
            err_path = ".".join(str(p) for p in first_err.path) if first_err.path else "root"
            raise RequestValidationError(
                f"Schema validation failed at '{err_path}': {first_err.message}",
                details={"errors": [e.message for e in errors]}
            )

        # Explicit defensive assertions against model-supplied parameter injection
        prohibited_injected_fields = [
            "healthy_count", "min_healthy_tasks", "is_authorized", "approved",
            "cooldown_override", "role", "assume_role", "shell", "force"
        ]
        for field_name in prohibited_injected_fields:
            if field_name in data:
                raise RequestValidationError(f"Prohibited model-supplied parameter detected: {field_name}")

        return cls(
            incident_id=data["incident_id"],
            action_id=data["action_id"],
            target_task_arn=data["target_task_arn"]
        )


@dataclass
class DecisionReceipt:
    incident_id: str
    action_id: str
    target_task_arn: str
    decision: str  # ALLOW, DENY, ERROR, UNKNOWN
    reason_code: str
    execution_status: str  # NOT_STARTED, SUBMITTED, VERIFIED, FAILED, UNKNOWN
    decision_id: str = field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:16]}")
    catalog_version: str = CATALOG_VERSION
    policy_version: str = POLICY_VERSION
    aws_request_id: Optional[str] = None
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rule_results: Dict[str, bool] = field(default_factory=lambda: RuleResults().to_dict())
    audit_persisted: bool = True
    audit_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "decision_id": self.decision_id,
            "incident_id": self.incident_id,
            "action_id": self.action_id,
            "target_task_arn": self.target_task_arn,
            "catalog_version": self.catalog_version,
            "policy_version": self.policy_version,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "execution_status": self.execution_status,
            "aws_request_id": self.aws_request_id,
            "recorded_at": self.recorded_at,
            "rule_results": self.rule_results,
            "audit_persisted": self.audit_persisted,
        }
        if self.audit_warning:
            data["audit_warning"] = self.audit_warning
        # Validate against authoritative decision receipt schema
        errors = list(_RECEIPT_VALIDATOR.iter_errors(data))
        if errors:
            raise ValueError(f"Receipt fails schema validation: {errors[0].message}")
        return data


@dataclass
class AuditRecord:
    event_type: str  # AUTHORIZATION_DECISION, MUTATION_EXECUTION, SYSTEM_REFUSAL, COOLDOWN_RESERVATION
    incident_id: str
    decision_id: str
    actor_type: str  # AGENT_GATEWAY, LAMBDA_BROKER, SYSTEM_WATCHDOG
    rule_results: Dict[str, bool]
    requested_action: str
    authorization_decision: str  # ALLOW, DENY, ERROR, UNKNOWN
    execution_status: str  # NOT_STARTED, SUBMITTED, VERIFIED, FAILED, UNKNOWN
    evidence_references: List[str]
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:16]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION
    previous_event_sha256: Optional[str] = None
    writer_role_arn: str = BROKER_ROLE_ARN

    def to_dict(self) -> Dict[str, Any]:
        # Compute deterministic SHA-256 integrity hash over canonical payload
        canonical_content = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "decision_id": self.decision_id,
            "actor_type": self.actor_type,
            "rule_results": self.rule_results,
            "requested_action": self.requested_action,
            "authorization_decision": self.authorization_decision,
            "execution_status": self.execution_status,
            "timestamp": self.timestamp,
            "evidence_references": self.evidence_references,
            "schema_version": self.schema_version,
            "previous_event_sha256": self.previous_event_sha256,
            "writer_role_arn": self.writer_role_arn
        }
        canonical_json = json.dumps(canonical_content, sort_keys=True, separators=(",", ":"))
        event_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        data = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "decision_id": self.decision_id,
            "actor_type": self.actor_type,
            "rule_results": self.rule_results,
            "requested_action": self.requested_action,
            "authorization_decision": self.authorization_decision,
            "execution_status": self.execution_status,
            "timestamp": self.timestamp,
            "evidence_references": self.evidence_references,
            "schema_version": self.schema_version,
            "integrity": {
                "event_sha256": event_sha256,
                "previous_event_sha256": self.previous_event_sha256,
                "writer_role_arn": self.writer_role_arn
            }
        }
        errors = list(_AUDIT_VALIDATOR.iter_errors(data))
        if errors:
            raise ValueError(f"Audit record fails schema validation: {errors[0].message}")
        return data
