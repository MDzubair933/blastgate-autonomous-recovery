"""
BlastGate Central Remediation Broker Lambda Handler
The sovereign orchestration endpoint for autonomous infrastructure recovery.
"""

import json
import os
import uuid
from typing import Dict, Any, Optional

from config import (
    DEFAULT_REGION,
    ALLOWED_CLUSTER,
    ALLOWED_SERVICE,
    STATE_TABLE_NAME,
    AUDIT_TABLE_NAME,
    HEARTBEAT_TABLE_NAME,
    CATALOG_VERSION,
    POLICY_VERSION,
)
from models import RemediationRequest, DecisionReceipt, RuleResults
from catalog import get_default_catalog
from inventory import (
    InventoryValidator,
    MockEcsInventoryProvider,
    MockHealthEvidenceProvider,
    Boto3EcsInventoryProvider,
    TelemetryHealthEvidenceAdapter,
)
from capacity import CapacityEngine
from budget import CooldownManager, MockStateStoreProvider, DynamoDbStateStoreProvider
from idempotency import IdempotencyManager, MockIdempotencyStore, DynamoDbIdempotencyStore
from executor import EcsMutationExecutor
from audit import AuditLogger, MockAuditStore, DynamoDbAuditStore
from recovery import RecoveryVerifier
from authorization import SovereignAuthorizer
from errors import BrokerError, RequestValidationError


def _is_live_aws_runtime() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))


def build_live_dependencies():
    """Constructs real AWS Boto3 providers for live Lambda runtime."""
    import boto3
    from telemetry.heartbeat_repository import DynamoDbHeartbeatRepository
    from telemetry.validator import TelemetryValidator

    ecs_client = boto3.client("ecs", region_name=DEFAULT_REGION)
    ddb_client = boto3.client("dynamodb", region_name=DEFAULT_REGION)

    inv_provider = Boto3EcsInventoryProvider(ecs_client=ecs_client)
    hb_repo = DynamoDbHeartbeatRepository(dynamodb_client=ddb_client, table_name=HEARTBEAT_TABLE_NAME)
    health_provider = TelemetryHealthEvidenceAdapter(TelemetryValidator(repository=hb_repo))
    state_store = DynamoDbStateStoreProvider(dynamodb_client=ddb_client, table_name=STATE_TABLE_NAME)
    idemp_store = DynamoDbIdempotencyStore(dynamodb_client=ddb_client, table_name=STATE_TABLE_NAME)
    audit_store = DynamoDbAuditStore(dynamodb_client=ddb_client, table_name=AUDIT_TABLE_NAME)

    authorizer = build_default_authorizer(
        inventory_provider=inv_provider,
        health_provider=health_provider,
        state_store=state_store,
        idempotency_store=idemp_store,
    )
    executor = EcsMutationExecutor(ecs_client=ecs_client)
    audit_logger = AuditLogger(store=audit_store)
    recovery_verifier = RecoveryVerifier(inventory_provider=inv_provider, health_provider=health_provider)
    return authorizer, executor, audit_logger, recovery_verifier


def build_default_authorizer(
    inventory_provider=None,
    health_provider=None,
    state_store=None,
    idempotency_store=None,
) -> SovereignAuthorizer:
    """Dependency injection factory for testing and production runtime."""
    catalog = get_default_catalog()
    inv_provider = inventory_provider or MockEcsInventoryProvider()
    hlth_provider = health_provider or MockHealthEvidenceProvider()
    st_store = state_store or MockStateStoreProvider()
    idemp_store = idempotency_store or MockIdempotencyStore()

    inventory_validator = InventoryValidator(
        inventory_provider=inv_provider,
        health_provider=hlth_provider,
    )
    capacity_engine = CapacityEngine()
    cooldown_manager = CooldownManager(state_provider=st_store)
    idempotency_mgr = IdempotencyManager(store=idemp_store)

    return SovereignAuthorizer(
        catalog=catalog,
        inventory_validator=inventory_validator,
        capacity_engine=capacity_engine,
        cooldown_manager=cooldown_manager,
        idempotency_manager=idempotency_mgr,
    )


