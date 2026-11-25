"""
BlastGate Storage Stack
Defines separated state, audit, heartbeat telemetry, and incident storage tables in Amazon DynamoDB.
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    CfnOutput,
)
from constructs import Construct
from config import (
    APP_PREFIX,
    STATE_TABLE_NAME,
    AUDIT_TABLE_NAME,
    HEARTBEAT_TABLE_NAME,
    INCIDENT_TABLE_NAME,
)


class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Table A: State Coordination & Cooldown Lock Table
        # Used for atomic conditional reservations (600s cooldown)
        self.state_table = dynamodb.Table(
            self,
            "StateTable",
            table_name=STATE_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="cluster_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Table B: Structured Audit Evidence Table
        # Append-oriented immutable audit log. NO TTL deletion allowed.
        self.audit_table = dynamodb.Table(
            self,
            "AuditTable",
            table_name=AUDIT_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="event_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
            # NOTE: TTL is intentionally NOT enabled on audit_table to prevent premature record deletion.
        )

        # Table C: Worker Heartbeat Telemetry Table (Task 4.2)
        # Partition key: task_arn (String)
        self.heartbeat_table = dynamodb.Table(
            self,
            "HeartbeatTable",
            table_name=HEARTBEAT_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="task_arn",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Table D: Incidents Store Table (Task 4.4)
        # Partition key: incident_id (String)
        self.incident_table = dynamodb.Table(
            self,
            "IncidentTable",
            table_name=INCIDENT_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="incident_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(
            self,
            "StateTableArnOutput",
            value=self.state_table.table_arn,
            description="BlastGate State Table ARN",
            export_name=f"{APP_PREFIX}-state-table-arn"
        )
        CfnOutput(
            self,
            "AuditTableArnOutput",
            value=self.audit_table.table_arn,
            description="BlastGate Audit Table ARN",
            export_name=f"{APP_PREFIX}-audit-table-arn"
        )
        CfnOutput(
            self,
            "HeartbeatTableArnOutput",
            value=self.heartbeat_table.table_arn,
            description="BlastGate Heartbeat Table ARN",
            export_name=f"{APP_PREFIX}-heartbeat-table-arn"
        )
        CfnOutput(
            self,
            "IncidentTableArnOutput",
            value=self.incident_table.table_arn,
            description="BlastGate Incident Table ARN",
            export_name=f"{APP_PREFIX}-incident-table-arn"
        )
