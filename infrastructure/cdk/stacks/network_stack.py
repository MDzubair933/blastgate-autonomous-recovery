"""
BlastGate Network Stack
Provides minimal, cost-isolated VPC infrastructure without NAT Gateways or Load Balancers.
"""

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct
from config import APP_PREFIX, VPC_CIDR, MAX_AZS


class NetworkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cost-Optimized VPC: 2 Public subnets, ZERO NAT Gateways ($0/month idle cost)
        self.vpc = ec2.Vpc(
            self,
            "SandboxVpc",
            vpc_name=f"{APP_PREFIX}-sandbox-vpc",
            ip_addresses=ec2.IpAddresses.cidr(VPC_CIDR),
            max_azs=MAX_AZS,
            nat_gateways=0,  # CRITICAL COST CONTROL: Prevent $32.40/month NAT Gateway charges
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name=f"{APP_PREFIX}-public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=26
                )
            ]
        )

        # Isolated Security Group: Outbound only for ECR image pull & CloudWatch logs
        # ZERO public inbound rules allowed
        self.worker_security_group = ec2.SecurityGroup(
            self,
            "WorkerSecurityGroup",
            security_group_name=f"{APP_PREFIX}-worker-sg",
            vpc=self.vpc,
            description="BlastGate worker security group with zero inbound public access",
            allow_all_outbound=True
        )

        CfnOutput(
            self,
            "VpcIdOutput",
            value=self.vpc.vpc_id,
            description="BlastGate Sandbox VPC ID",
            export_name=f"{APP_PREFIX}-vpc-id"
        )
        CfnOutput(
            self,
            "WorkerSecurityGroupIdOutput",
            value=self.worker_security_group.security_group_id,
            description="BlastGate Worker Security Group ID",
            export_name=f"{APP_PREFIX}-worker-sg-id"
        )
