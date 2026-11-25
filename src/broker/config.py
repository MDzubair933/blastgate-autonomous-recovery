"""
BlastGate Broker Central Configuration & Constants
Defines runtime defaults, sandbox boundaries, and operational thresholds.
"""

import os
from pathlib import Path

# Paths
BROKER_DIR = Path(__file__).resolve().parent
if (BROKER_DIR / "contracts").exists():
    CONTRACTS_DIR = BROKER_DIR / "contracts"
else:
    SRC_DIR = BROKER_DIR.parent
    WORKSPACE_ROOT = SRC_DIR.parent
    CONTRACTS_DIR = WORKSPACE_ROOT / "contracts"

ACTION_CATALOG_PATH = CONTRACTS_DIR / "action_catalog.json"
ACTION_CATALOG_SCHEMA_PATH = CONTRACTS_DIR / "action_catalog.schema.json"
REMEDIATION_REQUEST_SCHEMA_PATH = CONTRACTS_DIR / "remediation_request.schema.json"
DECISION_RECEIPT_SCHEMA_PATH = CONTRACTS_DIR / "decision_receipt.schema.json"
AUDIT_SCHEMA_PATH = CONTRACTS_DIR / "audit_schema.json"

# AWS Sandbox Scope Defaults
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")
DEFAULT_ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID", "123456789012")
ALLOWED_CLUSTER = os.environ.get("CLUSTER_NAME", "blastgate-sandbox")
ALLOWED_SERVICE = os.environ.get("SERVICE_NAME", "blastgate-workers")
ALLOWED_TASK_FAMILY = os.environ.get("TASK_FAMILY", "blastgate-worker")

# DynamoDB Tables
STATE_TABLE_NAME = os.environ.get("STATE_TABLE_NAME", "blastgate-state")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME", "blastgate-audit")
HEARTBEAT_TABLE_NAME = os.environ.get("HEARTBEAT_TABLE_NAME", "blastgate-heartbeats")

# Operational Invariant Defaults (R1-R8)
COOLDOWN_WINDOW_SECONDS = int(os.environ.get("COOLDOWN_WINDOW_SECONDS", "600"))
REFERENCE_DESIRED_COUNT = int(os.environ.get("REFERENCE_DESIRED_COUNT", "6"))
MIN_HEALTHY_TASKS = int(os.environ.get("MIN_HEALTHY_TASKS", "4"))
MAX_UNAVAILABLE_PERCENT = float(os.environ.get("MAX_UNAVAILABLE_PERCENT", "20.0"))
TELEMETRY_FRESHNESS_SECONDS = int(os.environ.get("TELEMETRY_FRESHNESS_SECONDS", "120"))
CLOCK_SKEW_TOLERANCE_SECONDS = int(os.environ.get("CLOCK_SKEW_TOLERANCE_SECONDS", "5"))

# Versioning
CATALOG_VERSION = "1.0.0"
POLICY_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
BROKER_ROLE_ARN = f"arn:aws:iam::{DEFAULT_ACCOUNT_ID}:role/blastgate-broker-role"
