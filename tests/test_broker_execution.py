"""
BlastGate Approved Mutation Executor Tests
Verifies scoped ecs:StopTask execution, authorization validation, and error classification.
"""

from unittest.mock import MagicMock
import pytest
from broker.executor import EcsMutationExecutor, BrokerAuthorization
from broker.errors import TargetNotAllowlistedError, UnauthorizedActionError


@pytest.fixture
def valid_authorization():
    return BrokerAuthorization(
        decision_id="dec-ef797c8118f02dfb",
        incident_id="inc-ef797c8118f02dfb",
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
        cluster_name="blastgate-sandbox",
        reservation_id="res-12345678",
        authorized_at=1000.0,
    )


def test_executor_success(valid_authorization):
    mock_ecs = MagicMock()
    mock_ecs.stop_task.return_value = {
        "ResponseMetadata": {"RequestId": "aws-req-999"},
        "task": {"desiredStatus": "STOPPED"}
    }

    executor = EcsMutationExecutor(ecs_client=mock_ecs)
    res = executor.execute_approved_replacement(valid_authorization)

    assert res.execution_status == "SUBMITTED"
    assert res.aws_request_id == "aws-req-999"
    mock_ecs.stop_task.assert_called_once_with(
        cluster="blastgate-sandbox",
        task=valid_authorization.target_task_arn,
        reason="BlastGate authorized remediation for incident inc-ef797c8118f02dfb",
    )


def test_executor_rejects_unauthorized_cluster():
    auth = BrokerAuthorization(
        decision_id="dec-1",
        incident_id="inc-1",
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
        cluster_name="production-cluster",  # WRONG CLUSTER
        reservation_id="res-1",
        authorized_at=1000.0,
    )
    executor = EcsMutationExecutor(ecs_client=MagicMock())
    with pytest.raises(TargetNotAllowlistedError):
        executor.execute_approved_replacement(auth)


def test_executor_handles_network_timeout():
    mock_ecs = MagicMock()
    mock_ecs.stop_task.side_effect = Exception("ConnectTimeoutError: Connection timed out")

    executor = EcsMutationExecutor(ecs_client=mock_ecs)
    auth = BrokerAuthorization(
        decision_id="dec-1",
        incident_id="inc-1",
        action_id="REPLACE_UNHEALTHY_ECS_WORKER",
        target_task_arn="arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/cc75443d8979fe5cdbdf2de55b822ec8",
        cluster_name="blastgate-sandbox",
        reservation_id="res-1",
        authorized_at=1000.0,
    )
    res = executor.execute_approved_replacement(auth)
    assert res.execution_status == "UNKNOWN"
    assert res.details["state"] == "NETWORK_TIMEOUT"
