"""
BlastGate Step 4 CDK Infrastructure Verification Tests (T4-025)
Verifies synthesized CloudFormation templates for Step 4 additions:
- DynamoDB blastgate-heartbeats table
- DynamoDB blastgate-incidents table
- CloudWatch Watchdog Alarm for ConfirmedStalledWorkerCount
- IAM permissions for worker telemetry publication and diagnostics reading
- Strict preservation of desiredCount = 0 (cost guardrail)
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


@pytest.fixture(scope="module")
def storage_template():
    template_file = CDK_OUT_DIR / "BlastGateStorageStack.template.json"
    assert template_file.exists(), f"Missing {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def monitoring_template():
    template_file = CDK_OUT_DIR / "BlastGateMonitoringStack.template.json"
    assert template_file.exists(), f"Missing {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def iam_template():
    template_file = CDK_OUT_DIR / "BlastGateIamStack.template.json"
    assert template_file.exists(), f"Missing {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def worker_template():
    template_file = CDK_OUT_DIR / "BlastGateWorkerStack.template.json"
    assert template_file.exists(), f"Missing {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


def test_storage_stack_has_heartbeat_and_incident_tables(storage_template):
    """StorageStack contains blastgate-heartbeats and blastgate-incidents tables with On-Demand billing."""
    tables = {}
    for res in storage_template.get("Resources", {}).values():
        if res.get("Type") == "AWS::DynamoDB::Table":
            name = res.get("Properties", {}).get("TableName", "")
            tables[name] = res.get("Properties", {})

    assert "blastgate-heartbeats" in tables, "blastgate-heartbeats table missing in StorageStack"
    assert "blastgate-incidents" in tables, "blastgate-incidents table missing in StorageStack"

    # Both tables must have On-Demand billing
    assert tables["blastgate-heartbeats"].get("BillingMode") == "PAY_PER_REQUEST"
    assert tables["blastgate-incidents"].get("BillingMode") == "PAY_PER_REQUEST"

    # Key schema checks
    hb_pk = tables["blastgate-heartbeats"]["KeySchema"][0]["AttributeName"]
    assert hb_pk == "task_arn"

    inc_pk = tables["blastgate-incidents"]["KeySchema"][0]["AttributeName"]
    assert inc_pk == "incident_id"


def test_monitoring_stack_has_stalled_worker_alarm(monitoring_template):
    """MonitoringStack contains blastgate-worker-stalled-alarm on ConfirmedStalledWorkerCount."""
    alarms = {}
    for res in monitoring_template.get("Resources", {}).values():
        if res.get("Type") == "AWS::CloudWatch::Alarm":
            name = res.get("Properties", {}).get("AlarmName", "")
            alarms[name] = res.get("Properties", {})

    assert "blastgate-worker-stalled-alarm" in alarms, "Worker stalled alarm missing in MonitoringStack"
    alarm_props = alarms["blastgate-worker-stalled-alarm"]
    assert alarm_props.get("MetricName") == "ConfirmedStalledWorkerCount"
    assert alarm_props.get("Namespace") == "BlastGate/Workers"
    assert alarm_props.get("Threshold") == 1
    assert alarm_props.get("ComparisonOperator") == "GreaterThanOrEqualToThreshold"


def test_iam_stack_worker_task_role_heartbeat_putitem(iam_template):
    """Worker task role allows dynamodb:PutItem on blastgate-heartbeats."""
    policies = iam_template.get("Resources", {})
    found_put = False
    for res in policies.values():
        if res.get("Type") == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                if "dynamodb:PutItem" in actions:
                    resources = stmt.get("Resource", [])
                    if isinstance(resources, str):
                        resources = [resources]
                    for r in resources:
                        if isinstance(r, str) and "blastgate-heartbeats" in r:
                            found_put = True
    assert found_put is True, "Worker task role must have PutItem on blastgate-heartbeats"


def test_iam_stack_diagnostics_role_read_permissions(iam_template):
    """Diagnostics role allows GetItem/Query/Scan on incidents and heartbeats."""
    policies = iam_template.get("Resources", {})
    read_actions_found = False
    for res in policies.values():
        if res.get("Type") == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                if any(a in actions for a in ["dynamodb:GetItem", "dynamodb:Query"]):
                    resources = stmt.get("Resource", [])
                    if isinstance(resources, str):
                        resources = [resources]
                    for r in resources:
                        if isinstance(r, str) and ("blastgate-incidents" in r or "blastgate-heartbeats" in r):
                            read_actions_found = True
    assert read_actions_found is True, "Diagnostics role must have read permission on incidents/heartbeats"


def test_worker_stack_cost_guardrail_desired_count_zero(worker_template):
    """CRITICAL COST GUARDRAIL: ECS Service desiredCount must remain strictly 0."""
    services = {}
    for res in worker_template.get("Resources", {}).values():
        if res.get("Type") == "AWS::ECS::Service":
            services[res.get("Properties", {}).get("ServiceName", "")] = res.get("Properties", {})

    assert "blastgate-workers" in services
    service_props = services["blastgate-workers"]
    assert service_props.get("DesiredCount") == 0, (
        f"CRITICAL: DesiredCount must be 0 for cost control, got {service_props.get('DesiredCount')}"
    )
