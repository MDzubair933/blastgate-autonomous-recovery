"""
BlastGate Read-Only Diagnostics Microservice Tests (T4-017, T4-018)
Tests get_incident_diagnostics, response schema, RB-ECS-001 runbook linkage, and 404 for unknown incidents.
"""

import time
import pytest
from incidents.models import IncidentRecord
from incidents.repository import MockIncidentRepository
from telemetry.models import WorkerHeartbeat
from telemetry.heartbeat_repository import MockHeartbeatRepository
from diagnostics.incident_reader import IncidentReader
from diagnostics.ecs_reader import EcsStateReader
from diagnostics.health_reader import HealthStateReader
from diagnostics.log_reader import LogReader
from diagnostics.response_builder import DiagnosticsResponseBuilder
from diagnostics.handler import lambda_handler


@pytest.fixture
def diagnostics_setup():
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    now = time.time()

    # Incident setup
    inc_repo = MockIncidentRepository()
    incident = IncidentRecord(
        incident_id="inc-test12345678",
        alarm_name="blastgate-worker-stalled-alarm",
        status="OPEN",
        target_task_arn=task_arn,
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        created_timestamp=now - 30.0,
        updated_timestamp=now,
    )
    inc_repo.save_incident(incident)

    # Health telemetry setup
    hb_repo = MockHeartbeatRepository()
    hb_repo.save_heartbeat(WorkerHeartbeat(
        task_arn=task_arn,
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        task_family="blastgate-worker",
        processing_state="STALLED",
        is_unhealthy=True,
        timestamp=now - 10.0,
        processing_age=35.0,
        processed_count=100,
        schema_version="1.0.0",
        details={"reason": "Simulated memory leak / deadlock"}
    ))

    inc_reader = IncidentReader(repository=inc_repo)
    health_reader = HealthStateReader(repository=hb_repo)
    ecs_reader = EcsStateReader()
    log_reader = LogReader()
    response_builder = DiagnosticsResponseBuilder()

    return {
        "incident_id": incident.incident_id,
        "task_arn": task_arn,
        "inc_reader": inc_reader,
        "health_reader": health_reader,
        "ecs_reader": ecs_reader,
        "log_reader": log_reader,
        "response_builder": response_builder,
    }


def test_get_incident_diagnostics_nominal(diagnostics_setup):
    """T4-017: Retrieves structured diagnostic package including RB-ECS-001 runbook and authority disclaimer."""
    event = {"incident_id": diagnostics_setup["incident_id"]}
    response = lambda_handler(
        event=event,
        incident_reader=diagnostics_setup["inc_reader"],
        ecs_reader=diagnostics_setup["ecs_reader"],
        health_reader=diagnostics_setup["health_reader"],
        log_reader=diagnostics_setup["log_reader"],
        response_builder=diagnostics_setup["response_builder"],
    )

    assert response["statusCode"] == 200
    diag = response["diagnostics"]

    assert diag["incident_id"] == diagnostics_setup["incident_id"]
    assert diag["target_task_arn"] == diagnostics_setup["task_arn"]
    assert diag["health_evidence"]["processing_state"] == "STALLED"
    assert diag["health_evidence"]["is_valid"] is True

    # Suggested action
    action = diag["suggested_action"]
    assert action is not None
    assert action["action_id"] == "REPLACE_UNHEALTHY_ECS_WORKER"
    assert action["runbook_id"] == "RB-ECS-001"

    # Authority notice
    assert "SUGGESTIONS ONLY" in diag["authority_notice"]


def test_get_incident_diagnostics_unknown_404(diagnostics_setup):
    """T4-018: Unknown incident ID returns HTTP 404."""
    event = {"incident_id": "inc-nonexistent99999"}
    response = lambda_handler(
        event=event,
        incident_reader=diagnostics_setup["inc_reader"],
        ecs_reader=diagnostics_setup["ecs_reader"],
        health_reader=diagnostics_setup["health_reader"],
        log_reader=diagnostics_setup["log_reader"],
        response_builder=diagnostics_setup["response_builder"],
    )

    assert response["statusCode"] == 404
    assert "not found" in response["error"].lower()


def test_get_incident_diagnostics_missing_param():
    """Missing incident_id returns HTTP 400."""
    response = lambda_handler({})
    assert response["statusCode"] == 400
