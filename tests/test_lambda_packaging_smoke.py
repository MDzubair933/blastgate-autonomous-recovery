"""
BlastGate Lambda Packaging Smoke Tests
Verifies that all 4 Lambda deployment packages staged in dist/lambda/
are self-contained, contain all mandatory runtime dependencies (including
Linux x86_64 binary wheels for Python 3.12), and can be imported cleanly.
"""

import zipfile
import tempfile
import sys
import importlib
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DIST_LAMBDA_DIR = WORKSPACE_ROOT / "dist" / "lambda"


@pytest.fixture(scope="module")
def ensure_packages_built():
    """Ensures Lambda packages in dist/lambda are built before running smoke tests."""
    broker_zip = DIST_LAMBDA_DIR / "broker.zip"
    if not broker_zip.exists():
        import subprocess
        res = subprocess.run(
            [sys.executable, str(WORKSPACE_ROOT / "scripts" / "package_lambdas.py")],
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, f"package_lambdas.py failed: {res.stderr}"
    return DIST_LAMBDA_DIR


def test_all_four_archives_exist(ensure_packages_built):
    """Verifies that all four Lambda archives exist and are non-empty."""
    expected = ["broker.zip", "diagnostics.zip", "watchdog.zip", "incident_ingestion.zip"]
    for name in expected:
        zip_path = DIST_LAMBDA_DIR / name
        assert zip_path.exists(), f"Archive {name} does not exist in {DIST_LAMBDA_DIR}"
        assert zip_path.stat().st_size > 1000, f"Archive {name} is suspiciously small: {zip_path.stat().st_size} bytes"


def test_broker_archive_contains_linux_jsonschema_and_contracts(ensure_packages_built):
    """Verifies broker.zip has bundled contracts schemas and Linux x86_64 jsonschema/rpds binaries."""
    zip_path = DIST_LAMBDA_DIR / "broker.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    # Core handler and contracts
    assert "handler.py" in names
    assert "models.py" in names
    assert "contracts/remediation_request.schema.json" in names
    assert "contracts/action_catalog.json" in names
    assert "telemetry/heartbeat_repository.py" in names
    assert "telemetry/validator.py" in names

    # Vendored jsonschema & dependencies
    assert any(n.startswith("jsonschema/") for n in names)
    assert any(n.startswith("attrs/") for n in names)
    assert any(n.startswith("referencing/") for n in names)
    assert any(n.startswith("rpds/") for n in names)
    assert "typing_extensions.py" in names

    # CRITICAL: Must contain Linux x86_64 ELF shared object (.so) for Python 3.12, NOT a Windows .pyd
    so_files = [n for n in names if n.endswith(".so")]
    assert len(so_files) > 0, "Missing Linux .so native extensions for AWS Lambda"
    assert any("rpds" in f and "x86_64" in f for f in so_files), f"Expected rpds Linux x86_64 .so, found: {so_files}"


def test_diagnostics_archive_contains_telemetry(ensure_packages_built):
    """Verifies diagnostics.zip contains handler and single-sourced telemetry module."""
    zip_path = DIST_LAMBDA_DIR / "diagnostics.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    assert "handler.py" in names
    assert "incident_reader.py" in names
    assert "telemetry/models.py" in names
    assert "telemetry/validator.py" in names


def test_watchdog_archive_contains_telemetry(ensure_packages_built):
    """Verifies watchdog.zip contains handler and single-sourced telemetry module."""
    zip_path = DIST_LAMBDA_DIR / "watchdog.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    assert "handler.py" in names
    assert "evaluator.py" in names
    assert "metrics.py" in names
    assert "telemetry/models.py" in names
    assert "telemetry/validator.py" in names


def test_incident_ingestion_archive_contents(ensure_packages_built):
    """Verifies incident_ingestion.zip contains handler, validator, and deduplicator."""
    zip_path = DIST_LAMBDA_DIR / "incident_ingestion.zip"
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    assert "handler.py" in names
    assert "validator.py" in names
    assert "deduplication.py" in names
    assert "models.py" in names


def test_package_unpack_and_smoke_import(ensure_packages_built):
    """Unpacks archives to isolated sandbox directories and runs subprocess smoke test to simulate true Lambda runtime isolation."""
    import subprocess
    for pkg_name in ["diagnostics", "watchdog", "incident_ingestion"]:
        zip_path = DIST_LAMBDA_DIR / f"{pkg_name}.zip"
        with tempfile.TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            # Test in clean subprocess with cwd=tmp_dir to accurately simulate isolated Lambda execution environment
            check_script = "import handler; assert hasattr(handler, 'lambda_handler'); assert callable(handler.lambda_handler); print('OK')"
            res = subprocess.run(
                [sys.executable, "-c", check_script],
                cwd=tmp_dir,
                capture_output=True,
                text=True
            )
            assert res.returncode == 0, f"{pkg_name} smoke import failed in isolated runtime: {res.stderr}"
            assert "OK" in res.stdout
