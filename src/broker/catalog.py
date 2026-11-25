"""
BlastGate Action Catalog Loader & Validator (Rules R1 & R5)
Guarantees strictly allowlisted operations and runbook binding.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import jsonschema

from config import (
    ACTION_CATALOG_PATH,
    ACTION_CATALOG_SCHEMA_PATH,
    ALLOWED_CLUSTER,
    ALLOWED_SERVICE,
    ALLOWED_TASK_FAMILY,
)
from errors import UnauthorizedActionError, UnregisteredProcedureError, TargetNotAllowlistedError


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    runbook_id: str
    enabled: bool
    environment: str
    aws_api: str
    allowed_cluster: str
    allowed_service: str
    allowed_task_family: str
    max_tasks_per_operation: int
    max_authorized_replacements: int
    cooldown_window_seconds: int
    reference_desired_count: int
    min_healthy_tasks: int
    max_projected_unavailable_percent: float
    requires_verified_unhealthy_state: bool
    requires_recent_telemetry: bool
    requires_stable_deployment: bool
    requires_recovery_verification: bool
    prohibited_environments: List[str] = field(default_factory=list)


class ActionCatalog:
    """Authoritative singleton loader for the BlastGate Action Catalog."""

    def __init__(self, catalog_path: Optional[str] = None):
        path = catalog_path or ACTION_CATALOG_PATH
        with open(ACTION_CATALOG_SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema = json.load(f)
        jsonschema.Draft7Validator.check_schema(self.schema)
        self.validator = jsonschema.Draft7Validator(self.schema)

        with open(path, "r", encoding="utf-8") as f:
            self.raw_catalog = json.load(f)

        # Validate catalog file against its own schema
        errors = list(self.validator.iter_errors(self.raw_catalog))
        if errors:
            raise ValueError(f"Action catalog file corrupted or invalid: {errors[0].message}")

        self.actions: Dict[str, ActionDefinition] = {}
        for action_data in self.raw_catalog.get("actions", []):
            action_def = ActionDefinition(**action_data)
            self.actions[action_def.action_id] = action_def

        # Safety Invariant: Exactly one approved action allowed in sandbox
        if "REPLACE_UNHEALTHY_ECS_WORKER" not in self.actions:
            raise ValueError("Mandatory action 'REPLACE_UNHEALTHY_ECS_WORKER' missing from catalog!")

    def get_action(self, action_id: str) -> ActionDefinition:
        """Retrieves and verifies an authorized action definition."""
        if action_id not in self.actions:
            raise UnauthorizedActionError(
                f"Action '{action_id}' is not an authorized BlastGate catalog action."
            )
        action = self.actions[action_id]
        if not action.enabled:
            raise UnauthorizedActionError(f"Action '{action_id}' is currently disabled in catalog.")
        return action

    def validate_action_target(self, action_id: str, cluster: str, service: str, task_family: str) -> ActionDefinition:
        """Validates that the requested target coordinates strictly match catalog perimeter."""
        action = self.get_action(action_id)

        if cluster != action.allowed_cluster or cluster != ALLOWED_CLUSTER:
            raise TargetNotAllowlistedError(
                f"Cluster '{cluster}' is not authorized. Must be '{action.allowed_cluster}'."
            )
        if service != action.allowed_service or service != ALLOWED_SERVICE:
            raise TargetNotAllowlistedError(
                f"Service '{service}' is not authorized. Must be '{action.allowed_service}'."
            )
        if task_family != action.allowed_task_family or task_family != ALLOWED_TASK_FAMILY:
            raise TargetNotAllowlistedError(
                f"Task family '{task_family}' is not authorized. Must be '{action.allowed_task_family}'."
            )

        return action


# Module-level default catalog instance
_CATALOG_INSTANCE: Optional[ActionCatalog] = None


def get_default_catalog() -> ActionCatalog:
    global _CATALOG_INSTANCE
    if _CATALOG_INSTANCE is None:
        _CATALOG_INSTANCE = ActionCatalog()
    return _CATALOG_INSTANCE
