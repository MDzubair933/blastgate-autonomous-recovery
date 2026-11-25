"""
BlastGate Diagnostics ECS Reader
Reads live ECS task state from an injected inventory provider or Boto3 ECS client.
"""

from typing import Optional, Dict, Any


class EcsStateReader:
    """Reads live ECS state."""

    def __init__(self, inventory_provider=None, ecs_client=None):
        self.inventory_provider = inventory_provider
        self.ecs_client = ecs_client

    def get_task_state(self, cluster: str, task_arn: str) -> Optional[Dict[str, Any]]:
        if self.inventory_provider:
            task = self.inventory_provider.get_task_details(cluster, task_arn)
            if not task:
                return None
            return {
                "task_arn": task.task_arn,
                "task_family": task.task_family,
                "last_status": task.last_status,
                "desired_status": task.desired_status,
            }

        if self.ecs_client and task_arn:
            resp = self.ecs_client.describe_tasks(cluster=cluster, tasks=[task_arn])
            tasks = resp.get("tasks", [])
            if not tasks:
                return None
            t = tasks[0]
            td_arn = t.get("taskDefinitionArn", "")
            td_part = td_arn.split("/")[-1] if "/" in td_arn else td_arn
            task_family = td_part.split(":")[0] if ":" in td_part else td_part
            return {
                "task_arn": t.get("taskArn", task_arn),
                "task_family": task_family,
                "last_status": t.get("lastStatus", "UNKNOWN"),
                "desired_status": t.get("desiredStatus", "UNKNOWN"),
            }

        return None
