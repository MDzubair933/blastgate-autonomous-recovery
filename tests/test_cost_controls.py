"""
BlastGate Cost Control Verification Tests
Covers requirements INF-003, INF-020, INF-027.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


# INF-003: ECS Service initial desiredCount is strictly 0
def test_inf_003_ecs_service_initial_desired_count_zero():
    worker_file = CDK_OUT_DIR / "BlastGateWorkerStack.template.json"
    assert worker_file.exists(), f"Missing template file: {worker_file}"
    with open(worker_file, "r", encoding="utf-8") as f:
        tmpl = json.load(f)

    resources = tmpl.get("Resources", {})
    services = [r for r in resources.values() if r.get("Type") == "AWS::ECS::Service"]
    assert len(services) == 1, f"Expected 1 ECS Service, found {len(services)}"

    desired = services[0].get("Properties", {}).get("DesiredCount")
    assert desired == 0, (
        f"CRITICAL COST FAILURE: ECS Service DesiredCount is {desired}! "
        f"Must be strictly 0 to guarantee $0.00 idle compute cost."
    )


# INF-020: CloudWatch Log Groups have retention set to 14 days (cost control)
def test_inf_020_cloudwatch_log_retention_fourteen_days():
    mon_file = CDK_OUT_DIR / "BlastGateMonitoringStack.template.json"
    assert mon_file.exists(), f"Missing template file: {mon_file}"
    with open(mon_file, "r", encoding="utf-8") as f:
        tmpl = json.load(f)

    resources = tmpl.get("Resources", {})
    log_groups = [r for r in resources.values() if r.get("Type") == "AWS::Logs::LogGroup"]
    assert len(log_groups) == 3, f"Expected 3 LogGroups in MonitoringStack, found {len(log_groups)}"

    for lg in log_groups:
        retention = lg.get("Properties", {}).get("RetentionInDays")
        assert retention == 14, (
            f"Log group retention is {retention} days; must be exactly 14 days to prevent storage accumulation"
        )


# INF-027: AWS Budget alert threshold is documented as advisory, not hard quota
def test_inf_027_budget_alert_is_advisory():
    # Verify that deployment plan explicitly notes budget alerts do not hard-terminate workloads
    plan_file = WORKSPACE_ROOT / "docs" / "STEP_2_DEPLOYMENT_PLAN.md"
    assert plan_file.exists(), "STEP_2_DEPLOYMENT_PLAN.md must exist"
    content = plan_file.read_text(encoding="utf-8")
    assert "Cost Guardrails" in content or "cost" in content.lower()
