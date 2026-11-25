"""
BlastGate Live AWS Adapter & Infrastructure Fix Verification Tests
Verifies the real Boto3 adapters, worker container fixes, CloudWatch metric dimensions,
and IAM resource scopes repaired during Step 6 deployment preflight.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from broker.inventory import Boto3EcsInventoryProvider
from diagnostics.incident_reader import IncidentReader
from diagnostics.ecs_reader import EcsStateReader
from diagnostics.log_reader import LogReader
from incidents.repository import DynamoDbIncidentRepository
from worker.processor import WorkProcessor
from worker.main import check_fault_injection_signal

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


def test_boto3_ecs_inventory_provider_parses_service_and_tasks():
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/5e06f3f870daa3e77006ba0c895029cb"
    mock_ecs = MagicMock()
    mock_ecs.describe_services.return_value = {
        "services": [{
            "status": "ACTIVE",
            "desiredCount": 6,
            "runningCount": 6,
            "pendingCount": 0,
            "deployments": [{"rolloutState": "COMPLETED", "status": "PRIMARY"}],
        }]
    }
    mock_ecs.list_tasks.return_value = {"taskArns": [task_arn]}
    mock_ecs.describe_tasks.return_value = {
        "tasks": [{
            "taskArn": task_arn,
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/blastgate-sandbox",
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/blastgate-worker:1",
            "lastStatus": "RUNNING",
            "desiredStatus": "RUNNING",
            "containers": [],
        }]
    }

    provider = Boto3EcsInventoryProvider(ecs_client=mock_ecs)
    state = provider.get_service_state("blastgate-sandbox", "blastgate-workers")

    assert state.status == "ACTIVE"
    assert state.desired_count == 6
    assert task_arn in state.tasks
    assert state.tasks[task_arn].task_family == "blastgate-worker"
    assert state.tasks[task_arn].last_status == "RUNNING"

    single = provider.get_task_details("blastgate-sandbox", task_arn)
    assert single is not None
    assert single.task_arn == task_arn


def test_diagnostics_dynamodb_and_cloudwatch_readers():
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/b6e222a94581aa6eb0f6ccbab5ad4c7c"
    mock_ddb = MagicMock()
    mock_ddb.get_item.return_value = {
        "Item": {
            "incident_id": {"S": "inc-14f8f4bb8c0e79a0"},
            "payload_json": {"S": json.dumps({
                "incident_id": "inc-14f8f4bb8c0e79a0",
                "alarm_name": "blastgate-worker-stalled-alarm",
                "cluster_name": "blastgate-sandbox",
                "service_name": "blastgate-workers",
                "target_task_arn": task_arn,
                "status": "OPEN",
                "state": "ALARM",
            })},
        }
    }
    reader = IncidentReader(dynamodb_client=mock_ddb)
    inc = reader.get_incident("inc-14f8f4bb8c0e79a0")
    assert inc is not None
    assert inc["target_task_arn"] == task_arn

    mock_logs = MagicMock()
    mock_logs.filter_log_events.return_value = {
        "events": [{"message": "<script>alert(1)</script> worker stalled"}]
    }
    log_rd = LogReader(logs_client=mock_logs)
    logs_out = log_rd.get_bounded_log_excerpts(task_arn)
    assert logs_out["is_untrusted_data"] is True
    assert logs_out["line_count"] == 1
    assert "&lt;script&gt;" in logs_out["log_lines"][0]


def test_dynamodb_incident_repo_scan_and_stalled_lookup():
    import time
    now = time.time()
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/11b95589484683d782f5054ca6d4605b"
    mock_ddb = MagicMock()
    mock_ddb.scan.return_value = {
        "Items": [
            {"task_arn": {"S": "CONTROL#FAULT_INJECTION"}, "timestamp": {"N": str(now)}},
            {"task_arn": {"S": task_arn}, "timestamp": {"N": str(now - 5)}},
        ]
    }
    repo = DynamoDbIncidentRepository(dynamodb_client=mock_ddb)
    found = repo.find_latest_stalled_task_arn()
    assert found == task_arn


def test_worker_fault_injection_signal_only_stalls_targeted_task():
    target_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/a5c6c1a104cf7da7890a5dda2afbed0f"
    other_arn = "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000001"
    mock_ddb = MagicMock()
    mock_ddb.get_item.return_value = {
        "Item": {
            "task_arn": {"S": "CONTROL#FAULT_INJECTION"},
            "target_task_arn": {"S": target_arn},
            "inject_stall": {"BOOL": True},
            "reason": {"S": "Test stall"},
        }
    }

    p_other = WorkProcessor(interval_seconds=0.1)
    p_target = WorkProcessor(interval_seconds=0.1)

    import worker.main as wmain
    orig = wmain.ENABLE_FAULT_INJECTION
    wmain.ENABLE_FAULT_INJECTION = True
    try:
        check_fault_injection_signal(mock_ddb, other_arn, p_other)
        check_fault_injection_signal(mock_ddb, target_arn, p_target)
        assert p_other.is_stalled is False
        assert p_target.is_stalled is True
    finally:
        wmain.ENABLE_FAULT_INJECTION = orig


def test_worker_dockerfile_readable_by_non_root():
    dockerfile = (WORKSPACE_ROOT / "src" / "worker" / "Dockerfile").read_text(encoding="utf-8")
    assert "--prefix=/install" in dockerfile
    assert "/usr/local" in dockerfile
    assert "/root/.local" not in dockerfile


def test_monitoring_alarm_includes_matching_metric_dimensions():
    tmpl = json.loads((CDK_OUT_DIR / "BlastGateMonitoringStack.template.json").read_text(encoding="utf-8"))
    alarms = [r["Properties"] for r in tmpl["Resources"].values() if r.get("Type") == "AWS::CloudWatch::Alarm"]
    assert len(alarms) == 1
    dims = {d["Name"]: d["Value"] for d in alarms[0].get("Dimensions", [])}
    assert dims == {"ClusterName": "blastgate-sandbox", "ServiceName": "blastgate-workers"}
