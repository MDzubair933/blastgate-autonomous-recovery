"""
BlastGate Broker & Diagnostics Stack
Deploys the independent deterministic AWS Lambda Remediation Broker,
read-only Diagnostics microservice, Watchdog evaluator, and Incident Ingestion pipeline.
"""

from pathlib import Path
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_events as events,
    aws_events_targets as targets,
    aws_sqs as sqs,
    CfnOutput,
)
from constructs import Construct
from config import (
    APP_PREFIX,
    BROKER_FUNCTION_NAME,
    STATE_TABLE_NAME,
    AUDIT_TABLE_NAME,
    HEARTBEAT_TABLE_NAME,
    INCIDENT_TABLE_NAME,
    CLUSTER_NAME,
    SERVICE_NAME,
    COOLDOWN_WINDOW_SECONDS,
    MIN_HEALTHY_TASKS,
    MAX_UNAVAILABLE_PERCENT,
)

HACKATHON_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DIST_LAMBDA_DIR = HACKATHON_ROOT / "dist" / "lambda"

# Use validated, self-contained deployment packages if staged, otherwise source directory
SRC_BROKER_DIR = str(DIST_LAMBDA_DIR / "broker.zip") if (DIST_LAMBDA_DIR / "broker.zip").exists() else str(HACKATHON_ROOT / "src" / "broker")
SRC_DIAGNOSTICS_DIR = str(DIST_LAMBDA_DIR / "diagnostics.zip") if (DIST_LAMBDA_DIR / "diagnostics.zip").exists() else str(HACKATHON_ROOT / "src" / "diagnostics")
SRC_WATCHDOG_DIR = str(DIST_LAMBDA_DIR / "watchdog.zip") if (DIST_LAMBDA_DIR / "watchdog.zip").exists() else str(HACKATHON_ROOT / "src" / "watchdog")
SRC_INCIDENTS_DIR = str(DIST_LAMBDA_DIR / "incident_ingestion.zip") if (DIST_LAMBDA_DIR / "incident_ingestion.zip").exists() else str(HACKATHON_ROOT / "src" / "incidents")
SRC_DISPATCHER_DIR = str(DIST_LAMBDA_DIR / "dispatcher.zip") if (DIST_LAMBDA_DIR / "dispatcher.zip").exists() else str(HACKATHON_ROOT / "src" / "dispatcher")


class BrokerStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        broker_role: iam.IRole,
        diagnostics_role: iam.IRole,
        log_group: logs.ILogGroup,
        alarm_arn: str = "",
        watchdog_role: iam.IRole = None,
        incident_ingestion_role: iam.IRole = None,
        dispatcher_role: iam.IRole = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        wd_role = watchdog_role or diagnostics_role
        inc_role = incident_ingestion_role or diagnostics_role
        disp_role = dispatcher_role or diagnostics_role

        # -----------------------------------------------------------------
        # 1. Sovereign Remediation Broker Lambda Function
        # -----------------------------------------------------------------
        self.broker_function = _lambda.Function(
            self,
            "RemediationBrokerFunction",
            function_name=BROKER_FUNCTION_NAME,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(SRC_BROKER_DIR),
            role=broker_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=log_group,
            environment={
                "STATE_TABLE_NAME": STATE_TABLE_NAME,
                "AUDIT_TABLE_NAME": AUDIT_TABLE_NAME,
                "HEARTBEAT_TABLE_NAME": HEARTBEAT_TABLE_NAME,
                "CLUSTER_NAME": CLUSTER_NAME,
                "SERVICE_NAME": SERVICE_NAME,
                "COOLDOWN_WINDOW_SECONDS": str(COOLDOWN_WINDOW_SECONDS),
                "MIN_HEALTHY_TASKS": str(MIN_HEALTHY_TASKS),
                "MAX_UNAVAILABLE_PERCENT": str(MAX_UNAVAILABLE_PERCENT),
            }
        )

        # Allow AgentCore Gateway to invoke Broker Lambda
        self.broker_function.add_permission(
            "AllowAgentCoreGatewayInvokeBroker",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction"
        )

        # -----------------------------------------------------------------
        # 2. Read-Only Diagnostics Microservice Lambda Function
        # -----------------------------------------------------------------
        self.diagnostics_function = _lambda.Function(
            self,
            "DiagnosticsFunction",
            function_name=f"{APP_PREFIX}-diagnostics",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(SRC_DIAGNOSTICS_DIR),
            role=diagnostics_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=log_group,
            environment={
                "INCIDENT_TABLE_NAME": INCIDENT_TABLE_NAME,
                "HEARTBEAT_TABLE_NAME": HEARTBEAT_TABLE_NAME,
                "CLUSTER_NAME": CLUSTER_NAME,
            }
        )

        # Allow AgentCore Gateway to invoke Diagnostics Lambda
        self.diagnostics_function.add_permission(
            "AllowAgentCoreGatewayInvokeDiagnostics",
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            action="lambda:InvokeFunction"
        )

        # -----------------------------------------------------------------
        # 3. CloudWatch Watchdog Evaluator Lambda Function
        # -----------------------------------------------------------------
        self.watchdog_function = _lambda.Function(
            self,
            "WatchdogFunction",
            function_name=f"{APP_PREFIX}-watchdog",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(SRC_WATCHDOG_DIR),
            role=wd_role,
            timeout=Duration.seconds(60),
            memory_size=256,
            log_group=log_group,
            environment={
                "CLUSTER_NAME": CLUSTER_NAME,
                "SERVICE_NAME": SERVICE_NAME,
                "HEARTBEAT_TABLE_NAME": HEARTBEAT_TABLE_NAME,
                "INCIDENT_TABLE_NAME": INCIDENT_TABLE_NAME,
            }
        )

        # Watchdog Execution Schedule: Rate of 1 minute
        self.watchdog_schedule_rule = events.Rule(
            self,
            "WatchdogScheduleRule",
            rule_name=f"{APP_PREFIX}-watchdog-schedule",
            description="Executes BlastGate Watchdog health evaluation every 1 minute",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(self.watchdog_function)]
        )

        # -----------------------------------------------------------------
        # 4. Incident Ingestion Pipeline Lambda Function
        # -----------------------------------------------------------------
        self.incident_ingestion_function = _lambda.Function(
            self,
            "IncidentIngestionFunction",
            function_name=f"{APP_PREFIX}-incident-ingestion",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(SRC_INCIDENTS_DIR),
            role=inc_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=log_group,
            environment={
                "INCIDENT_TABLE_NAME": INCIDENT_TABLE_NAME,
                "HEARTBEAT_TABLE_NAME": HEARTBEAT_TABLE_NAME,
                "CLUSTER_NAME": CLUSTER_NAME,
            }
        )

        # Incident EventBridge Rule: Triggers on CloudWatch Alarm State Changes
        self.incident_alarm_rule = events.Rule(
            self,
            "IncidentAlarmRule",
            rule_name=f"{APP_PREFIX}-alarm-state-change-rule",
            description="Captures CloudWatch worker alarm transitions and registers incidents",
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={
                    "alarmName": [f"{APP_PREFIX}-worker-stalled-alarm"],
                    "state": {
                        "value": ["ALARM", "OK"]
                    }
                }
            ),
            targets=[targets.LambdaFunction(self.incident_ingestion_function)]
        )

        # -----------------------------------------------------------------
        # 5. Closed-Loop Harness Dispatcher Lambda Function
        # -----------------------------------------------------------------
        self.dispatcher_function = _lambda.Function(
            self,
            "HarnessDispatcherFunction",
            function_name=f"{APP_PREFIX}-harness-dispatcher",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(SRC_DISPATCHER_DIR),
            role=disp_role,
            timeout=Duration.seconds(60),
            memory_size=256,
            log_group=log_group,
            environment={
                "STATE_TABLE_NAME": STATE_TABLE_NAME,
                "HARNESS_ARN": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:harness/blastgate_recovery_harness-example",
                "CLUSTER_NAME": CLUSTER_NAME,
            }
        )

        # -----------------------------------------------------------------
        # 5b. Dispatcher Dead Letter Queue (DLQ)
        # References pre-provisioned blastgate-dispatch-dlq (14-day retention, SSE)
        # -----------------------------------------------------------------
        self.dispatch_dlq = sqs.Queue.from_queue_arn(
            self,
            "DispatchDeadLetterQueue",
            f"arn:aws:sqs:{self.region}:{self.account}:{APP_PREFIX}-dispatch-dlq"
        )

        # Dispatcher EventBridge Rule: Triggers on BlastGate.IncidentOpened
        self.incident_dispatch_rule = events.Rule(
            self,
            "IncidentDispatchRule",
            rule_name=f"{APP_PREFIX}-incident-dispatch-rule",
            description="Dispatches opened BlastGate incidents to AgentCore Managed Harness with atomic deduplication",
            event_pattern=events.EventPattern(
                source=["blastgate.incidents"],
                detail_type=["BlastGate.IncidentOpened"],
            ),
            targets=[targets.LambdaFunction(
                self.dispatcher_function,
                max_event_age=Duration.minutes(15),
                retry_attempts=0,
                dead_letter_queue=self.dispatch_dlq,
            )]
        )

        # -----------------------------------------------------------------
        # Stack Outputs
        # -----------------------------------------------------------------
        CfnOutput(
            self,
            "DispatchDlqArnOutput",
            value=self.dispatch_dlq.queue_arn,
            description="BlastGate Dispatcher Dead Letter Queue ARN",
            export_name=f"{APP_PREFIX}-dispatch-dlq-arn"
        )
        CfnOutput(
            self,
            "BrokerFunctionArnOutput",
            value=self.broker_function.function_arn,
            description="BlastGate Remediation Broker Function ARN",
            export_name=f"{APP_PREFIX}-broker-function-arn"
        )
        CfnOutput(
            self,
            "DiagnosticsFunctionArnOutput",
            value=self.diagnostics_function.function_arn,
            description="BlastGate Diagnostics Function ARN",
            export_name=f"{APP_PREFIX}-diagnostics-function-arn"
        )
        CfnOutput(
            self,
            "WatchdogFunctionArnOutput",
            value=self.watchdog_function.function_arn,
            description="BlastGate Watchdog Function ARN",
            export_name=f"{APP_PREFIX}-watchdog-function-arn"
        )
        CfnOutput(
            self,
            "IncidentIngestionFunctionArnOutput",
            value=self.incident_ingestion_function.function_arn,
            description="BlastGate Incident Ingestion Function ARN",
            export_name=f"{APP_PREFIX}-incident-ingestion-function-arn"
        )
        CfnOutput(
            self,
            "DispatcherFunctionArnOutput",
            value=self.dispatcher_function.function_arn,
            description="BlastGate Harness Dispatcher Function ARN",
            export_name=f"{APP_PREFIX}-dispatcher-function-arn"
        )
