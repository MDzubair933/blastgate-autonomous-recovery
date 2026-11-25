"""
BlastGate AgentCore Local Orchestrator Simulator
Simulates the complete boundary chain:
  Incident Ingestion -> Diagnostics Tool -> Simulated Model Reasoning ->
  Gateway Cedar Policy Evaluation -> Lambda Remediation Broker -> Decision Receipt.

NOTE: This simulator evaluates deterministic fixtures and genuine backend logic.
It NEVER calls live Bedrock inference or live AWS mutation APIs.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from broker.handler import lambda_handler as broker_lambda_handler
from broker.inventory import (
    MockEcsInventoryProvider,
    MockHealthEvidenceProvider,
    ServiceInventoryState,
    TaskInventoryItem,
    TaskHealthEvidence,
)
from broker.budget import MockStateStoreProvider
from broker.idempotency import MockIdempotencyStore
from broker.executor import EcsMutationExecutor
from broker.audit import AuditLogger, MockAuditStore
from broker.handler import build_default_authorizer

from diagnostics.handler import lambda_handler as diagnostics_lambda_handler
from diagnostics.incident_reader import IncidentReader
from diagnostics.ecs_reader import EcsStateReader
from diagnostics.health_reader import HealthStateReader
from diagnostics.log_reader import LogReader
from diagnostics.response_builder import DiagnosticsResponseBuilder

from incidents.models import IncidentRecord
from incidents.repository import MockIncidentRepository
from telemetry.models import WorkerHeartbeat
from telemetry.heartbeat_repository import MockHeartbeatRepository
from telemetry.freshness import FreshnessEvaluator
from telemetry.validator import TelemetryValidator

from agentcore.policies.config import load_cedar_policy_text
from agentcore.policies.evaluator import (
    CedarPolicyEvaluator,
    TRUSTED_PRINCIPAL,
    TRUSTED_RESOURCE,
    APPROVED_REMEDIATION_ACTION_ID,
)


@dataclass
class SimulationResult:
    scenario_name: str
    incident_id: str
    diagnostics_response: Optional[Dict[str, Any]]
    cedar_decision: str  # PERMIT, DENY
    cedar_reason: str
    broker_receipt: Optional[Dict[str, Any]]
    broker_decision: str  # ALLOW, DENY, NOT_INVOKED
    broker_reason_code: Optional[str]
    is_mutation_authorized: bool
    is_live_aws_mutation: bool = False
    model_source: str = "SYNTHETIC_FIXTURE"
    cedar_evaluation_source: str = "LOCAL_CEDAR_SEMANTIC_EVALUATOR"
    traces: list = field(default_factory=list)


class AgentCoreLocalSimulator:
    """Deterministic local Simulator for the BlastGate AgentCore boundary."""

    ALLOWED_GATEWAY_TOOLS = [
        "get_incident_diagnostics",
        "propose_worker_replacement",
        "blastgate_gateway/get_incident_diagnostics",
        "blastgate_gateway/propose_worker_replacement",
    ]
    ALLOWLISTED_ACTION_ID = APPROVED_REMEDIATION_ACTION_ID

    def __init__(self, now: float = 1000.0):
        self.now = now
        self.cedar_evaluator = CedarPolicyEvaluator(
            cedar_policy_text=load_cedar_policy_text()
        )
        self._setup_mock_infrastructure()

    def _setup_mock_infrastructure(self):
        """Sets up in-memory mock repositories and broker authorizer."""
        self.inc_repo = MockIncidentRepository()
        self.hb_repo = MockHeartbeatRepository()

        # Seed nominal stalled worker
        stalled_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
        healthy_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002"
        stale_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000003"

        self.hb_repo.save_heartbeat(WorkerHeartbeat(
            task_arn=stalled_arn,
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state="STALLED",
            is_unhealthy=True,
            timestamp=self.now - 20.0,
            processing_age=40.0,
            processed_count=100,
            schema_version="1.0.0",
            details={"reason": "Simulated thread lockup"}
        ))

        self.hb_repo.save_heartbeat(WorkerHeartbeat(
            task_arn=healthy_arn,
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state="HEALTHY",
            is_unhealthy=False,
            timestamp=self.now - 5.0,
            processing_age=1.0,
            processed_count=200,
            schema_version="1.0.0",
            details={}
        ))

        self.hb_repo.save_heartbeat(WorkerHeartbeat(
            task_arn=stale_arn,
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            task_family="blastgate-worker",
            processing_state="STALLED",
            is_unhealthy=True,
            timestamp=self.now - 250.0,  # Stale (>120s)
            processing_age=300.0,
            processed_count=50,
            schema_version="1.0.0",
            details={"reason": "Old stall"}
        ))

        # ECS mock inventory
        tasks = {}
        for i, arn in enumerate([stalled_arn, healthy_arn, stale_arn], 1):
            tasks[arn] = TaskInventoryItem(
                task_arn=arn,
                cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
                task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
                task_family="blastgate-worker",
                last_status="RUNNING",
                desired_status="RUNNING",
            )
        for i in range(4, 7):
            arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
            tasks[arn] = TaskInventoryItem(
                task_arn=arn,
                cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
                task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
                task_family="blastgate-worker",
                last_status="RUNNING",
                desired_status="RUNNING",
            )

        service_state = ServiceInventoryState(
            cluster_name="blastgate-sandbox",
            service_name="blastgate-workers",
            status="ACTIVE",
            desired_count=6,
            running_count=6,
            pending_count=0,
            deployments=[{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
            tasks=tasks,
        )

        health_map = {
            stalled_arn: TaskHealthEvidence(task_arn=stalled_arn, is_unhealthy=True, evidence_timestamp=self.now - 20.0, evidence_source="telemetry"),
            healthy_arn: TaskHealthEvidence(task_arn=healthy_arn, is_unhealthy=False, evidence_timestamp=self.now - 5.0, evidence_source="telemetry"),
            stale_arn: TaskHealthEvidence(task_arn=stale_arn, is_unhealthy=False, evidence_timestamp=self.now - 5.0, evidence_source="telemetry"),
        }
        for i in range(4, 7):
            arn = f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{i:032x}"
            health_map[arn] = TaskHealthEvidence(task_arn=arn, is_unhealthy=False, evidence_timestamp=self.now - 5.0, evidence_source="telemetry")

        self.inv_provider = MockEcsInventoryProvider(service_state)
        self.health_provider = MockHealthEvidenceProvider(health_map)
        self.state_store = MockStateStoreProvider()
        self.idemp_store = MockIdempotencyStore()
        self.audit_store = MockAuditStore()
        self.audit_logger = AuditLogger(store=self.audit_store)

        self.authorizer = build_default_authorizer(
            inventory_provider=self.inv_provider,
            health_provider=self.health_provider,
            state_store=self.state_store,
            idempotency_store=self.idemp_store,
        )
        self.authorizer.cooldown_manager.current_time_fn = lambda: self.now
        self.authorizer.inventory_validator.current_time_fn = lambda: self.now

        # Mutation executor mock
        class MockEcsClient:
            def stop_task(self, **kwargs):
                return {
                    "ResponseMetadata": {"RequestId": "req-simulated-stop-task-1"},
                    "task": {"desiredStatus": "STOPPED"}
                }

        self.executor = EcsMutationExecutor(ecs_client=MockEcsClient())

    def evaluate_cedar_policy(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        principal: str = TRUSTED_PRINCIPAL,
        resource: str = TRUSTED_RESOURCE,
    ) -> tuple[str, str]:
        """
        Evaluates Gateway Cedar policy using the CedarPolicyEvaluator.
        Enforces default-deny, principal isolation, resource scoping, and context invariants.
        """
        res = self.cedar_evaluator.evaluate(
            principal=principal,
            action=tool_name,
            resource=resource,
            context=parameters,
        )
        return res.decision, res.reason

    def run_simulation(self, scenario_name: str, scenario_data: Dict[str, Any]) -> SimulationResult:
        """Executes full orchestrated simulation run for a scenario."""
        traces = [
            f"[SIMULATION - MOCK] Starting scenario: {scenario_name}",
            "[SIMULATION - MOCK] Zero live AWS mutations performed (in-memory mock boundary)."
        ]
        incident_id = scenario_data.get("incident_id", "inc-unknown")

        # 1. Register incident in repository
        raw_logs = scenario_data.get("raw_logs", ["Nominal worker execution log."])
        incident_rec = IncidentRecord(
            incident_id=incident_id,
            alarm_name=scenario_data.get("alarm_name", "blastgate-worker-stalled-alarm"),
            status=scenario_data.get("status", "OPEN"),
            target_task_arn=scenario_data.get("target_task_arn"),
            created_at=self.now - 60.0,
            updated_at=self.now,
        )
        self.inc_repo.save_incident(incident_rec)
        traces.append(f"[SIMULATION - MOCK] Registered incident {incident_id}")

        # 2. Invoke Diagnostics Tool
        diag_cedar_decision, diag_cedar_reason = self.evaluate_cedar_policy("get_incident_diagnostics", {"incident_id": incident_id})
        traces.append(f"[SIMULATION - MOCK] Cedar policy for diagnostics: {diag_cedar_decision} ({diag_cedar_reason})")

        diag_resp = None
        if diag_cedar_decision == "PERMIT":
            freshness = FreshnessEvaluator(current_time_fn=lambda: self.now)
            val = TelemetryValidator(repository=self.hb_repo, freshness_evaluator=freshness)
            diag_resp = diagnostics_lambda_handler(
                event={"incident_id": incident_id},
                incident_reader=IncidentReader(repository=self.inc_repo),
                ecs_reader=EcsStateReader(inventory_provider=self.inv_provider),
                health_reader=HealthStateReader(telemetry_validator=val),
                log_reader=LogReader(),
                response_builder=DiagnosticsResponseBuilder(),
            )
            traces.append(f"[SIMULATION - MOCK] Diagnostics returned statusCode={diag_resp.get('statusCode')}")

        # 3. Model Proposal Formulated
        proposal = scenario_data.get("proposal")
        if not proposal:
            traces.append("[SIMULATION - MOCK] Model refused to formulate a proposal (nominal behavior).")
            return SimulationResult(
                scenario_name=scenario_name,
                incident_id=incident_id,
                diagnostics_response=diag_resp,
                cedar_decision="NOT_APPLICABLE",
                cedar_reason="No proposal submitted",
                broker_receipt=None,
                broker_decision="NOT_INVOKED",
                broker_reason_code=None,
                is_mutation_authorized=False,
                is_live_aws_mutation=False,
                model_source="SYNTHETIC_FIXTURE",
                cedar_evaluation_source="LOCAL_CEDAR_SEMANTIC_EVALUATOR",
                traces=traces,
            )

        # 4. Gateway Cedar Policy Evaluation on Proposal Tool
        action_name = "propose_worker_replacement"
        cedar_decision, cedar_reason = self.evaluate_cedar_policy(action_name, proposal)
        traces.append(f"[SIMULATION - MOCK] Cedar policy for proposal: {cedar_decision} ({cedar_reason})")

        if cedar_decision != "PERMIT":
            traces.append("[SIMULATION - MOCK] Gateway blocked proposal at Cedar policy boundary.")
            return SimulationResult(
                scenario_name=scenario_name,
                incident_id=incident_id,
                diagnostics_response=diag_resp,
                cedar_decision=cedar_decision,
                cedar_reason=cedar_reason,
                broker_receipt=None,
                broker_decision="DENY",
                broker_reason_code="ERR_CEDAR_POLICY_DENY",
                is_mutation_authorized=False,
                is_live_aws_mutation=False,
                model_source="SYNTHETIC_FIXTURE",
                cedar_evaluation_source="LOCAL_CEDAR_SEMANTIC_EVALUATOR",
                traces=traces,
            )

        # 5. Dispatch to Sovereign Remediation Broker
        traces.append("[SIMULATION - MOCK] Dispatching proposal to Sovereign Remediation Broker (mock in-memory)...")
        broker_resp = broker_lambda_handler(
            event=proposal,
            authorizer=self.authorizer,
            executor=self.executor,
            audit_logger=self.audit_logger,
        )

        receipt = json.loads(broker_resp.get("body", "{}"))
        decision = receipt.get("decision", "DENY")
        reason_code = receipt.get("reason_code")
        is_authorized = (decision == "ALLOW")
        traces.append(f"[SIMULATION - MOCK] Broker responded: decision={decision}, reason_code={reason_code}")

        return SimulationResult(
            scenario_name=scenario_name,
            incident_id=incident_id,
            diagnostics_response=diag_resp,
            cedar_decision=cedar_decision,
            cedar_reason=cedar_reason,
            broker_receipt=receipt,
            broker_decision=decision,
            broker_reason_code=reason_code,
            is_mutation_authorized=is_authorized,
            is_live_aws_mutation=False,
            model_source="SYNTHETIC_FIXTURE",
            cedar_evaluation_source="LOCAL_CEDAR_SEMANTIC_EVALUATOR",
            traces=traces,
        )
