"""
BlastGate Contract Validation Script
Validates all contract documents, JSON schemas, catalog constraints, and cross-references.
"""

import json
import os
import sys
from pathlib import Path
import jsonschema

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = WORKSPACE_ROOT / "contracts"
DOCS_DIR = WORKSPACE_ROOT / "docs"


def validate_json_file(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[FAIL] Malformed JSON in {file_path.name}: {e}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("BLASTGATE CONTRACT VALIDATION SUITE")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print("=" * 60)

    # 1. Verify existence of all mandatory specification files
    required_files = [
        CONTRACTS_DIR / "OPERATIONAL_RULES.md",
        CONTRACTS_DIR / "SECURITY_INVARIANTS.md",
        CONTRACTS_DIR / "action_catalog.json",
        CONTRACTS_DIR / "action_catalog.schema.json",
        CONTRACTS_DIR / "remediation_request.schema.json",
        CONTRACTS_DIR / "decision_receipt.schema.json",
        CONTRACTS_DIR / "audit_schema.json",
        CONTRACTS_DIR / "threat_model.md",
        DOCS_DIR / "RULE_ENFORCEMENT_MATRIX.md",
    ]

    for rf in required_files:
        if not rf.exists():
            print(f"[FAIL] Missing required specification file: {rf}")
            sys.exit(1)
        if rf.stat().st_size == 0:
            print(f"[FAIL] Specification file is empty: {rf}")
            sys.exit(1)
        print(f"[PASS] Found: {rf.relative_to(WORKSPACE_ROOT)} ({rf.stat().st_size} bytes)")

    # 2. Validate JSON Schemas
    schemas = [
        "action_catalog.schema.json",
        "remediation_request.schema.json",
        "decision_receipt.schema.json",
        "audit_schema.json",
    ]
    for s_name in schemas:
        s_data = validate_json_file(CONTRACTS_DIR / s_name)
        jsonschema.Draft7Validator.check_schema(s_data)
        print(f"[PASS] JSON Schema Draft-07 valid: {s_name}")

    # 3. Validate Catalog against Catalog Schema
    cat_schema = validate_json_file(CONTRACTS_DIR / "action_catalog.schema.json")
    catalog = validate_json_file(CONTRACTS_DIR / "action_catalog.json")
    jsonschema.validate(instance=catalog, schema=cat_schema)
    print("[PASS] action_catalog.json strictly conforms to action_catalog.schema.json")

    # 4. Verify Single Scoped Action
    actions = catalog.get("actions", [])
    if len(actions) != 1:
        print(f"[FAIL] Catalog must contain exactly 1 approved action, found {len(actions)}")
        sys.exit(1)

    act = actions[0]
    if act.get("action_id") != "REPLACE_UNHEALTHY_ECS_WORKER":
        print(f"[FAIL] Unexpected action_id: {act.get('action_id')}")
        sys.exit(1)
    if act.get("aws_api") != "ecs:StopTask":
        print(f"[FAIL] Unexpected aws_api: {act.get('aws_api')}")
        sys.exit(1)
    print(f"[PASS] Verified single allowable action: {act.get('action_id')} -> {act.get('aws_api')}")

    # 5. Check Operational Rules Coverage
    with open(CONTRACTS_DIR / "OPERATIONAL_RULES.md", "r", encoding="utf-8") as f:
        rules_text = f.read()

    for r_num in range(1, 9):
        r_tag = f"RULE R{r_num}:"
        if r_tag not in rules_text:
            print(f"[FAIL] Operational rule R{r_num} missing from OPERATIONAL_RULES.md")
            sys.exit(1)
    print("[PASS] Operational rules R1 through R8 verified in contracts/OPERATIONAL_RULES.md")

    # 6. Check Threat Model Coverage (A through L)
    with open(CONTRACTS_DIR / "threat_model.md", "r", encoding="utf-8") as f:
        threat_text = f.read()

    threat_letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    for t_let in threat_letters:
        t_tag = f"Threat {t_let}:"
        if t_tag not in threat_text:
            print(f"[FAIL] Threat scenario {t_let} missing from contracts/threat_model.md")
            sys.exit(1)
    print("[PASS] All 12 mandatory threat scenarios (A through L) verified in threat_model.md")

    print("\n[SUCCESS] ALL CONTRACT SPECIFICATIONS AND SCHEMAS VALIDATED PERFECTLY!")


if __name__ == "__main__":
    main()
