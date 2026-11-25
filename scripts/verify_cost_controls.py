#!/usr/bin/env python3
"""
BlastGate Cost Control Verification Script
Audits synthesized CloudFormation templates and configuration to ensure
strict cost guardrails (zero NAT, zero ALB, initial desiredCount=0, 14-day log retention).
"""

import json
from pathlib import Path

CDK_OUT_DIR = Path(__file__).resolve().parent.parent / "infrastructure" / "cdk" / "cdk.out"


def load_template(stack_name: str) -> dict:
    template_path = CDK_OUT_DIR / f"{stack_name}.template.json"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("BLASTGATE COST CONTROL AUDIT")
    print(f"CDK Output Dir: {CDK_OUT_DIR}")
    print("=" * 60)

    # 1. Audit WorkerStack: DesiredCount == 0
    worker_tmpl = load_template("BlastGateWorkerStack")
    resources = worker_tmpl.get("Resources", {})
    services = [r for r in resources.values() if r.get("Type") == "AWS::ECS::Service"]
    assert len(services) == 1, "Expected exactly 1 ECS Service"
    svc_props = services[0].get("Properties", {})
    desired = svc_props.get("DesiredCount", -1)
    if desired != 0:
        print(f"[FAIL] ECS Service DesiredCount is {desired}, expected 0!")
        exit(1)
    print("[PASS] WorkerStack: Initial DesiredCount is strictly 0.")

    # 2. Audit NetworkStack: Zero NAT Gateways & Zero ALBs
    net_tmpl = load_template("BlastGateNetworkStack")
    net_resources = net_tmpl.get("Resources", {})
    nat_gws = [r for r in net_resources.values() if r.get("Type") == "AWS::EC2::NatGateway"]
    if nat_gws:
        print(f"[FAIL] Found {len(nat_gws)} NAT Gateways in NetworkStack! Must be 0.")
        exit(1)
    print("[PASS] NetworkStack: Zero NAT Gateways configured ($0/month fixed network cost).")

    # Check for Load Balancers
    elbs = [r for r in net_resources.values() if r.get("Type") in ["AWS::ElasticLoadBalancingV2::LoadBalancer", "AWS::ElasticLoadBalancing::LoadBalancer"]]
    if elbs:
        print(f"[FAIL] Found {len(elbs)} Load Balancers! Must be 0.")
        exit(1)
    print("[PASS] NetworkStack: Zero Load Balancers configured.")

    # 3. Audit MonitoringStack: Log retention is 14 days
    mon_tmpl = load_template("BlastGateMonitoringStack")
    mon_resources = mon_tmpl.get("Resources", {})
    log_groups = [r for r in mon_resources.values() if r.get("Type") == "AWS::Logs::LogGroup"]
    for lg in log_groups:
        ret = lg.get("Properties", {}).get("RetentionInDays", None)
        assert ret == 14, f"Log group retention is {ret}, expected 14 days!"
    print(f"[PASS] MonitoringStack: All {len(log_groups)} log groups enforce 14-day retention.")

    # 4. Audit StorageStack: On-Demand Billing & No Audit TTL
    storage_tmpl = load_template("BlastGateStorageStack")
    storage_res = storage_tmpl.get("Resources", {})
    tables = [r for r in storage_res.values() if r.get("Type") == "AWS::DynamoDB::Table"]
    for t in tables:
        billing = t.get("Properties", {}).get("BillingMode")
        assert billing == "PAY_PER_REQUEST", f"Table billing mode is {billing}, expected PAY_PER_REQUEST"
        t_name = t.get("Properties", {}).get("TableName", "")
        if "audit" in t_name.lower():
            ttl_spec = t.get("Properties", {}).get("TimeToLiveSpecification")
            assert ttl_spec is None, "Audit table must NOT have TTL configured!"
    print(f"[PASS] StorageStack: All {len(tables)} DynamoDB tables enforce PAY_PER_REQUEST on-demand billing.")
    print("[PASS] StorageStack: Audit table has zero automatic TTL deletion.")

    print("\n[SUCCESS] ALL COST CONTROLS VERIFIED!")


if __name__ == "__main__":
    main()
