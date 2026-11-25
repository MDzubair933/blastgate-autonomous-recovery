"""
BlastGate Network Security Verification Tests
Covers requirements INF-004, INF-005, INF-006.
"""

import json
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CDK_OUT_DIR = WORKSPACE_ROOT / "infrastructure" / "cdk" / "cdk.out"


@pytest.fixture(scope="module")
def network_template():
    template_file = CDK_OUT_DIR / "BlastGateNetworkStack.template.json"
    assert template_file.exists(), f"Missing template file: {template_file}"
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)


# INF-004: Network stack has zero NAT Gateways (nat_gateways=0)
def test_inf_004_zero_nat_gateways(network_template):
    resources = network_template.get("Resources", {})
    nat_gateways = [
        res_id for res_id, res in resources.items()
        if res.get("Type") == "AWS::EC2::NatGateway"
    ]
    assert len(nat_gateways) == 0, (
        f"CRITICAL COST FAILURE: Found {len(nat_gateways)} NAT Gateway(s): {nat_gateways}. "
        f"NAT Gateways cost ~$32.40/month each and are forbidden."
    )


# INF-005: Network stack has zero Application Load Balancers
def test_inf_005_zero_load_balancers(network_template):
    resources = network_template.get("Resources", {})
    load_balancers = [
        res_id for res_id, res in resources.items()
        if res.get("Type") in [
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            "AWS::ElasticLoadBalancing::LoadBalancer"
        ]
    ]
    assert len(load_balancers) == 0, (
        f"CRITICAL COST FAILURE: Found {len(load_balancers)} Load Balancer(s): {load_balancers}. "
        f"Load Balancers cost ~$16.20/month each and are forbidden in sandbox."
    )


# INF-006: Worker security group has zero open inbound CIDR (no 0.0.0.0/0 ingress)
def test_inf_006_worker_security_group_no_open_ingress(network_template):
    resources = network_template.get("Resources", {})
    sec_groups = [
        res for res in resources.values()
        if res.get("Type") == "AWS::EC2::SecurityGroup"
    ]
    assert len(sec_groups) >= 1, "Expected at least 1 SecurityGroup in NetworkStack"

    for sg in sec_groups:
        props = sg.get("Properties", {})
        ingress_rules = props.get("SecurityGroupIngress", [])
        for rule in ingress_rules:
            cidr = rule.get("CidrIp", "")
            cidr_v6 = rule.get("CidrIpv6", "")
            assert cidr != "0.0.0.0/0", f"CRITICAL SECURITY FAILURE: Found 0.0.0.0/0 ingress in SG: {rule}"
            assert cidr_v6 != "::/0", f"CRITICAL SECURITY FAILURE: Found ::/0 ingress in SG: {rule}"
