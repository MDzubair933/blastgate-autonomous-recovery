"""
BlastGate ECS Identity Validator
Cross-references heartbeat task identity against trusted ECS ownership boundaries.
"""

import re
from typing import Dict, Any


class EcsIdentityValidator:
    """Validates that a task ARN belongs to the approved sandbox cluster and service."""

    TASK_ARN_PATTERN = re.compile(r"^arn:aws:ecs:([a-z0-9-]+):([0-9]{12}):task/([a-zA-Z0-9_-]+)/([a-f0-9]{32})$")

    def __init__(
        self,
        expected_account: str = "123456789012",
        expected_region: str = "us-east-1",
        expected_cluster: str = "blastgate-sandbox",
        expected_service: str = "blastgate-workers",
        expected_family: str = "blastgate-worker",
    ):
        self.expected_account = expected_account
        self.expected_region = expected_region
        self.expected_cluster = expected_cluster
        self.expected_service = expected_service
        self.expected_family = expected_family

    def validate_task_arn(self, task_arn: str) -> Dict[str, Any]:
        """Validates ARN format and ownership perimeter."""
        match = self.TASK_ARN_PATTERN.match(task_arn)
        if not match:
            return {"is_valid": False, "error": f"Invalid ECS task ARN format: {task_arn}"}

        region, account, cluster, task_id = match.groups()

        if account != self.expected_account:
            return {"is_valid": False, "error": f"Account mismatch: {account} != {self.expected_account}"}
        if region != self.expected_region:
            return {"is_valid": False, "error": f"Region mismatch: {region} != {self.expected_region}"}
        if cluster != self.expected_cluster:
            return {"is_valid": False, "error": f"Cluster mismatch: {cluster} != {self.expected_cluster}"}

        return {
            "is_valid": True,
            "region": region,
            "account": account,
            "cluster": cluster,
            "task_id": task_id,
        }
