"""
BlastGate Watchdog Inventory Reader
Fetches live running tasks for the target ECS service.
"""

from typing import List, Dict, Any


class WatchdogInventoryReader:
    """Reads running tasks from ECS service."""

    def __init__(self, ecs_client=None, cluster_name: str = "blastgate-sandbox", service_name: str = "blastgate-workers"):
        self.client = ecs_client
        self.cluster_name = cluster_name
        self.service_name = service_name

    def get_service_inventory(self) -> Dict[str, Any]:
        """Returns desired count, running count, and list of running task ARNs."""
        if not self.client:
            return {
                "desired_count": 0,
                "running_count": 0,
                "task_arns": [],
            }

        # Query DescribeServices
        svc_resp = self.client.describe_services(
            cluster=self.cluster_name,
            services=[self.service_name],
        )
        services = svc_resp.get("services", [])
        if not services:
            return {"desired_count": 0, "running_count": 0, "task_arns": []}

        service = services[0]
        desired = service.get("desiredCount", 0)
        running = service.get("runningCount", 0)

        if running == 0:
            return {"desired_count": desired, "running_count": 0, "task_arns": []}

        # Query ListTasks
        list_resp = self.client.list_tasks(
            cluster=self.cluster_name,
            serviceName=self.service_name,
            desiredStatus="RUNNING",
        )
        task_arns = list_resp.get("taskArns", [])

        return {
            "desired_count": desired,
            "running_count": running,
            "task_arns": task_arns,
        }
