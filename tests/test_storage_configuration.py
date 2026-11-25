"""
BlastGate Storage Configuration Verification Tests
Covers requirements INF-007, INF-008, INF-009, INF-010, INF-011.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


@pytest.fixture(scope="module")
def storage_template():
    template_file = CDK_OUT_DIR / "BlastGateStorageStack.template.json"
    assert template_file.exists(), f"Missing template file: {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def tables_by_name(storage_template):
    tables = {}
    resources = storage_template.get("Resources", {})
    for res in resources.values():
        if res.get("Type") == "AWS::DynamoDB::Table":
            props = res.get("Properties", {})
            name = props.get("TableName", "")
            tables[name] = props
    return tables


# INF-007: DynamoDB state table (blastgate-state) configured with On-Demand billing
def test_inf_007_state_table_on_demand_billing(tables_by_name):
    assert "blastgate-state" in tables_by_name, "Table 'blastgate-state' not found in StorageStack"
    props = tables_by_name["blastgate-state"]
    assert props.get("BillingMode") == "PAY_PER_REQUEST", (
        f"State table billing mode must be PAY_PER_REQUEST, got {props.get('BillingMode')}"
    )


# INF-008: DynamoDB state table has partition key 'cluster_id' (String)
def test_inf_008_state_table_keys(tables_by_name):
    props = tables_by_name["blastgate-state"]
    key_schema = props.get("KeySchema", [])
    pk = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), None)
    assert pk == "cluster_id", f"State table partition key must be 'cluster_id', got '{pk}'"

    attrs = props.get("AttributeDefinitions", [])
    pk_attr = next((a for a in attrs if a["AttributeName"] == "cluster_id"), None)
    assert pk_attr is not None, "Attribute definition for cluster_id missing"
    assert pk_attr["AttributeType"] == "S", f"cluster_id attribute type must be 'S' (String), got '{pk_attr['AttributeType']}'"


# INF-009: DynamoDB audit table (blastgate-audit) configured with On-Demand billing
def test_inf_009_audit_table_on_demand_billing(tables_by_name):
    assert "blastgate-audit" in tables_by_name, "Table 'blastgate-audit' not found in StorageStack"
    props = tables_by_name["blastgate-audit"]
    assert props.get("BillingMode") == "PAY_PER_REQUEST", (
        f"Audit table billing mode must be PAY_PER_REQUEST, got {props.get('BillingMode')}"
    )


# INF-010: DynamoDB audit table has partition key 'event_id' (String)
def test_inf_010_audit_table_keys(tables_by_name):
    props = tables_by_name["blastgate-audit"]
    key_schema = props.get("KeySchema", [])
    pk = next((k["AttributeName"] for k in key_schema if k["KeyType"] == "HASH"), None)
    assert pk == "event_id", f"Audit table partition key must be 'event_id', got '{pk}'"

    attrs = props.get("AttributeDefinitions", [])
    pk_attr = next((a for a in attrs if a["AttributeName"] == "event_id"), None)
    assert pk_attr is not None, "Attribute definition for event_id missing"
    assert pk_attr["AttributeType"] == "S", f"event_id attribute type must be 'S' (String), got '{pk_attr['AttributeType']}'"


# INF-011: DynamoDB audit table has NO TTL enabled (append-oriented retention)
def test_inf_011_audit_table_no_ttl(tables_by_name):
    props = tables_by_name["blastgate-audit"]
    ttl_spec = props.get("TimeToLiveSpecification")
    assert ttl_spec is None or ttl_spec.get("Enabled") is False, (
        f"Audit table must NOT have TTL enabled, found: {ttl_spec}"
    )
