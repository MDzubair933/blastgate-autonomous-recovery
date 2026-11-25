"""
BlastGate Trusted ECS Inventory & Telemetry Validator (Rules R1 & R3)
Retrieves live infrastructure truth and verifies application health evidence.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from config import (
    DEFAULT_REGION,
    DEFAULT_ACCOUNT_ID,
    ALLOWED_CLUSTER,
    ALLOWED_SERVICE,
    ALLOWED_TASK_FAMILY,
    TELEMETRY_FRESHNESS_SECONDS,
)
from errors import (
    TargetNotAllowlistedError,
    TargetNotUnhealthyError,
    StaleTelemetryError,
    InternalBrokerError,
)


@dataclass
class TaskInventoryItem:
    task_arn: str
    cluster_arn: str
    task_definition_arn: str
    task_family: str
    last_status: str  # RUNNING, PENDING, STOPPED
    desired_status: str
    containers: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[float] = None
    group: Optional[str] = None


@dataclass
class ServiceInventoryState:
    cluster_name: str
    service_name: str
    status: str  # ACTIVE, DRAINING, INACTIVE
    desired_count: int
    running_count: int
    pending_count: int = 0
    deployments: List[Dict[str, Any]] = field(default_factory=list)
    tasks: Dict[str, TaskInventoryItem] = field(default_factory=dict)


@dataclass
class TaskHealthEvidence:
    task_arn: str
    is_unhealthy: bool
    evidence_timestamp: float  # epoch seconds
    evidence_source: str  # container_health_check, cloudwatch_metric, heartbeat
    details: Dict[str, Any] = field(default_factory=dict)


class EcsInventoryProvider(ABC):
    """Abstract interface for querying trusted live ECS cluster and task inventory."""

    @abstractmethod
    def get_service_state(self, cluster: str, service: str) -> ServiceInventoryState:
        pass

    @abstractmethod
    def get_task_details(self, cluster: str, task_arn: str) -> Optional[TaskInventoryItem]:
        pass


class HealthEvidenceProvider(ABC):
    """Abstract interface for retrieving empirical application health evidence."""

    @abstractmethod
    def get_task_health(self, task_arn: str) -> TaskHealthEvidence:
        pass


class TelemetryHealthEvidenceAdapter(HealthEvidenceProvider):
    """Adapts telemetry TelemetryValidator to broker HealthEvidenceProvider interface."""

    def __init__(self, telemetry_validator):
        self.validator = telemetry_validator

    def get_task_health(self, task_arn: str) -> TaskHealthEvidence:
        evidence = self.validator.get_validated_evidence(task_arn)
        if not evidence.get("is_valid_evidence"):
            reason = evidence.get("reason", "TELEMETRY_INVALID")
            if reason == "STALE":
                raise StaleTelemetryError(evidence.get("error", "Stale telemetry"))
            raise StaleTelemetryError(f"Invalid health telemetry: {evidence.get('error', reason)}")

        return TaskHealthEvidence(
            task_arn=task_arn,
            is_unhealthy=evidence["is_unhealthy"],
            evidence_timestamp=evidence["timestamp"],
            evidence_source="heartbeat_validator",
            details=evidence.get("details", {}),
        )


class MockEcsInventoryProvider(EcsInventoryProvider):
    """Deterministic in-memory ECS inventory for testing and local simulation."""

    def __init__(self, service_state: Optional[ServiceInventoryState] = None):
        self.service_state = service_state

    def get_service_state(self, cluster: str, service: str) -> ServiceInventoryState:
        if not self.service_state:
            raise InternalBrokerError("Mock ECS inventory has no configured service state.")
        return self.service_state

    def get_task_details(self, cluster: str, task_arn: str) -> Optional[TaskInventoryItem]:
        if not self.service_state:
            return None
        return self.service_state.tasks.get(task_arn)


class Boto3EcsInventoryProvider(EcsInventoryProvider):
    """Live AWS ECS inventory provider querying ECS DescribeServices/ListTasks/DescribeTasks."""

    def __init__(self, ecs_client):
        self.ecs = ecs_client

    @staticmethod
    def _parse_task(raw_task: Dict[str, Any]) -> TaskInventoryItem:
        td_arn = raw_task.get("taskDefinitionArn", "")
        # format: arn:aws:ecs:region:acct:task-definition/<family>:<revision>
        td_part = td_arn.split("/")[-1] if "/" in td_arn else td_arn
        task_family = td_part.split(":")[0] if ":" in td_part else td_part
        started_dt = raw_task.get("startedAt")
        started_ts = started_dt.timestamp() if hasattr(started_dt, "timestamp") else None
        return TaskInventoryItem(
            task_arn=raw_task.get("taskArn", ""),
            cluster_arn=raw_task.get("clusterArn", ""),
            task_definition_arn=td_arn,
            task_family=task_family,
            last_status=raw_task.get("lastStatus", "UNKNOWN"),
            desired_status=raw_task.get("desiredStatus", "UNKNOWN"),
            containers=raw_task.get("containers", []),
            started_at=started_ts,
            group=raw_task.get("group"),
        )

    def get_service_state(self, cluster: str, service: str) -> ServiceInventoryState:
        svc_resp = self.ecs.describe_services(cluster=cluster, services=[service])
        services = svc_resp.get("services", [])
        if not services:
            raise TargetNotAllowlistedError(f"ECS service '{service}' not found in cluster '{cluster}'.")

        svc = services[0]
        tasks_map: Dict[str, TaskInventoryItem] = {}

        # List running tasks (and handle pagination up to 100 sandbox tasks)
        list_resp = self.ecs.list_tasks(cluster=cluster, serviceName=service, desiredStatus="RUNNING")
        task_arns = list_resp.get("taskArns", [])
        if task_arns:
            desc_resp = self.ecs.describe_tasks(cluster=cluster, tasks=task_arns[:100])
            for raw_t in desc_resp.get("tasks", []):
                item = self._parse_task(raw_t)
                tasks_map[item.task_arn] = item

        return ServiceInventoryState(
            cluster_name=cluster,
            service_name=service,
            status=svc.get("status", "UNKNOWN"),
            desired_count=svc.get("desiredCount", 0),
            running_count=svc.get("runningCount", 0),
            pending_count=svc.get("pendingCount", 0),
            deployments=svc.get("deployments", []),
            tasks=tasks_map,
        )

    def get_task_details(self, cluster: str, task_arn: str) -> Optional[TaskInventoryItem]:
        resp = self.ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
        tasks = resp.get("tasks", [])
        if not tasks:
            return None
        return self._parse_task(tasks[0])


class MockHealthEvidenceProvider(HealthEvidenceProvider):
    """Deterministic health evidence provider for testing."""

    def __init__(self, health_map: Optional[Dict[str, TaskHealthEvidence]] = None):
        self.health_map = health_map or {}

    def set_health(self, task_arn: str, evidence: TaskHealthEvidence):
        self.health_map[task_arn] = evidence

    def get_task_health(self, task_arn: str) -> TaskHealthEvidence:
        if task_arn not in self.health_map:
            # Step 3 limitation: Fail closed when no health evidence is available
            raise StaleTelemetryError(f"No health telemetry recorded for target worker: {task_arn}")
        return self.health_map[task_arn]


class InventoryValidator:
    """Validates target worker membership and application health against trusted sources."""

    def __init__(
        self,
        inventory_provider: EcsInventoryProvider,
        health_provider: HealthEvidenceProvider,
        telemetry_freshness_seconds: int = TELEMETRY_FRESHNESS_SECONDS,
        current_time_fn=None,
    ):
        self.inventory_provider = inventory_provider
        self.health_provider = health_provider
        self.telemetry_freshness_seconds = telemetry_freshness_seconds
        self.current_time_fn = current_time_fn or time.time

    def validate_target(
        self,
        target_task_arn: str,
        expected_cluster: str = ALLOWED_CLUSTER,
        expected_service: str = ALLOWED_SERVICE,
        expected_family: str = ALLOWED_TASK_FAMILY,
    ) -> TaskInventoryItem:
        """
        Validates target task ownership, family, status, and active deployment state.
        Fails closed on any inconsistency.
        """
        # 1. Fetch live service inventory
        service_state = self.inventory_provider.get_service_state(expected_cluster, expected_service)
        if service_state.status != "ACTIVE":
            raise TargetNotAllowlistedError(f"Target service '{expected_service}' is not in ACTIVE state.")

        # 2. Check for active rollout / deployment in progress (Rule R3 safety)
        if len(service_state.deployments) > 1:
            active_rollouts = [
                d for d in service_state.deployments
                if d.get("rolloutState") in ["IN_PROGRESS", "PRE_ROLLOUT"]
            ]
            if active_rollouts:
                raise TargetNotAllowlistedError("Service has an active rolling deployment in progress. Remediations paused.")

        # 3. Verify task exists in and belongs to authorized ECS service task inventory (Rule R1)
        if target_task_arn not in service_state.tasks:
            raise TargetNotAllowlistedError(
                f"Target task '{target_task_arn}' does not belong to authorized service '{expected_service}' (does not exist in cluster/service inventory)."
            )

        task_item = service_state.tasks[target_task_arn]
        if not task_item:
            task_item = self.inventory_provider.get_task_details(expected_cluster, target_task_arn)
        if not task_item:
            raise TargetNotAllowlistedError(f"Target task '{target_task_arn}' does not exist in cluster/service inventory.")

        # 4. Verify task group belongs to expected service if group is specified
        expected_group = f"service:{expected_service}"
        if task_item.group and task_item.group != expected_group:
            raise TargetNotAllowlistedError(
                f"Target task group '{task_item.group}' does not match authorized service group '{expected_group}'."
            )

        # 5. Verify task family
        if task_item.task_family != expected_family:
            raise TargetNotAllowlistedError(
                f"Target task family '{task_item.task_family}' does not match approved '{expected_family}'."
            )

        # 6. Verify task is in RUNNING status (cannot remediate already STOPPED tasks)
        if task_item.last_status != "RUNNING":
            raise TargetNotAllowlistedError(
                f"Target task status is '{task_item.last_status}', expected 'RUNNING'."
            )

        return task_item

    def verify_application_health(self, target_task_arn: str) -> TaskHealthEvidence:
        """
        Verifies that the target worker is empirically confirmed UNHEALTHY,
        and that the telemetry evidence is fresh (within 120s).
        """
        now = self.current_time_fn()
        evidence = self.health_provider.get_task_health(target_task_arn)

        # Telemetry freshness check (Rule R3)
        age = now - evidence.evidence_timestamp
        if age > self.telemetry_freshness_seconds:
            raise StaleTelemetryError(
                f"Health telemetry for '{target_task_arn}' is stale ({age:.1f}s old > {self.telemetry_freshness_seconds}s limit)."
            )
        if age < -5:  # Clocks skewed into the future
            raise StaleTelemetryError("Health telemetry timestamp is in the future (clock skew detected).")

        # Target must be confirmed unhealthy (Rule R3)
        if not evidence.is_unhealthy:
            raise TargetNotUnhealthyError(
                f"Target worker '{target_task_arn}' reports HEALTHY application state. Replacement denied."
            )

        return evidence
