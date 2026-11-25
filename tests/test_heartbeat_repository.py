"""
BlastGate Heartbeat Repository Tests (T4-001)
Tests MockHeartbeatRepository and DynamoDbHeartbeatRepository serialization and queries.
"""

import time
import pytest
from telemetry.models import WorkerHeartbeat
from telemetry.heartbeat_repository import MockHeartbeatRepository, DynamoDbHeartbeatRepository


@pytest.fixture
def sample_heartbeat():
    return WorkerHeartbeat(
        task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/11820b5c8c71152eb9613525778941e6",
        cluster_name="blastgate-sandbox",
        service_name="blastgate-workers",
        task_family="blastgate-worker",
        processing_state="HEALTHY",
        is_unhealthy=False,
        timestamp=time.time(),
        processing_age=1.5,
        processed_count=120,
        schema_version="1.0.0",
        details={"status": "nominal"}
    )


def test_mock_repository_save_and_retrieve(sample_heartbeat):
    """Save and retrieve a valid heartbeat record by task_arn."""
    repo = MockHeartbeatRepository()
    repo.save_heartbeat(sample_heartbeat)

    retrieved = repo.get_heartbeat(sample_heartbeat.task_arn)
    assert retrieved is not None
    assert retrieved.task_arn == sample_heartbeat.task_arn
    assert retrieved.processing_state == "HEALTHY"
    assert retrieved.is_unhealthy is False
    assert retrieved.processed_count == 120


def test_mock_repository_missing_arn():
    """Querying non-existent task_arn returns None."""
    repo = MockHeartbeatRepository()
    retrieved = repo.get_heartbeat("arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/nonexistent1234")
    assert retrieved is None


def test_mock_repository_overwrite(sample_heartbeat):
    """Saving updated heartbeat overwrites previous record for that task_arn."""
    repo = MockHeartbeatRepository()
    repo.save_heartbeat(sample_heartbeat)

    updated = WorkerHeartbeat(
        task_arn=sample_heartbeat.task_arn,
        cluster_name=sample_heartbeat.cluster_name,
        service_name=sample_heartbeat.service_name,
        task_family=sample_heartbeat.task_family,
        processing_state="STALLED",
        is_unhealthy=True,
        timestamp=time.time() + 10,
        processing_age=25.0,
        processed_count=120,
        schema_version="1.0.0",
        details={"reason": "Stall detected"}
    )
    repo.save_heartbeat(updated)

    retrieved = repo.get_heartbeat(sample_heartbeat.task_arn)
    assert retrieved.processing_state == "STALLED"
    assert retrieved.is_unhealthy is True


def test_dynamodb_repository_serialization(sample_heartbeat):
    """DynamoDbHeartbeatRepository formats and parses DynamoDB item accurately."""
    repo = DynamoDbHeartbeatRepository(client=None)
    item = repo._to_dynamo_item(sample_heartbeat)

    assert item["task_arn"]["S"] == sample_heartbeat.task_arn
    assert item["processing_state"]["S"] == "HEALTHY"
    assert item["is_unhealthy"]["BOOL"] is False
    assert item["processed_count"]["N"] == "120"

    reconstructed = repo._from_dynamo_item(item)
    assert reconstructed.task_arn == sample_heartbeat.task_arn
    assert reconstructed.processing_state == sample_heartbeat.processing_state
    assert reconstructed.is_unhealthy == sample_heartbeat.is_unhealthy
    assert reconstructed.processed_count == sample_heartbeat.processed_count
