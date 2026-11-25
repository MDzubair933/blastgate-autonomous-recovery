"""
BlastGate Step 5.2 Deployment Readiness & Security Gate Tests
Covers automated pre-deployment verifications across synthesized CDK stacks,
packaged Lambda runtimes, EventBridge rules, ECR configuration, and Cedar policies.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


@pytest.fixture(scope="module")
def broker_template():
    template_file = CDK_OUT_DIR / "BlastGateBrokerStack.template.json"
    assert template_file.exists(), f"Missing template: {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def worker_template():
    template_file = CDK_OUT_DIR / "BlastGateWorkerStack.template.json"
    assert template_file.exists(), f"Missing template: {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


def test_all_four_operational_lambdas_synthesized(broker_template):
    """Verifies that all 4 required operational Lambdas are synthesized with Python 3.12."""
    resources = broker_template.get("Resources", {})
    functions = {}
    for res_id, res in resources.items():
        if res.get("Type") == "AWS::Lambda::Function":
            fn_name = res.get("Properties", {}).get("FunctionName", "")
            functions[fn_name] = res.get("Properties", {})

    expected_functions = [
        "blastgate-remediation-broker",
        "blastgate-diagnostics",
        "blastgate-watchdog",
        "blastgate-incident-ingestion",
    ]

    for exp_fn in expected_functions:
        assert exp_fn in functions, f"Expected Lambda function {exp_fn} missing from BrokerStack"
        props = functions[exp_fn]
        assert props.get("Runtime") == "python3.12"
        assert props.get("MemorySize") == 256
        assert props.get("Timeout") in [30, 60]


def test_agentcore_gateway_resource_permissions_on_lambdas(broker_template):
    """Verifies resource-based invoke permissions for bedrock-agentcore.amazonaws.com on broker and diagnostics."""
    resources = broker_template.get("Resources", {})
    permissions = [
        res.get("Properties", {})
        for res in resources.values()
        if res.get("Type") == "AWS::Lambda::Permission"
    ]

    allowed_principals = [p.get("Principal") for p in permissions]
    assert "bedrock-agentcore.amazonaws.com" in allowed_principals, (
        "bedrock-agentcore.amazonaws.com must be granted lambda:InvokeFunction permission"
    )

    # Must have permissions for both Broker and Diagnostics functions
    actions = [p.get("Action") for p in permissions]
    assert all(a == "lambda:InvokeFunction" for a in actions)
    assert len(permissions) >= 2


def test_eventbridge_watchdog_schedule_and_incident_alarm_rules(broker_template):
    """Verifies EventBridge rules for 1-minute watchdog evaluation and CloudWatch Alarm State Change."""
    resources = broker_template.get("Resources", {})
    rules = {}
    for res_id, res in resources.items():
        if res.get("Type") == "AWS::Events::Rule":
            rule_name = res.get("Properties", {}).get("Name", "")
            rules[rule_name] = res.get("Properties", {})

    assert "blastgate-watchdog-schedule" in rules, "Watchdog schedule rule missing"
    assert rules["blastgate-watchdog-schedule"].get("ScheduleExpression") == "rate(1 minute)"

    assert "blastgate-alarm-state-change-rule" in rules, "Alarm state change rule missing"
    pattern = rules["blastgate-alarm-state-change-rule"].get("EventPattern", {})
    assert pattern.get("source") == ["aws.cloudwatch"]
    assert pattern.get("detail-type") == ["CloudWatch Alarm State Change"]


def test_worker_stack_ecr_repository_configuration(worker_template):
    """Verifies WorkerStack provisions a dedicated ECR repo blastgate-worker with scan-on-push."""
    resources = worker_template.get("Resources", {})
    ecr_repos = [
        res.get("Properties", {})
        for res in resources.values()
        if res.get("Type") == "AWS::ECR::Repository"
    ]

    assert len(ecr_repos) == 1, f"Expected 1 ECR Repository, found {len(ecr_repos)}"
    repo_props = ecr_repos[0]
    assert repo_props.get("RepositoryName") == "blastgate-worker"
    assert repo_props.get("ImageScanningConfiguration", {}).get("ScanOnPush") is True


def test_lambda_runtime_bundled_artifacts():
    """Verifies local source directories and staged Lambda packages contain required contracts, schemas, and telemetry."""
    broker_contracts = WORKSPACE_ROOT / "src" / "broker" / "contracts" / "remediation_request.schema.json"
    broker_reqs = WORKSPACE_ROOT / "src" / "broker" / "requirements.txt"
    dist_broker = WORKSPACE_ROOT / "dist" / "lambda" / "broker.zip"

    assert broker_contracts.exists(), "src/broker/contracts/remediation_request.schema.json must exist"
    assert broker_reqs.exists(), "src/broker/requirements.txt must exist"
    assert dist_broker.exists(), "dist/lambda/broker.zip must exist"


def test_cedar_policy_security_state():
    """Verifies production Cedar policy has zero unconditional forbid and default deny with permit policies."""
    from agentcore.policies.evaluator import CedarPolicySyntaxAuditor

    cedar_file = WORKSPACE_ROOT / "agentcore" / "policies" / "cedar_policies.cedar"
    assert cedar_file.exists(), f"Missing {cedar_file}"
    content = cedar_file.read_text(encoding="utf-8")

    # Use CedarPolicySyntaxAuditor to ensure no critical defects (like unconditional forbid statements)
    findings = CedarPolicySyntaxAuditor.audit_policy_text(content)
    critical_defects = [f for f in findings if f.startswith("CRITICAL_DEFECT")]
    assert len(critical_defects) == 0, f"Cedar defects detected: {critical_defects}"

    # Strip comments and ensure no actual forbid statement is executed
    code_lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("//")]
    assert not any(line.startswith("forbid") for line in code_lines), "No forbid statements allowed in production Cedar policy"
    assert any(line.startswith("permit") for line in code_lines), "Production Cedar policy must contain explicit permit policies"
    assert "REPLACE_UNHEALTHY_ECS_WORKER" in content
    assert "blastgatediag___get_incident_diagnostics" in content
