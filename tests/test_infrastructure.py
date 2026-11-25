"""
BlastGate Infrastructure Stack Verification Tests
Covers requirements INF-001, INF-002, INF-026, INF-028, INF-029.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"

EXPECTED_STACKS = [
    "BlastGateNetworkStack",
    "BlastGateStorageStack",
    "BlastGateMonitoringStack",
    "BlastGateIamStack",
    "BlastGateWorkerStack",
    "BlastGateBrokerStack",
]


@pytest.fixture(scope="module")
def stack_templates():
    templates = {}
    for stack_name in EXPECTED_STACKS:
        template_file = CDK_OUT_DIR / f"{stack_name}.template.json"
        assert template_file.exists(), f"Missing template file: {template_file}"
        with open(template_file, "r", encoding="utf-8") as f:
            templates[stack_name] = json.load(f)
    return templates


# INF-001: All stacks synthesize without error using Python CDK v2
def test_inf_001_cdk_synthesis_manifest():
    manifest_file = CDK_OUT_DIR / "manifest.json"
    assert manifest_file.exists(), "cdk.out/manifest.json must exist"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    artifacts = manifest.get("artifacts", {})
    for stack in EXPECTED_STACKS:
        assert stack in artifacts, f"Stack {stack} not found in CDK manifest artifacts"


# INF-002: CloudFormation templates generated in cdk.out for all 6 stacks
def test_inf_002_all_six_templates_generated(stack_templates):
    assert len(stack_templates) == 6, f"Expected 6 templates, found {len(stack_templates)}"
    for stack in EXPECTED_STACKS:
        assert stack in stack_templates
        assert "Resources" in stack_templates[stack], f"Stack {stack} has no Resources block"


# INF-026: Resource naming follows consistent prefix 'blastgate-'
def test_inf_026_resource_naming_prefix(stack_templates):
    allowed_prefixes = ("blastgate-", "/aws/blastgate/")
    named_resources_found = 0

    for stack_name, template in stack_templates.items():
        resources = template.get("Resources", {})
        for res_id, res in resources.items():
            props = res.get("Properties", {})
            for name_field in ["TableName", "ClusterName", "ServiceName", "RoleName", "FunctionName", "LogGroupName"]:
                if name_field in props:
                    val = props[name_field]
                    if isinstance(val, str):
                        named_resources_found += 1
                        assert val.startswith(allowed_prefixes), (
                            f"Resource {res_id} ({name_field}={val}) in {stack_name} does not start with 'blastgate-'"
                        )
    assert named_resources_found >= 10, f"Expected at least 10 named resources with prefix, found {named_resources_found}"


# INF-028: All stacks declare explicit tags (Project=BlastGate, Environment=sandbox)
def test_inf_028_standard_tagging(stack_templates):
    # Check that tagged resources contain Project and Environment
    tagged_count = 0
    for stack_name, template in stack_templates.items():
        resources = template.get("Resources", {})
        for res_id, res in resources.items():
            props = res.get("Properties", {})
            tags = props.get("Tags", [])
            if isinstance(tags, list):
                tag_dict = {t.get("Key"): t.get("Value") for t in tags if isinstance(t, dict)}
                if "Project" in tag_dict:
                    tagged_count += 1
                    assert tag_dict.get("Project") == "BlastGate", f"Invalid Project tag in {res_id}"
                    assert tag_dict.get("Environment") == "sandbox", f"Invalid Environment tag in {res_id}"
    assert tagged_count > 0, "At least some resources must have standard tags rendered"


# INF-029: CDK outputs declare essential resource ARNs and names for Step 3 integration
def test_inf_029_essential_cdk_outputs(stack_templates):
    expected_outputs_by_stack = {
        "BlastGateNetworkStack": ["blastgate-vpc-id", "blastgate-worker-sg-id"],
        "BlastGateStorageStack": ["blastgate-state-table-arn", "blastgate-audit-table-arn"],
        "BlastGateMonitoringStack": ["blastgate-broker-log-group-arn", "blastgate-worker-log-group-arn", "blastgate-audit-log-group-arn"],
        "BlastGateIamStack": ["blastgate-agent-role-arn", "blastgate-gateway-example-arn", "blastgate-broker-role-arn"],
        "BlastGateWorkerStack": ["blastgate-cluster-arn", "blastgate-service-arn"],
        "BlastGateBrokerStack": ["blastgate-broker-function-arn"],
    }

    for stack_name, exp_exports in expected_outputs_by_stack.items():
        tmpl = stack_templates[stack_name]
        outputs = tmpl.get("Outputs", {})
        export_names = [o.get("Export", {}).get("Name") for o in outputs.values() if "Export" in o]
        for exp in exp_exports:
            assert exp in export_names, f"Export {exp} missing from {stack_name} outputs (found: {export_names})"
