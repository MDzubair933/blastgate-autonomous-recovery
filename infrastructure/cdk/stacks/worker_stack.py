"""
BlastGate Worker Stack
Provisions the isolated Amazon ECS Fargate sandbox cluster and worker service.
CRITICAL COST CONTROL: Initial deployed desiredCount is strictly ZERO.
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct
from config import (
    APP_PREFIX,
    CLUSTER_NAME,
    SERVICE_NAME,
    TASK_FAMILY,
    INITIAL_DESIRED_COUNT,
    HEARTBEAT_TABLE_NAME,
)


class WorkerStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        security_group: ec2.ISecurityGroup,
        execution_role: iam.IRole,
        task_role: iam.IRole,
        log_group: logs.ILogGroup,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Isolated ECS Fargate Cluster
        self.cluster = ecs.Cluster(
            self,
            "SandboxCluster",
            cluster_name=CLUSTER_NAME,
            vpc=vpc,
            enable_fargate_capacity_providers=True
        )

        # 2. Fargate Task Definition (256 CPU, 512 MB RAM - Minimal footprint)
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "WorkerTaskDef",
            family=TASK_FAMILY,
            cpu=256,
            memory_limit_mib=512,
            execution_role=execution_role,
            task_role=task_role
        )

        # Dedicated ECR Repository for the BlastGate Worker container
        self.worker_repository = ecr.Repository(
            self,
            "WorkerRepository",
            repository_name=f"{APP_PREFIX}-worker",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            image_scan_on_push=True,
        )

        # Container Definition (References real BlastGate worker ECR repository)
        # Supports immutable SHA-256 digest via CDK context (-c worker_image_digest=sha256:...)
        # or version tag (-c worker_image_tag=...), defaulting to 'latest' when desiredCount=0.
        image_digest = self.node.try_get_context("worker_image_digest")
        image_tag = self.node.try_get_context("worker_image_tag") or "latest"
        image_uri = (
            f"{self.worker_repository.repository_uri}@{image_digest}"
            if image_digest
            else self.worker_repository.repository_uri_for_tag(image_tag)
        )
        self.container = self.task_definition.add_container(
            "WorkerContainer",
            image=ecs.ContainerImage.from_registry(image_uri),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="worker",
                log_group=log_group
            ),
            environment={
                "SERVICE_NAME": SERVICE_NAME,
                "ENVIRONMENT": "sandbox",
                "CLUSTER_NAME": CLUSTER_NAME,
                "HEARTBEAT_TABLE_NAME": HEARTBEAT_TABLE_NAME,
                "ENABLE_FAULT_INJECTION": "true",
            }
        )

        # 3. Fargate Service
        # CRITICAL COST CONTROL: desired_count is HARDCODED to INITIAL_DESIRED_COUNT (0)
        # Prevents running charges until controlled live testing in Step 6.
        self.service = ecs.FargateService(
            self,
            "WorkerService",
            service_name=SERVICE_NAME,
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=INITIAL_DESIRED_COUNT,
            assign_public_ip=True,
            security_groups=[security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        CfnOutput(
            self,
            "ClusterArnOutput",
            value=self.cluster.cluster_arn,
            description="Sandbox Cluster ARN",
            export_name=f"{APP_PREFIX}-cluster-arn"
        )
        CfnOutput(
            self,
            "ServiceArnOutput",
            value=self.service.service_arn,
            description="Sandbox Service ARN",
            export_name=f"{APP_PREFIX}-service-arn"
        )
        CfnOutput(
            self,
            "TaskDefinitionArnOutput",
            value=self.task_definition.task_definition_arn,
            description="Worker Task Definition ARN",
            export_name=f"{APP_PREFIX}-task-def-arn"
        )
        CfnOutput(
            self,
            "WorkerRepositoryUriOutput",
            value=self.worker_repository.repository_uri,
            description="BlastGate Worker ECR Repository URI",
            export_name=f"{APP_PREFIX}-worker-repo-uri"
        )
