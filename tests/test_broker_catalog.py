"""
BlastGate Broker Action Catalog Tests (Rules R1 & R5)
Verifies allowlist enforcement and runbook bindings.
"""

import pytest
from broker.catalog import get_default_catalog
from broker.errors import UnauthorizedActionError, TargetNotAllowlistedError


@pytest.fixture
def catalog():
    return get_default_catalog()


def test_catalog_loads_approved_action(catalog):
    action = catalog.get_action("REPLACE_UNHEALTHY_ECS_WORKER")
    assert action.action_id == "REPLACE_UNHEALTHY_ECS_WORKER"
    assert action.enabled is True
    assert action.aws_api == "ecs:StopTask"
    assert action.allowed_cluster == "blastgate-sandbox"
    assert action.allowed_service == "blastgate-workers"
    assert action.allowed_task_family == "blastgate-worker"
    assert action.cooldown_window_seconds == 600
    assert action.min_healthy_tasks == 4


@pytest.mark.parametrize("disallowed_action", [
    "iam:CreateUser",
    "iam:AttachRolePolicy",
    "iam:PassRole",
    "ecs:DeleteCluster",
    "ecs:UpdateService",
    "rds:DeleteDBInstance",
    "ec2:TerminateInstances",
    "shell:ExecuteScript",
    "UNKNOWN_ACTION",
])
def test_catalog_rejects_unregistered_actions(catalog, disallowed_action):
    with pytest.raises(UnauthorizedActionError) as exc:
        catalog.get_action(disallowed_action)
    assert "not an authorized BlastGate catalog action" in str(exc.value)


def test_validate_action_target_success(catalog):
    action = catalog.validate_action_target(
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        cluster="blastgate-sandbox",
        service="blastgate-workers",
        task_family="blastgate-worker",
    )
    assert action.action_id == "REPLACE_UNHEALTHY_ECS_WORKER"


def test_validate_action_target_rejects_wrong_cluster(catalog):
    with pytest.raises(TargetNotAllowlistedError) as exc:
        catalog.validate_action_target(
            action_id="REPLACE_UNHEALTHY_ECS_WORKER",
            cluster="production-cluster",
            service="blastgate-workers",
            task_family="blastgate-worker",
        )
    assert "Cluster 'production-cluster' is not authorized" in str(exc.value)


def test_validate_action_target_rejects_wrong_service(catalog):
    with pytest.raises(TargetNotAllowlistedError) as exc:
        catalog.validate_action_target(
            action_id="REPLACE_UNHEALTHY_ECS_WORKER",
            cluster="blastgate-sandbox",
            service="billing-service",
            task_family="blastgate-worker",
        )
    assert "Service 'billing-service' is not authorized" in str(exc.value)


def test_validate_action_target_rejects_wrong_task_family(catalog):
    with pytest.raises(TargetNotAllowlistedError) as exc:
        catalog.validate_action_target(
            action_id="REPLACE_UNHEALTHY_ECS_WORKER",
            cluster="blastgate-sandbox",
            service="blastgate-workers",
            task_family="unauthorized-task-family",
        )
    assert "Task family 'unauthorized-task-family' is not authorized" in str(exc.value)
