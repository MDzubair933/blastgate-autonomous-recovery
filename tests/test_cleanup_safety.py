"""
BlastGate Cleanup Safety & Code Integrity Tests
Covers requirements INF-021, INF-022, INF-023, INF-024, INF-025.
"""

import re
import sys
import subprocess
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = WORKSPACE_ROOT / "scripts"


# INF-021: Cleanup script defaults to dry-run mode
def test_inf_021_cleanup_defaults_to_dry_run():
    cleanup_script = SCRIPTS_DIR / "cleanup.py"
    assert cleanup_script.exists(), "scripts/cleanup.py must exist"
    content = cleanup_script.read_text(encoding="utf-8")
    assert "default=True" in content, "Cleanup parse_args must default --dry-run to True"
    assert "default=False" in content, "Cleanup parse_args must default --confirm to False"


# INF-022: Cleanup script requires explicit --confirm flag to modify resources
def test_inf_022_cleanup_requires_confirm_flag():
    cleanup_script = SCRIPTS_DIR / "cleanup.py"
    content = cleanup_script.read_text(encoding="utf-8")
    assert "args.confirm" in content, "Cleanup script must check args.confirm before execution"
    assert "is_dry_run = args.dry_run and not args.confirm" in content or "not args.confirm" in content


# INF-023: Cleanup script checks account ID and refuses execution on non-sandbox account
def test_inf_023_cleanup_checks_account_safety():
    cleanup_script = SCRIPTS_DIR / "cleanup.py"
    content = cleanup_script.read_text(encoding="utf-8")
    assert 'EXPECTED_ACCOUNT_ID = "123456789012"' in content, "Cleanup must hardcode sandbox account verification"
    assert "account_id != EXPECTED_ACCOUNT_ID" in content, "Cleanup must check account_id != EXPECTED_ACCOUNT_ID"
    assert "ALLOWED_REGIONS" in content, "Cleanup must enforce ALLOWED_REGIONS"


# INF-024: Step 1 contracts remain unchanged and pass validation (regression)
def test_inf_024_step1_contracts_regression():
    validate_script = SCRIPTS_DIR / "validate_contracts.py"
    assert validate_script.exists(), "scripts/validate_contracts.py must exist"
    # Execute validation script
    result = subprocess.run(
        [sys.executable, str(validate_script)],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Step 1 validate_contracts.py failed: {result.stderr}\n{result.stdout}"
    assert "ALL CONTRACT SPECIFICATIONS AND SCHEMAS VALIDATED PERFECTLY!" in result.stdout


# INF-025: No hardcoded secrets, access keys, or credentials in any file
def test_inf_025_no_hardcoded_secrets():
    # Scan python files, json files, md files in repository for AWS secret keys / tokens
    secret_patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID
        re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]"),
        re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_]{20,}"),
    ]

    files_to_scan = []
    for ext in ["*.py", "*.json", "*.md"]:
        for p in WORKSPACE_ROOT.rglob(ext):
            # Skip virtual environments and git directories
            if ".venv" in p.parts or ".git" in p.parts or "cdk.out" in p.parts or "__pycache__" in p.parts:
                continue
            files_to_scan.append(p)

    violations = []
    for f in files_to_scan:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for pat in secret_patterns:
            matches = pat.findall(content)
            if matches:
                violations.append(f"{f}: matches {pat.pattern}")

    assert len(violations) == 0, f"Found hardcoded secrets in repository: {violations}"
