#!/usr/bin/env python3
"""
BlastGate AWS CDK Application Entrypoint
Synthesizes all modular infrastructure stacks for the BlastGate sandbox environment.
"""

import sys
from pathlib import Path
import aws_cdk as cdk

# Add cdk directory to path
CDK_DIR = Path(__file__).resolve().parent
if str(CDK_DIR) not in sys.path:
    sys.path.insert(0, str(CDK_DIR))

from config import (
    AWS_ACCOUNT,
    AWS_REGION,
    STANDARD_TAGS,
)
from stacks.network_stack import NetworkStack
from stacks.storage_stack import StorageStack
from stacks.monitoring_stack import MonitoringStack
from stacks.iam_stack import IamStack
from stacks.worker_stack import WorkerStack
from stacks.broker_stack import BrokerStack

app = cdk.App(outdir=str(CDK_DIR / "cdk.out"))
env = cdk.Environment(account=AWS_ACCOUNT, region=AWS_REGION)

# 1. Network Stack (Isolated VPC, 0 NAT Gateways)
network_stack = NetworkStack(
    app,
    "BlastGateNetworkStack",
    env=env,
    description="BlastGate Sandbox isolated VPC and network security boundaries"
)

# 2. Storage Stack (Separated State and Audit DynamoDB Tables)
storage_stack = StorageStack(
    app,
    "BlastGateStorageStack",
    env=env,
    description="BlastGate DynamoDB state coordination and append-only audit tables"
)

# 3. Monitoring Stack (CloudWatch Log Groups with 14-day cost-controlled retention)
monitoring_stack = MonitoringStack(
    app,
    "BlastGateMonitoringStack",
    env=env,
    description="BlastGate CloudWatch log groups and monitoring boundaries"
)

# 4. IAM Stack (Strict Role Segregation & Least-Privilege Policies)
iam_stack = IamStack(
    app,
    "BlastGateIamStack",
    env=env,
    description="BlastGate least-privilege IAM roles with zero direct agent mutation rights"
)

# 5. Worker Stack (ECS Fargate Sandbox Cluster & Service with desiredCount = 0)
worker_stack = WorkerStack(
    app,
    "BlastGateWorkerStack",
    vpc=network_stack.vpc,
    security_group=network_stack.worker_security_group,
    execution_role=iam_stack.worker_execution_role,
    task_role=iam_stack.worker_task_role,
    log_group=monitoring_stack.worker_log_group,
    env=env,
    description="BlastGate ECS Fargate sandbox service with initial desiredCount = 0"
)
worker_stack.add_stack_dependency(network_stack)
worker_stack.add_stack_dependency(iam_stack)
worker_stack.add_stack_dependency(monitoring_stack)

# 6. Broker Stack (Independent Lambda Remediation Broker & Diagnostics)
broker_stack = BrokerStack(
    app,
    "BlastGateBrokerStack",
    broker_role=iam_stack.broker_role,
    diagnostics_role=iam_stack.diagnostics_role,
    watchdog_role=iam_stack.watchdog_role,
    incident_ingestion_role=iam_stack.incident_ingestion_role,
    dispatcher_role=iam_stack.dispatcher_role,
    log_group=monitoring_stack.broker_log_group,
    alarm_arn=monitoring_stack.worker_stalled_alarm.alarm_arn,
    env=env,
    description="BlastGate independent deterministic Lambda Remediation Broker and Diagnostics"
)
broker_stack.add_stack_dependency(storage_stack)
broker_stack.add_stack_dependency(iam_stack)
broker_stack.add_stack_dependency(monitoring_stack)

# Apply Standard Tags across all stacks
for key, value in STANDARD_TAGS.items():
    cdk.Tags.of(app).add(key, value)

if __name__ == "__main__":
    app.synth()
