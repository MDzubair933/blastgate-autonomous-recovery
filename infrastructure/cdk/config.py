"""
BlastGate Infrastructure Configuration Module
Centralized, environment-aware configuration for AWS CDK deployment.
"""

from typing import Dict

# Project Identity & Scoping
APP_PREFIX: str = "blastgate"
ENVIRONMENT: str = "sandbox"
AWS_ACCOUNT: str = "123456789012"
AWS_REGION: str = "us-east-1"

# Compute & Sandbox Configuration
CLUSTER_NAME: str = f"{APP_PREFIX}-{ENVIRONMENT}"
SERVICE_NAME: str = f"{APP_PREFIX}-workers"
TASK_FAMILY: str = f"{APP_PREFIX}-worker"

# Strict Cost Control: Initial deployed task count is ZERO
INITIAL_DESIRED_COUNT: int = 0
REFERENCE_DESIRED_COUNT: int = 6
MIN_HEALTHY_TASKS: int = 4
MAX_UNAVAILABLE_PERCENT: float = 20.0
COOLDOWN_WINDOW_SECONDS: int = 600

# Storage Resource Identifiers
STATE_TABLE_NAME: str = f"{APP_PREFIX}-state"
AUDIT_TABLE_NAME: str = f"{APP_PREFIX}-audit"
HEARTBEAT_TABLE_NAME: str = f"{APP_PREFIX}-heartbeats"
INCIDENT_TABLE_NAME: str = f"{APP_PREFIX}-incidents"

# Broker Lambda Identifiers
BROKER_FUNCTION_NAME: str = f"{APP_PREFIX}-remediation-broker"
BROKER_RUNTIME_PYTHON: str = "python3.12"

# Network Configuration
VPC_CIDR: str = "10.50.0.0/24"
MAX_AZS: int = 2

# Standard Project Resource Tags
STANDARD_TAGS: Dict[str, str] = {
    "Project": "BlastGate",
    "Environment": ENVIRONMENT,
    "ManagedBy": "AWS-CDK",
    "Hackathon": "AWS-Builder-Center-Bedrock-Agents",
    "CostCenter": "BlastGate-Sandbox"
}
