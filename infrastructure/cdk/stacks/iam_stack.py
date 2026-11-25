"""
BlastGate IAM Stack
Defines least-privilege, segregated IAM roles and policies for all runtime actors.
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct
from config import (
    APP_PREFIX,
    AWS_ACCOUNT,
    AWS_REGION,
    CLUSTER_NAME,
    STATE_TABLE_NAME,
    AUDIT_TABLE_NAME,
    HEARTBEAT_TABLE_NAME,
    INCIDENT_TABLE_NAME,
)


class IamStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Apply enforceable permissions boundary to every BlastGate runtime IAM role
        # Prevents privilege escalation even via inline Policy updates.
        runtime_boundary = iam.ManagedPolicy.from_managed_policy_name(
            self, "BlastGateRuntimeBoundary", "BlastGateRuntimeBoundary"
        )
        iam.PermissionsBoundary.of(self).apply(runtime_boundary)

        # ---------------------------------------------------------------------
        # 1. BlastGate AgentCore Execution Role (Diagnostic & Proposal Only)
        # ---------------------------------------------------------------------
        # Strictly PROHIBITS direct ECS mutations, IAM admin, shell execution, and InvokeAgentRuntimeCommand
        self.agent_role = iam.Role(
            self,
            "AgentRole",
            role_name=f"{APP_PREFIX}-agent-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            ),
            description="BlastGate Bedrock AgentCore execution role with zero infrastructure mutation authority"
        )
        self.harness_role = self.agent_role  # Alias for Managed Harness

        self.agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowBedrockModelInvocation",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ApplyGuardrail"
                ],
                resources=[
                    f"arn:aws:bedrock:{AWS_REGION}::foundation-model/*",
                    f"arn:aws:bedrock:{AWS_REGION}:{AWS_ACCOUNT}:inference-profile/*",
                    f"arn:aws:bedrock:{AWS_REGION}:{AWS_ACCOUNT}:guardrail/*"
                ]
            )
        )
        self.agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowScopedGatewayInvocationOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeGateway"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:gateway/{APP_PREFIX}-gateway*"
                ]
            )
        )
        self.agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowHarnessLogging",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/*:log-stream:*",
                    f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/bedrock-agentcore/*:log-stream:*",
                ]
            )
        )

        # ---------------------------------------------------------------------
        # 2. BlastGate AgentCore Gateway Role
        # ---------------------------------------------------------------------
        # Invokes authorized diagnostics and broker Lambda targets, and queries Policy Engine
        self.gateway_role = iam.Role(
            self,
            "GatewayRole",
            role_name=f"{APP_PREFIX}-gateway-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="BlastGate AgentCore Gateway role authorized to invoke broker and diagnostics Lambda only"
        )
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowScopedGatewayLambdaTargetsOnly",
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{APP_PREFIX}-remediation-broker",
                    f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{APP_PREFIX}-diagnostics",
                ]
            )
        )
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowPolicyEngineOperations",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:AuthorizeAction",
                    "bedrock-agentcore:PartiallyAuthorizeActions",
                    "bedrock-agentcore:GetPolicyEngine"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:gateway/{APP_PREFIX}-gateway*",
                    f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:policy-engine/{APP_PREFIX}_policy_engine*"
                ]
            )
        )

        # ---------------------------------------------------------------------
        # 3. BlastGate Read-Only Diagnostics Role
        # ---------------------------------------------------------------------
        # Read-only inspection of CloudWatch metrics and ECS tasks
        self.diagnostics_role = iam.Role(
            self,
            "DiagnosticsRole",
            role_name=f"{APP_PREFIX}-diagnostics-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="BlastGate diagnostics role for read-only inspection of sandbox telemetry"
        )
        self.diagnostics_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowReadOnlyDiagnostics",
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:GetMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "ecs:DescribeServices",
                    "ecs:DescribeTasks",
                    "ecs:ListTasks"
                ],
                resources=["*"]
            )
        )
        self.diagnostics_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDiagnosticsLogGroupFilter",
                effect=iam.Effect.ALLOW,
                actions=["logs:FilterLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/*"]
            )
        )
        self.diagnostics_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDiagnosticsLogStreamRead",
                effect=iam.Effect.ALLOW,
                actions=["logs:GetLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/*:log-stream:*"]
            )
        )
        self.diagnostics_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDiagnosticsDataReads",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=[
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{INCIDENT_TABLE_NAME}",
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"
                ]
            )
        )

        # ---------------------------------------------------------------------
        # 4. BlastGate Lambda Remediation Broker Execution Role (The Sovereign Boundary)
        # ---------------------------------------------------------------------
        # Holds the strictly scoped mutation permission. Rejects IAM, RDS, and arbitrary compute.
        self.broker_role = iam.Role(
            self,
            "BrokerRole",
            role_name=f"{APP_PREFIX}-broker-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="BlastGate independent remediation broker execution role holding scoped StopTask authority"
        )

        # Scoped ECS Inspection and Mutation
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowSandboxEcsInspection",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:DescribeServices",
                    "ecs:DescribeTasks",
                    "ecs:ListTasks"
                ],
                resources=["*"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": f"arn:aws:ecs:{AWS_REGION}:{AWS_ACCOUNT}:cluster/{CLUSTER_NAME}"
                    }
                }
            )
        )
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowScopedStopTaskOnSandboxOnly",
                effect=iam.Effect.ALLOW,
                actions=["ecs:StopTask"],
                resources=[f"arn:aws:ecs:{AWS_REGION}:{AWS_ACCOUNT}:task/{CLUSTER_NAME}/*"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": f"arn:aws:ecs:{AWS_REGION}:{AWS_ACCOUNT}:cluster/{CLUSTER_NAME}"
                    }
                }
            )
        )

        # DynamoDB State Management (Conditional Update for Cooldown Lock)
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowStateCoordination",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:PutItem"
                ],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{STATE_TABLE_NAME}"]
            )
        )

        # DynamoDB Heartbeat Inspection (Rule R3 Verified Health Telemetry)
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowBrokerHeartbeatReadOnly",
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem"],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"]
            )
        )

        # DynamoDB Audit Storage (PutItem Only, Delete/Update Denied)
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowAuditPutItemOnly",
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:PutItem"],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{AUDIT_TABLE_NAME}"]
            )
        )
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="DenyAuditModifications",
                effect=iam.Effect.DENY,
                actions=[
                    "dynamodb:DeleteItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:BatchWriteItem"
                ],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{AUDIT_TABLE_NAME}"]
            )
        )

        # CloudWatch Logging
        self.broker_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowBrokerCloudWatchLogs",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/broker:log-stream:*"]
            )
        )

        # ---------------------------------------------------------------------
        # 5. BlastGate ECS Worker Execution & Task Roles
        # ---------------------------------------------------------------------
        # Zero remediation permissions. Allows pulling images and logging only.
        self.worker_execution_role = iam.Role(
            self,
            "WorkerExecutionRole",
            role_name=f"{APP_PREFIX}-worker-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="BlastGate Fargate task execution role for image pulling and log routing"
        )
        self.worker_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowEcrAuthToken",
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"]
            )
        )
        self.worker_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowScopedEcrPull",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                resources=[f"arn:aws:ecr:{AWS_REGION}:{AWS_ACCOUNT}:repository/{APP_PREFIX}-*"]
            )
        )
        self.worker_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWorkerExecutionLogs",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/workers:log-stream:*"]
            )
        )

        self.worker_task_role = iam.Role(
            self,
            "WorkerTaskRole",
            role_name=f"{APP_PREFIX}-worker-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="BlastGate worker application task role with zero infrastructure authority"
        )
        self.worker_task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWorkerTelemetryEmissionOnly",
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "BlastGate/Workers"
                    }
                }
            )
        )
        self.worker_task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWorkerLogEvents",
                effect=iam.Effect.ALLOW,
                actions=["logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/workers:log-stream:*"]
            )
        )
        self.worker_task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWorkerHeartbeatPublication",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:PutItem"
                ],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"]
            )
        )
        self.worker_task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowScopedFaultInjectionSignalRead",
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem"],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"],
                conditions={
                    "ForAllValues:StringEquals": {
                        "dynamodb:LeadingKeys": ["CONTROL#FAULT_INJECTION"]
                    }
                }
            )
        )

        # ---------------------------------------------------------------------
        # 5b. BlastGate Watchdog & Incident Ingestion Roles
        # ---------------------------------------------------------------------
        self.watchdog_role = iam.Role(
            self,
            "WatchdogRole",
            role_name=f"{APP_PREFIX}-watchdog-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="BlastGate Watchdog role for health evaluation and CloudWatch metric emission"
        )
        self.watchdog_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWatchdogEcsAndHeartbeatRead",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:DescribeServices",
                    "ecs:ListTasks"
                ],
                resources=["*"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": f"arn:aws:ecs:{AWS_REGION}:{AWS_ACCOUNT}:cluster/{CLUSTER_NAME}"
                    }
                }
            )
        )
        self.watchdog_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWatchdogHeartbeatLookup",
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem"],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"]
            )
        )
        self.watchdog_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWatchdogCustomMetrics",
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "BlastGate/Workers"
                    }
                }
            )
        )
        self.watchdog_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowWatchdogLogs",
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/broker:log-stream:*"]
            )
        )

        self.incident_ingestion_role = iam.Role(
            self,
            "IncidentIngestionRole",
            role_name=f"{APP_PREFIX}-incident-ingestion-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="BlastGate Incident Ingestion role for writing deduplicated incidents"
        )
        self.incident_ingestion_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowIncidentIngestionStorage",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Scan"
                ],
                resources=[
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{INCIDENT_TABLE_NAME}"
                ]
            )
        )
        self.incident_ingestion_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowIncidentHeartbeatStallLookup",
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem", "dynamodb:Scan"],
                resources=[
                    f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{HEARTBEAT_TABLE_NAME}"
                ]
            )
        )
        self.incident_ingestion_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowIncidentIngestionLogs",
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/broker:log-stream:*"]
            )
        )
        self.incident_ingestion_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowIncidentEventBridgeEmit",
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[f"arn:aws:events:{AWS_REGION}:{AWS_ACCOUNT}:event-bus/default"]
            )
        )

        # ---------------------------------------------------------------------
        # 5b. BlastGate Harness Dispatcher Lambda Role
        # ---------------------------------------------------------------------
        self.dispatcher_role = iam.Role(
            self,
            "DispatcherRole",
            role_name=f"{APP_PREFIX}-dispatcher-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="BlastGate Dispatcher role for invoking AgentCore Harness and atomic deduplication"
        )
        self.dispatcher_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDispatcherStateLock",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{STATE_TABLE_NAME}"]
            )
        )
        self.dispatcher_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDispatcherHarnessInvoke",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeHarness",
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                resources=[f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:harness/blastgate_recovery_harness*"]
            )
        )
        self.dispatcher_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDispatcherLogs",
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[f"arn:aws:logs:{AWS_REGION}:{AWS_ACCOUNT}:log-group:/aws/{APP_PREFIX}/broker:log-stream:*"]
            )
        )

        # ---------------------------------------------------------------------
        # 6. BlastGate Evidence Console Read-Only Role
        # ---------------------------------------------------------------------
        self.console_role = iam.Role(
            self,
            "ConsoleRole",
            role_name=f"{APP_PREFIX}-console-role",
            assumed_by=iam.AccountRootPrincipal(),
            description="BlastGate evidence console read-only role for audit visualization"
        )
        self.console_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowConsoleAuditQueries",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=[f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT}:table/{AUDIT_TABLE_NAME}"]
            )
        )

        # Outputs
        CfnOutput(self, "AgentRoleArnOutput", value=self.agent_role.role_arn, export_name=f"{APP_PREFIX}-agent-role-arn")
        CfnOutput(self, "GatewayRoleArnOutput", value=self.gateway_role.role_arn, export_name=f"{APP_PREFIX}-gateway-role-arn")
        CfnOutput(self, "BrokerRoleArnOutput", value=self.broker_role.role_arn, export_name=f"{APP_PREFIX}-broker-role-arn")
        CfnOutput(self, "WorkerExecutionRoleArnOutput", value=self.worker_execution_role.role_arn, export_name=f"{APP_PREFIX}-worker-exec-role-arn")
        CfnOutput(self, "WorkerTaskRoleArnOutput", value=self.worker_task_role.role_arn, export_name=f"{APP_PREFIX}-worker-task-role-arn")
        CfnOutput(self, "DispatcherRoleArnOutput", value=self.dispatcher_role.role_arn, export_name=f"{APP_PREFIX}-dispatcher-role-arn")
