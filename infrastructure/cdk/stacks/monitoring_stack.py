"""
BlastGate Monitoring Stack
Provides dedicated CloudWatch log groups with strict cost-controlled retention
and custom watchdog alarms.
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    CfnOutput,
)
from constructs import Construct
from config import APP_PREFIX, CLUSTER_NAME, SERVICE_NAME


class MonitoringStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Broker Execution Log Group (14-day retention for cost control)
        self.broker_log_group = logs.LogGroup(
            self,
            "BrokerLogGroup",
            log_group_name=f"/aws/{APP_PREFIX}/broker",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Sandbox Workers Log Group
        self.worker_log_group = logs.LogGroup(
            self,
            "WorkerLogGroup",
            log_group_name=f"/aws/{APP_PREFIX}/workers",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Audit Event Log Group (for secondary streaming & CloudWatch metric filters)
        self.audit_log_group = logs.LogGroup(
            self,
            "AuditLogGroup",
            log_group_name=f"/aws/{APP_PREFIX}/audit",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY
        )

        # CloudWatch Watchdog Alarm: Confirmed Stalled Workers >= 1 (Task 4.3)
        self.stalled_worker_metric = cloudwatch.Metric(
            namespace="BlastGate/Workers",
            metric_name="ConfirmedStalledWorkerCount",
            dimensions_map={
                "ClusterName": CLUSTER_NAME,
                "ServiceName": SERVICE_NAME,
            },
            statistic="Maximum",
            period=Duration.minutes(1)
        )

        self.worker_stalled_alarm = cloudwatch.Alarm(
            self,
            "WorkerStalledAlarm",
            alarm_name=f"{APP_PREFIX}-worker-stalled-alarm",
            alarm_description="Triggers when one or more ECS workers are confirmed STALLED while remaining RUNNING",
            metric=self.stalled_worker_metric,
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )

        CfnOutput(
            self,
            "BrokerLogGroupArnOutput",
            value=self.broker_log_group.log_group_arn,
            description="Broker Log Group ARN",
            export_name=f"{APP_PREFIX}-broker-log-group-arn"
        )
        CfnOutput(
            self,
            "WorkerLogGroupArnOutput",
            value=self.worker_log_group.log_group_arn,
            description="Worker Log Group ARN",
            export_name=f"{APP_PREFIX}-worker-log-group-arn"
        )
        CfnOutput(
            self,
            "AuditLogGroupArnOutput",
            value=self.audit_log_group.log_group_arn,
            description="Audit Log Group ARN",
            export_name=f"{APP_PREFIX}-audit-log-group-arn"
        )
        CfnOutput(
            self,
            "WorkerStalledAlarmArnOutput",
            value=self.worker_stalled_alarm.alarm_arn,
            description="Worker Stalled Alarm ARN",
            export_name=f"{APP_PREFIX}-worker-stalled-alarm-arn"
        )
