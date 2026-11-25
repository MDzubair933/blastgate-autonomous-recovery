#!/usr/bin/env python3
"""
BlastGate Lambda Package Staging & Validation Engine
Builds genuine, self-contained, deployable Lambda ZIP assets for:
1. blastgate-remediation-broker (with vendored Linux x86_64 jsonschema + contracts schemas)
2. blastgate-diagnostics (with single-source telemetry module)
3. blastgate-watchdog (with single-source telemetry module)
4. blastgate-incident-ingestion (with event validators and repository)

Performs archive inspection and dependency verification before marking ready.
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = WORKSPACE_ROOT / "src"
CONTRACTS_DIR = WORKSPACE_ROOT / "contracts"
DIST_DIR = WORKSPACE_ROOT / "dist" / "lambda"


def clean_and_prepare_dist():
    """Ensures dist/lambda directory is clean and prepared."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[PREPARE] Cleaned and created staging directory: {DIST_DIR}")


def stage_broker():
    """Stages and packages blastgate-remediation-broker."""
    stage_dir = DIST_DIR / "staging_broker"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy broker python sources
    src_broker = SRC_DIR / "broker"
    for py_file in src_broker.glob("*.py"):
        shutil.copy2(py_file, stage_dir / py_file.name)

    # 2. Stage contracts schemas
    contracts_target = stage_dir / "contracts"
    contracts_target.mkdir(parents=True, exist_ok=True)
    for schema_file in CONTRACTS_DIR.glob("*.json"):
        shutil.copy2(schema_file, contracts_target / schema_file.name)

    # 2b. Stage single-source telemetry module (for Rule R3 live heartbeat validation)
    telemetry_target = stage_dir / "telemetry"
    telemetry_target.mkdir(parents=True, exist_ok=True)
    for py_file in (SRC_DIR / "telemetry").glob("*.py"):
        shutil.copy2(py_file, telemetry_target / py_file.name)

    # 3. Vendor jsonschema for Python 3.12 Linux x86_64 runtime
    print("[VENDOR] Installing Linux x86_64 binary wheels for jsonschema into broker package...")
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--platform",
        "manylinux2014_x86_64",
        "--target",
        str(stage_dir),
        "--implementation",
        "cp",
        "--python-version",
        "3.12",
        "--only-binary=:all:",
        "--no-compile",
        "jsonschema",
        "typing_extensions",
    ]
    res = subprocess.run(pip_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[FAIL] Failed to vendor jsonschema: {res.stderr}")
        sys.exit(1)

    # 4. Create ZIP archive
    zip_path = DIST_DIR / "broker.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(stage_dir)
                zf.write(file_path, str(archive_name))

    print(f"[PACKAGED] {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    return zip_path, stage_dir


def stage_diagnostics():
    """Stages and packages blastgate-diagnostics."""
    stage_dir = DIST_DIR / "staging_diagnostics"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy diagnostics python sources
    src_diag = SRC_DIR / "diagnostics"
    for py_file in src_diag.glob("*.py"):
        shutil.copy2(py_file, stage_dir / py_file.name)

    # 2. Stage telemetry from single source of truth (SRC_DIR / telemetry)
    telemetry_target = stage_dir / "telemetry"
    telemetry_target.mkdir(parents=True, exist_ok=True)
    src_telemetry = SRC_DIR / "telemetry"
    for py_file in src_telemetry.glob("*.py"):
        shutil.copy2(py_file, telemetry_target / py_file.name)

    # 3. Create ZIP archive
    zip_path = DIST_DIR / "diagnostics.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(stage_dir)
                zf.write(file_path, str(archive_name))

    print(f"[PACKAGED] {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    return zip_path, stage_dir


def stage_watchdog():
    """Stages and packages blastgate-watchdog."""
    stage_dir = DIST_DIR / "staging_watchdog"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy watchdog python sources
    src_watch = SRC_DIR / "watchdog"
    for py_file in src_watch.glob("*.py"):
        shutil.copy2(py_file, stage_dir / py_file.name)

    # 2. Stage telemetry from single source of truth
    telemetry_target = stage_dir / "telemetry"
    telemetry_target.mkdir(parents=True, exist_ok=True)
    src_telemetry = SRC_DIR / "telemetry"
    for py_file in src_telemetry.glob("*.py"):
        shutil.copy2(py_file, telemetry_target / py_file.name)

    # 3. Create ZIP archive
    zip_path = DIST_DIR / "watchdog.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(stage_dir)
                zf.write(file_path, str(archive_name))

    print(f"[PACKAGED] {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    return zip_path, stage_dir


def stage_incidents():
    """Stages and packages blastgate-incident-ingestion."""
    stage_dir = DIST_DIR / "staging_incidents"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy incidents python sources
    src_inc = SRC_DIR / "incidents"
    for py_file in src_inc.glob("*.py"):
        shutil.copy2(py_file, stage_dir / py_file.name)

    # 2. Create ZIP archive
    zip_path = DIST_DIR / "incident_ingestion.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(stage_dir)
                zf.write(file_path, str(archive_name))

    print(f"[PACKAGED] {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    return zip_path, stage_dir


def stage_dispatcher():
    """Stages and packages blastgate-harness-dispatcher."""
    stage_dir = DIST_DIR / "staging_dispatcher"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy dispatcher python sources
    src_disp = SRC_DIR / "dispatcher"
    for py_file in src_disp.glob("*.py"):
        shutil.copy2(py_file, stage_dir / py_file.name)

    # 2. Create ZIP archive
    zip_path = DIST_DIR / "dispatcher.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(stage_dir)
                zf.write(file_path, str(archive_name))

    print(f"[PACKAGED] {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
    return zip_path, stage_dir


def inspect_and_verify_archive(zip_path: Path, expected_files: list, required_modules: list):
    """Inspects ZIP contents and verifies required files exist."""
    assert zip_path.exists(), f"Missing archive: {zip_path}"
    with zipfile.ZipFile(zip_path, "r") as zf:
        file_list = zf.namelist()

    # Check expected files
    for exp in expected_files:
        assert exp in file_list, f"Archive {zip_path.name} is missing expected file: {exp}"

    # Check required modules/dirs
    for req in required_modules:
        found = any(f.startswith(req) for f in file_list)
        assert found, f"Archive {zip_path.name} is missing module/directory: {req}"

    print(f"[VERIFIED] {zip_path.name}: {len(file_list)} files checked, all requirements present.")


def main():
    print("=" * 60)
    print("BLASTGATE LAMBDA PACKAGING & DEPENDENCY AUDIT")
    print("=" * 60)

    clean_and_prepare_dist()

    # Build all 5 genuine archives
    broker_zip, _ = stage_broker()
    diag_zip, _ = stage_diagnostics()
    watch_zip, _ = stage_watchdog()
    inc_zip, _ = stage_incidents()
    disp_zip, _ = stage_dispatcher()

    print("\n--- ARCHIVE INSPECTIONS ---")
    # Verify broker
    inspect_and_verify_archive(
        broker_zip,
        expected_files=[
            "handler.py",
            "models.py",
            "catalog.py",
            "contracts/remediation_request.schema.json",
            "contracts/action_catalog.json",
            "telemetry/heartbeat_repository.py",
            "telemetry/validator.py",
        ],
        required_modules=["jsonschema/", "attrs/", "rpds/", "telemetry/", "typing_extensions.py"],
    )

    # Verify Linux .so exists in rpds
    with zipfile.ZipFile(broker_zip, "r") as zf:
        rpds_so = [f for f in zf.namelist() if "rpds" in f and f.endswith(".so")]
        assert len(rpds_so) > 0, "Missing Linux x86_64 .so binary for rpds in broker.zip"
        print(f"[VERIFIED] rpds Linux binary in broker.zip: {rpds_so[0]}")

    # Verify diagnostics
    inspect_and_verify_archive(
        diag_zip,
        expected_files=["handler.py", "incident_reader.py", "telemetry/models.py", "telemetry/validator.py"],
        required_modules=["telemetry/"],
    )

    # Verify watchdog
    inspect_and_verify_archive(
        watch_zip,
        expected_files=["handler.py", "inventory.py", "evaluator.py", "telemetry/models.py", "telemetry/validator.py"],
        required_modules=["telemetry/"],
    )

    # Verify incidents
    inspect_and_verify_archive(
        inc_zip,
        expected_files=["handler.py", "validator.py", "deduplication.py", "models.py"],
        required_modules=["models.py"],
    )

    # Verify dispatcher
    inspect_and_verify_archive(
        disp_zip,
        expected_files=["handler.py", "lock.py", "config.py"],
        required_modules=["handler.py"],
    )

    print("\n[SUCCESS] ALL 5 LAMBDA PACKAGES BUILT, STAGED, AND VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
