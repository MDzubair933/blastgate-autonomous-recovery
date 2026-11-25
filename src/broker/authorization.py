"""
BlastGate Core Sovereign Authorization Engine
Coordinates deterministic evaluation of rules R1 through R8.
"""

from typing import Dict, Any, Tuple
import uuid

from config import (
    ALLOWED_CLUSTER,
    ALLOWED_SERVICE,
    ALLOWED_TASK_FAMILY,
    CATALOG_VERSION,
    POLICY_VERSION,
)
from models import RemediationRequest, RuleResults, DecisionReceipt
from catalog import ActionCatalog
from inventory import InventoryValidator
from capacity import CapacityEngine
from budget import CooldownManager, CooldownReservation
from idempotency import IdempotencyManager
from errors import (
    BrokerError,
    UnauthorizedActionError,
    TargetNotAllowlistedError,
    CapacityQuorumError,
    TargetNotUnhealthyError,
    StaleTelemetryError,
    CooldownActiveError,
    UnregisteredProcedureError,
)
from executor import BrokerAuthorization


class SovereignAuthorizer:
    """The central deterministic decision engine for BlastGate."""

    def __init__(
        self,
        catalog: ActionCatalog,
        inventory_validator: InventoryValidator,
        capacity_engine: CapacityEngine,
        cooldown_manager: CooldownManager,
        idempotency_manager: IdempotencyManager,
    ):
        self.catalog = catalog
        self.inventory_validator = inventory_validator
        self.capacity_engine = capacity_engine
        self.cooldown_manager = cooldown_manager
        self.idempotency_manager = idempotency_manager

    def evaluate_proposal(
        self,
        request: RemediationRequest,
    ) -> Tuple[BrokerAuthorization, DecisionReceipt, RuleResults]:
        """
        Evaluates an untrusted agent proposal against R1 through R8.
        Returns (BrokerAuthorization, DecisionReceipt, RuleResults) if approved.
        Raises specific BrokerError subclasses if rejected.
        """
        decision_id = f"dec-{uuid.uuid4().hex[:16]}"
        r1 = r2 = r3 = r4 = r5 = r6 = r7 = r8 = False

        # --- Rule R7: Identity & Authority Boundary ---
        # The proposal is from an untrusted model; authority comes solely from broker checks.
        r7 = True

        # --- Rule R1 & R5: Action Catalog & Infrastructure Allowlist ---
        action_def = self.catalog.get_action(request.action_id)
        if not action_def.enabled:
            raise UnauthorizedActionError(f"Action '{request.action_id}' is disabled.")
        r5 = True

        # Verify cluster, service, task family match sandbox configuration
        self.catalog.validate_action_target(
            action_id=request.action_id,
            cluster=ALLOWED_CLUSTER,
            service=ALLOWED_SERVICE,
            task_family=ALLOWED_TASK_FAMILY,
        )
        r1 = True

        # --- Rule R8: Request Idempotency Check ---
        cached_receipt = self.idempotency_manager.check_or_lock(
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
        )
        if cached_receipt:
            # Duplicate request completed previously
            r8 = True
            receipt = DecisionReceipt(
                incident_id=request.incident_id,
                action_id=request.action_id,
                target_task_arn=request.target_task_arn,
                decision=cached_receipt.get("decision", "ALLOW"),
                reason_code=cached_receipt.get("reason_code", "AUTH_APPROVED"),
                execution_status=cached_receipt.get("execution_status", "SUBMITTED"),
                decision_id=cached_receipt.get("decision_id", decision_id),
                aws_request_id=cached_receipt.get("aws_request_id"),
                rule_results=cached_receipt.get("rule_results", {}),
            )
            dummy_auth = BrokerAuthorization(
                decision_id=receipt.decision_id,
                incident_id=request.incident_id,
                action_id=request.action_id,
                target_task_arn=request.target_task_arn,
                cluster_name=ALLOWED_CLUSTER,
                reservation_id="cached",
                authorized_at=0.0,
            )
            return dummy_auth, receipt, RuleResults(**receipt.rule_results)
        r8 = True

        # --- Rule R3: Trusted ECS Inventory & Telemetry Freshness ---
        # 1. Verify task ownership & status in service inventory
        task_item = self.inventory_validator.validate_target(
            target_task_arn=request.target_task_arn,
            expected_cluster=ALLOWED_CLUSTER,
            expected_service=ALLOWED_SERVICE,
            expected_family=ALLOWED_TASK_FAMILY,
        )

        # 2. Verify application health telemetry (must be confirmed unhealthy and fresh)
        health_evidence = self.inventory_validator.verify_application_health(request.target_task_arn)
        r3 = True

        # --- Rule R2: Minimum Healthy Capacity Quorum ---
        # Fetch live desired count and unavailable tasks from trusted inventory
        service_state = self.inventory_validator.inventory_provider.get_service_state(
            ALLOWED_CLUSTER, ALLOWED_SERVICE
        )

        # 1. Missing tasks from desired count (unprovisioned tasks missing from desired capacity)
        actual_tracked_count = max(len(service_state.tasks), service_state.running_count)
        missing_tasks_count = max(0, service_state.desired_count - actual_tracked_count)

        # 2. Identify all tasks currently unavailable
        unavailable_tasks = set()
        for task_arn, task_item in service_state.tasks.items():
            # Check lifecycle status: must be RUNNING
            if task_item.last_status != "RUNNING":
                unavailable_tasks.add(task_arn)
                continue

            # Target task is evaluated separately for Rule R3, but must be counted in unavailable
            if task_arn == request.target_task_arn:
                unavailable_tasks.add(task_arn)
                continue

            # Sibling RUNNING tasks must have verified, fresh, healthy application telemetry
            if self.inventory_validator.health_provider:
                try:
                    sibling_health = self.inventory_validator.health_provider.get_task_health(task_arn)
                    if sibling_health.is_unhealthy:
                        unavailable_tasks.add(task_arn)
                except Exception:
                    # Fail closed: If sibling telemetry cannot be verified, is stale, or missing, treat as unavailable
                    unavailable_tasks.add(task_arn)

        # Ensure the proposed target task is always included in the unavailable set
        unavailable_tasks.add(request.target_task_arn)

        self.capacity_engine.evaluate_quorum(
            desired_capacity=service_state.desired_count,
            currently_unavailable_tasks=unavailable_tasks,
            target_task_arn=request.target_task_arn,
            missing_tasks_count=missing_tasks_count,
        )
        r2 = True

        # --- Rule R4: Global Atomic Cooldown Budget Reservation ---
        cooldown_res = self.cooldown_manager.reserve_budget(
            cluster_id=ALLOWED_CLUSTER,
            incident_id=request.incident_id,
        )
        r4 = True

        # Mandatory audit rule flag
        r6 = True

        rule_results = RuleResults(
            R1_allowlist=r1,
            R2_capacity=r2,
            R3_telemetry=r3,
            R4_cooldown=r4,
            R5_catalog=r5,
            R6_audit=r6,
            R7_authority=r7,
            R8_idempotency=r8,
        )

        authorization = BrokerAuthorization(
            decision_id=decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            cluster_name=ALLOWED_CLUSTER,
            reservation_id=cooldown_res.reservation_id,
            authorized_at=cooldown_res.reserved_at,
            pre_mutation_task_arns=tuple(service_state.tasks.keys()),
        )

        receipt = DecisionReceipt(
            decision_id=decision_id,
            incident_id=request.incident_id,
            action_id=request.action_id,
            target_task_arn=request.target_task_arn,
            decision="ALLOW",
            reason_code="AUTH_APPROVED",
            execution_status="NOT_STARTED",
            rule_results=rule_results.to_dict(),
        )

        return authorization, receipt, rule_results
