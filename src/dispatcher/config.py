"""
Configuration constants for BlastGate Harness Dispatcher.
"""

import os

STATE_TABLE_NAME = os.environ.get("STATE_TABLE_NAME", "blastgate-state")
HARNESS_ARN = os.environ.get(
    "HARNESS_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/blastgate_recovery_harness-example",
)
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "blastgate-sandbox")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
LOCK_TTL_SECONDS = int(os.environ.get("LOCK_TTL_SECONDS", "86400"))
COOLDOWN_WINDOW_SECONDS = int(os.environ.get("COOLDOWN_WINDOW_SECONDS", "600"))
