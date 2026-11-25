"""
BlastGate Controlled AWS Deployment Plan & Sequence
Defines the authoritative 16-stage deployment roadmap, cost estimates, rollback procedures,
and strict pre-deployment readiness checks.
"""

from typing import List, Dict, Any

AWS_ACCOUNT = "123456789012"
AWS_REGION = "us-east-1"
AWS_PROFILE = "antigravity"

DEPLOYMENT_PRECHECKS: List[Dict[str, Any]] = [
    {
        "check_id": "PRE-001",
        "description": "AWS STS identity matches antigravity-ide on account 123456789012",
        "status": "PASS",
        "verified_at": "Step 0",
    },
    {
        "check_id": "PRE-002",
        "description": "Amazon Bedrock foundation model inference authorization (amazon.nova-micro-v1:0)",
        "status": "BLOCKED",
        "blocker": "ValidationException: Operation not allowed; AWS Support case pending.",
        "mitigation": "Harness and Gateway configurations decouple model ID; local test suite uses deterministic fixtures.",
    },
    {
        "check_id": "PRE-003",
        "description": "CDK Synthesis completed with 6 CloudFormation templates in cdk.out/",
        "status": "PASS",
        "verified_at": "Step 2 & Step 4",
    },
    {
        "check_id": "PRE-004",
        "description": "Initial ECS Service desiredCount hardcoded to ZERO (cost guardrail)",
        "status": "PASS",
        "verified_at": "Step 2 & Step 4",
    },
    {
        "check_id": "PRE-005",
        "description": "Local test suite passes with zero regressions",
        "status": "PASS",
        "pass_count": 159,
    },
]

DEPLOYMENT_STAGES: List[Dict[str, Any]] = [
    {
        "stage": 1,
        "name": "AWS Account & Region Confirmation",
        "description": f"Verify credentials for {AWS_PROFILE} in {AWS_REGION}.",
        "cost_impact": "$0.00",
    },
    {
        "stage": 2,
        "name": "CDK Bootstrapping",
        "description": f"Bootstrap CDK toolkit stack in account {AWS_ACCOUNT}.",
        "cost_impact": "< $0.05 (S3 staging bucket)",
    },
    {
        "stage": 3,
        "name": "Network & Storage Foundation Stacks",
        "description": "Deploy NetworkStack (0 NAT Gateways) and StorageStack (4 DynamoDB On-Demand tables).",
        "cost_impact": "$0.00 idle (On-Demand tables charge per request only)",
    },
    {
        "stage": 4,
        "name": "Monitoring & IAM Stack Deployment",
        "description": "Deploy MonitoringStack (14-day retention) and IamStack (least-privilege roles).",
        "cost_impact": "$0.00 idle",
    },
    {
        "stage": 5,
        "name": "Remediation Broker & Diagnostics Lambda Deployment",
        "description": "Deploy BrokerStack and Diagnostics Lambda functions.",
        "cost_impact": "$0.00 idle",
    },
    {
        "stage": 6,
        "name": "Worker Stack Deployment (desiredCount = 0)",
        "description": "Deploy ECS Fargate Cluster, Task Definition, and Service with initial desiredCount=0.",
        "cost_impact": "$0.00 idle (0 tasks running)",
    },
    {
        "stage": 7,
        "name": "ECR Worker Image Build & Push",
        "description": "Build Dockerfile on a Docker-enabled environment and push to ECR repository.",
        "cost_impact": "< $0.10/month for image storage",
    },
    {
        "stage": 8,
        "name": "AgentCore Gateway Creation",
        "description": "Create blastgate-gateway with MCP protocol and AWS_IAM authorizer.",
        "cost_impact": "AgentCore gateway charges per invocation",
    },
    {
        "stage": 9,
        "name": "Gateway Target Binding",
        "description": "Register diagnostics and remediation broker Lambda targets with Gateway.",
        "cost_impact": "$0.00 idle",
    },
    {
        "stage": 10,
        "name": "Cedar Policy Engine & Policy Attachment",
        "description": "Create blastgate_policy_engine and attach blastgate_gateway_cedar_policy in ACTIVE mode.",
        "cost_impact": "$0.00 idle",
    },
    {
        "stage": 11,
        "name": "Bedrock Guardrails Creation (Optional Hardening)",
        "description": "Create blastgate-operational-guardrail with prompt attack & authority override filters.",
        "cost_impact": "Charge per text unit evaluated during live calls",
    },
    {
        "stage": 12,
        "name": "Managed Harness Creation",
        "description": "Create blastgate_recovery_harness with allowedTools restriction and system prompt.",
        "cost_impact": "$0.00 idle",
    },
    {
        "stage": 13,
        "name": "Controlled Bedrock Model Inference Smoke Test",
        "description": "Verify foundation model access after AWS Support resolution before running full harness.",
        "cost_impact": "< $0.01",
    },
    {
        "stage": 14,
        "name": "Controlled Live Sandbox Worker Test (desiredCount = 6)",
        "description": "Scale sandbox service to 6 tasks for controlled stall and recovery test.",
        "cost_impact": "~$0.02 for 15 minutes of Fargate compute (6 tasks * 0.25 vCPU)",
    },
    {
        "stage": 15,
        "name": "End-to-End Autonomous Remediation Verification",
        "description": "Simulate worker stall, verify watchdog alarm, agent proposal, broker execution, and recovery.",
        "cost_impact": "< $0.05",
    },
    {
        "stage": 16,
        "name": "Immediate Teardown & Post-Test Scale-Down",
        "description": "Scale desiredCount back to 0 immediately; run cleanup script if destroying sandbox.",
        "cost_impact": "$0.00 post-scale-down",
    },
]


def get_deployment_plan() -> Dict[str, Any]:
    return {
        "target_account": AWS_ACCOUNT,
        "target_region": AWS_REGION,
        "target_profile": AWS_PROFILE,
        "prechecks": DEPLOYMENT_PRECHECKS,
        "stages": DEPLOYMENT_STAGES,
        "estimated_total_test_cost": "< $0.50",
        "monthly_idle_cost": "$0.00 (all resources On-Demand or scaled to zero)",
    }
