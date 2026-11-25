"""
BlastGate Worker Configuration
"""

import os

ENVIRONMENT = os.environ.get("ENVIRONMENT", "sandbox")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "blastgate-workers")
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "blastgate-sandbox")
TASK_FAMILY = os.environ.get("TASK_FAMILY", "blastgate-worker")
HEARTBEAT_TABLE_NAME = os.environ.get("HEARTBEAT_TABLE_NAME", "blastgate-heartbeats")

# Telemetry Cadence
HEARTBEAT_INTERVAL_SECONDS = float(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "10.0"))
PROCESSOR_INTERVAL_SECONDS = float(os.environ.get("PROCESSOR_INTERVAL_SECONDS", "2.0"))
STALL_THRESHOLD_SECONDS = float(os.environ.get("STALL_THRESHOLD_SECONDS", "15.0"))

# Fault Injection (Sandbox Only, Disabled by Default)
ENABLE_FAULT_INJECTION = os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() == "true"