def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    authorizer: Optional[SovereignAuthorizer] = None,
    executor: Optional[EcsMutationExecutor] = None,
    audit_logger: Optional[AuditLogger] = None,
    recovery_verifier: Optional[RecoveryVerifier] = None,
) -> Dict[str, Any]:
    """
    Main Sovereign Broker Lambda Handler.
    Orchestrates:
    1. Parse and validate proposal schema.
    2. Record initial REQUEST_RECEIVED audit event.
    3. Evaluate operational rules R1 through R8.
    4. If authorized, record BUDGET_RESERVED and execute ecs:StopTask.
    5. Record outcome in audit store and idempotency cache.
    6. Return authoritative decision receipt.
    """
    # 1. Dependency Resolution
    if _is_live_aws_runtime() and authorizer is None and executor is None and audit_logger is None:
        auth, exec_engine, auditor, verifier = build_live_dependencies()
    else:
        auth = authorizer or build_default_authorizer()
        exec_engine = executor or EcsMutationExecutor()
        auditor = audit_logger or AuditLogger(store=MockAuditStore())
        verifier = recovery_verifier or RecoveryVerifier()

    # 2. Extract raw proposal payload (handles direct invocation or Gateway wrapper)
    raw_payload = event
    if "body" in event and isinstance(event["body"], str):
        try:
            raw_payload = json.loads(event["body"])
        except Exception:
            raw_payload = event.get("body")
    elif "actionGroupInput" in event:  # AgentCore Gateway format
        raw_payload = event.get("actionGroupInput", {})

    incident_id = raw_payload.get("incident_id", f"inc-unknown-{uuid.uuid4().hex[:8]}") if isinstance(raw_payload, dict) else "inc-unknown"
    action_id = raw_payload.get("action_id", "UNKNOWN") if isinstance(raw_payload, dict) else "UNKNOWN"
    target_arn = raw_payload.get("target_task_arn", "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000000") if isinstance(raw_payload, dict) else "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000000"
    decision_id = f"dec-{uuid.uuid4().hex[:16]}"

    # Initial rule results tracker
    rule_results = RuleResults()

    # 3. Input Validation against Schema
    try:
        request = RemediationRequest.from_dict(raw_payload)
    except RequestValidationError as e:
        # Guarantee valid hex incident_id for receipt schema
        safe_incident_id = incident_id
        if not (isinstance(safe_incident_id, str) and safe_incident_id.startswith("inc-") and len(safe_incident_id) >= 12 and all(c in "0123456789abcdef" for c in safe_incident_id[4:])):
            safe_incident_id = f"inc-{uuid.uuid4().hex[:16]}"

        safe_target_arn = target_arn
        if not (isinstance(safe_target_arn, str) and safe_target_arn.startswith("arn:aws:ecs:") and len(safe_target_arn) >= 60):
            safe_target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000000"

        # Fail closed on schema violation
        receipt = DecisionReceipt(
            decision_id=decision_id,
            incident_id=safe_incident_id,
            action_id="REPLACE_UNHEALTHY_ECS_WORKER",
            target_task_arn=safe_target_arn,
            decision="DENY",
            reason_code=e.reason_code,
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
        )
        # Log refusal to audit store
        try:
            auditor.log_event(
                event_type="SYSTEM_REFUSAL",
                incident_id=receipt.incident_id,
                decision_id=receipt.decision_id,
                requested_action=action_id,
                authorization_decision="DENY",
                execution_status="NOT_STARTED",
                rule_results=rule_results.to_dict(),
                evidence_references=[f"ValidationError: {e.message}"],
            )
        except Exception:
            pass

        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }

    # 4. Record REQUEST_RECEIVED Audit Event
    try:
        auditor.log_event(
            event_type="AUTHORIZATION_DECISION",
            incident_id=request.incident_id,
            decision_id=decision_id,
            requested_action=request.action_id,
            authorization_decision="UNKNOWN",
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
            evidence_references=[f"target_arn: {request.target_task_arn}"],
        )
    except Exception as e:
        # Mandatory audit write failure (Rule R6 fail closed)
        receipt = DecisionReceipt(
            decision_id=decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision="DENY",
            reason_code="ERR_AUDIT_WRITE_FAILED",
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
        )
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }

    # 5. Evaluate Operational Rules R1 through R8
    try:
        authorization, receipt, evaluated_rules = auth.evaluate_proposal(request)
    except BrokerError as e:
        # Refusal by deterministic rule
        receipt = DecisionReceipt(
            decision_id=decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision=e.decision,
            reason_code=e.reason_code,
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
        )
        try:
            auditor.log_event(
                event_type="SYSTEM_REFUSAL",
                incident_id=request.incident_id,
                decision_id=decision_id,
                requested_action=request.action_id,
                authorization_decision=e.decision,
                execution_status="NOT_STARTED",
                rule_results=rule_results.to_dict(),
                evidence_references=[f"Refusal: {e.message}"],
            )
        except Exception:
            pass

        return {
            "statusCode": 403 if e.decision == "DENY" else 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }
    except Exception as e:
        # Unexpected internal error
        receipt = DecisionReceipt(
            decision_id=decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision="ERROR",
            reason_code="ERR_INTERNAL_EXCEPTION",
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
        )
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }

    # 6. Check if proposal was resolved from idempotency cache (already executed)
    if receipt.execution_status in ["SUBMITTED", "VERIFIED"]:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }

    # 7. Pre-execution Audit Event: BUDGET_RESERVED
    try:
        auditor.log_event(
            event_type="COOLDOWN_RESERVATION",
            incident_id=request.incident_id,
            decision_id=authorization.decision_id,
            requested_action=request.action_id,
            authorization_decision="ALLOW",
            execution_status="NOT_STARTED",
            rule_results=evaluated_rules.to_dict(),
            evidence_references=[f"reservation_id: {authorization.reservation_id}"],
        )
    except Exception:
        # Fail closed: If pre-execution audit write fails, do NOT execute mutation!
        receipt = DecisionReceipt(
            decision_id=authorization.decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision="DENY",
            reason_code="ERR_AUDIT_WRITE_FAILED",
            execution_status="NOT_STARTED",
            rule_results=evaluated_rules.to_dict(),
        )
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(receipt.to_dict())
        }

    # 8. Execute Single Approved Mutation (ecs:StopTask)
    exec_result = exec_engine.execute_approved_replacement(authorization)
    receipt.execution_status = exec_result.execution_status
    receipt.aws_request_id = exec_result.aws_request_id

    # 9. Optional Immediate Recovery Check
    if exec_result.execution_status == "SUBMITTED":
        rec_check = verifier.verify_recovery(
            cluster=ALLOWED_CLUSTER,
            service=ALLOWED_SERVICE,
            stopped_task_arn=authorization.target_task_arn,
            pre_mutation_task_arns=set(authorization.pre_mutation_task_arns) if authorization.pre_mutation_task_arns else None,
            mutation_time=authorization.authorized_at,
        )
        if rec_check.is_fully_verified:
            receipt.execution_status = "VERIFIED"

    # 10. Post-Execution Audit Record
    post_event_type = "MUTATION_EXECUTION"
    try:
        auditor.log_event(
            event_type=post_event_type,
            incident_id=request.incident_id,
            decision_id=authorization.decision_id,
            requested_action=request.action_id,
            authorization_decision="ALLOW",
            execution_status=receipt.execution_status,
            rule_results=evaluated_rules.to_dict(),
            evidence_references=[
                f"aws_request_id: {exec_result.aws_request_id}",
                f"execution_status: {receipt.execution_status}",
            ],
        )
        receipt.audit_persisted = True
    except Exception as audit_exc:
        # Audit failure after execution must NOT claim mutation did not occur!
        # Emit structured diagnostic error to stderr with non-sensitive identifiers
        receipt.audit_persisted = False
        receipt.audit_warning = "POST_EXECUTION_AUDIT_WRITE_FAILED"
        import sys
        print(
            json.dumps({
                "event": "POST_EXECUTION_AUDIT_FAILURE",
                "error_code": "POST_EXECUTION_AUDIT_WRITE_FAILED",
                "decision_id": authorization.decision_id,
                "incident_id": request.incident_id,
                "action_id": request.action_id,
                "execution_status": receipt.execution_status,
                "aws_request_id": exec_result.aws_request_id,
                "error_type": type(audit_exc).__name__,
                "error_message": str(audit_exc),
                "remediation_status": "MUTATION_SUCCEEDED_AUDIT_DEGRADED",
            }),
            file=sys.stderr
        )

    # 11. Finalize Idempotency Record
    try:
        auth.idempotency_manager.finalize(
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision_receipt=receipt.to_dict(),
        )
    except Exception:
        pass

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(receipt.to_dict())
    }
