"""
BlastGate Incident Ingestion & Deduplication Tests (T4-013, T4-016)
Tests ALARM event creation, deduplication of active incidents, and OK resolution transition.
"""

import json
import time
import pytest
from incidents.repository import MockIncidentRepository
from incidents.deduplication import IncidentDeduplicator
from incidents.handler import lambda_handler


def test_alarm_transition_creates_incident():
    """T4-013: ALARM transition creates a new incident with status OPEN."""
    repo = MockIncidentRepository()
    dedup = IncidentDeduplicator(repository=repo)
    now = time.time()
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"

    incident = dedup.process_alarm_transition(
        alarm_name="blastgate-worker-stalled-alarm",
        new_state="ALARM",
        target_task_arn=task_arn,
        timestamp=now
    )

    assert incident.status == "OPEN"
    assert incident.alarm_name == "blastgate-worker-stalled-alarm"
    assert incident.target_task_arn == task_arn
    assert incident.incident_id.startswith("inc-")
    assert incident.created_timestamp == now

    # Verify saved in repository
    retrieved = repo.get_incident(incident.incident_id)
    assert retrieved is not None
    assert retrieved.incident_id == incident.incident_id


def test_alarm_deduplication_of_active_incident():
    """T4-016: Multiple ALARM events for the same alarm do not create duplicate incidents."""
    repo = MockIncidentRepository()
    dedup = IncidentDeduplicator(repository=repo)
    now = time.time()

    inc1 = dedup.process_alarm_transition(
        alarm_name="blastgate-worker-stalled-alarm",
        new_state="ALARM",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/task01",
        timestamp=now
    )

    # 30 seconds later, alarm fires again
    inc2 = dedup.process_alarm_transition(
        alarm_name="blastgate-worker-stalled-alarm",
        new_state="ALARM",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/task01",
        timestamp=now + 30.0
    )

    assert inc1.incident_id == inc2.incident_id, "Deduplicator must reuse active incident ID"
    assert inc2.updated_timestamp == now + 30.0

    # Ensure repository contains only 1 incident
    all_incidents = repo.list_incidents()
    assert len(all_incidents) == 1


def test_ok_transition_resolves_open_incident():
    """Transition to OK resolves active open incident."""
    repo = MockIncidentRepository()
    dedup = IncidentDeduplicator(repository=repo)
    now = time.time()

    open_inc = dedup.process_alarm_transition(
        alarm_name="blastgate-worker-stalled-alarm",
        new_state="ALARM",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/task01",
        timestamp=now
    )
    assert open_inc.status == "OPEN"

    resolved_inc = dedup.process_alarm_transition(
        alarm_name="blastgate-worker-stalled-alarm",
        new_state="OK",
        target_task_arn=None,
        timestamp=now + 60.0
    )

    assert resolved_inc.incident_id == open_inc.incident_id
    assert resolved_inc.status == "RESOLVED"
    assert resolved_inc.resolved_timestamp == now + 60.0

    # Ensure active incident lookup returns None
    assert repo.get_active_incident_by_alarm("blastgate-worker-stalled-alarm") is None


def test_lambda_handler_full_flow():
    """End-to-end incident ingestion handler processes EventBridge payload."""
    event = {
        "version": "0",
        "detail-type": "CloudWatch Alarm State Change",
        "source": "aws.cloudwatch",
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "alarmName": "blastgate-worker-stalled-alarm",
            "state": {"value": "ALARM", "timestamp": "2026-11-22T12:00:00.000+0000"},
        }
    }
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    assert response["processed"] is True
    assert "incident_id" in response


def test_lambda_handler_emits_incident_opened_event():
    """Incident ingestion emits BlastGate.IncidentOpened when new incident is created."""
    class MockEventsClient:
        def __init__(self):
            self.entries = []

        def put_events(self, Entries):
            self.entries.extend(Entries)
            return {"FailedEntryCount": 0, "Entries": [{"EventId": "evt-12345"}]}

    mock_events = MockEventsClient()
    event = {
        "version": "0",
        "detail-type": "CloudWatch Alarm State Change",
        "source": "aws.cloudwatch",
        "account": "123456789012",
        "region": "us-east-1",
        "detail": {
            "alarmName": "blastgate-worker-stalled-alarm",
            "state": {"value": "ALARM", "timestamp": "2026-11-22T12:00:00.000+0000"},
        }
    }
    response = lambda_handler(event, events_client=mock_events)
    assert response["statusCode"] == 200
    assert response["event_emitted"] is True
    assert len(mock_events.entries) == 1
    entry = mock_events.entries[0]
    assert entry["Source"] == "blastgate.incidents"
    assert entry["DetailType"] == "BlastGate.IncidentOpened"
    detail = json.loads(entry["Detail"])
    assert detail["incident_id"] == response["incident_id"]
    assert detail["status"] == "OPEN"

