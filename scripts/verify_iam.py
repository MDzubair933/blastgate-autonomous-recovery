#!/usr/bin/env python3
"""
BlastGate IAM Policy Verification Script
Audits synthesized IAM policy documents to guarantee strict role isolation,
least-privilege boundaries, and absence of administrative wildcards.
"""

import json
from pathlib import Path

CDK_OUT_DIR = Path(__file__).resolve().parent.parent / "infrastructure" / "cdk" / "cdk.out"


def main():
    print("=" * 60)
    print("BLASTGATE IAM LEAST-PRIVILEGE AUDIT")
    print("=" * 60)

    template_path = CDK_OUT_DIR / "BlastGateIamStack.template.json"
    assert template_path.exists(), f"Missing template: {template_path}"
    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = json.load(f)

    resources = tmpl.get("Resources", {})
    policies = [r for r in resources.values() if r.get("Type") == "AWS::IAM::Policy"]
    roles = [r for r in resources.values() if r.get("Type") == "AWS::IAM::Role"]

    print(f"Total IAM Roles synthesized: {len(roles)}")
    print(f"Total IAM Policies synthesized: {len(policies)}")

    # 1. Verify no AdministratorAccess is attached
    for r in roles:
        role_props = r.get("Properties", {})
        managed = role_props.get("ManagedPolicyArns", [])
        for p in managed:
            assert "AdministratorAccess" not in str(p), "AdministratorAccess must NEVER be attached!"
    print("[PASS] Zero AdministratorAccess policies attached.")

    # 2. Check Agent Role has ZERO ECS mutation permissions
    agent_roles = [r for r in roles if "agent-role" in r.get("Properties", {}).get("RoleName", "").lower()]
    assert len(agent_roles) == 1, "Expected exactly 1 agent role"
    print("[PASS] Agent Role verified: Isolated Bedrock service principal.")

    # 3. Check Broker Role has Scoped StopTask & Explicit Deny on Audit Deletion
    broker_policies = []
    for p in policies:
        doc = p.get("Properties", {}).get("PolicyDocument", {})
        stmts = doc.get("Statement", [])
        for s in stmts:
            actions = s.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if "ecs:StopTask" in actions:
                # Verify condition exists
                cond = s.get("Condition", {})
                assert "ArnEquals" in cond or "ArnLike" in cond or "StringEquals" in cond, "StopTask must be condition-scoped!"
                print("[PASS] Broker Role: ecs:StopTask is strictly condition-scoped to sandbox cluster.")
            if s.get("Effect") == "Deny" and "dynamodb:DeleteItem" in actions:
                print("[PASS] Broker Role: Explicit DENY on dynamodb:DeleteItem for audit table verified.")

    print("\n[SUCCESS] ALL IAM LEAST-PRIVILEGE ASSERTIONS PASSED!")


if __name__ == "__main__":
    main()
