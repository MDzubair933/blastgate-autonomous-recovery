"""
BlastGate Watchdog Configuration
"""

import os

CLOUDWATCH_NAMESPACE = os.environ.get("CLOUDWATCH_NAMESPACE", "BlastGate/Workers")
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "blastgate-sandbox")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "blastgate-workers")
HEARTBEAT_TABLE_NAME = os.environ.get("HEARTBEAT_TABLE_NAME", "blastgate-heartbeats")
INCIDENT_TABLE_NAME = os.environ.get("INCIDENT_TABLE_NAME", "blastgate-incidents")
STALLED_METRIC_NAME = "ConfirmedStalledWorkerCount"
METRIC_EVALUATION_WINDOW_SECONDS = int(os.environ.get("METRIC_EVALUATION_WINDOW_SECONDS", "60"))
