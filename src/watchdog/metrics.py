"""
BlastGate Watchdog CloudWatch Metrics Emitter
Publishes low-cardinality custom metrics to CloudWatch namespace BlastGate/Workers.
"""

from typing import Dict, Any, List
try:
    from .config import CLOUDWATCH_NAMESPACE, CLUSTER_NAME, SERVICE_NAME
except (ImportError, ValueError):
    from config import CLOUDWATCH_NAMESPACE, CLUSTER_NAME, SERVICE_NAME


class WatchdogMetricsEmitter:
    """Publishes custom service metrics."""

    def __init__(self, cloudwatch_client=None, namespace: str = CLOUDWATCH_NAMESPACE):
        self.client = cloudwatch_client
        self.namespace = namespace
        self.emitted_metrics: List[Dict[str, Any]] = []

    def emit_metrics(self, evaluation: Dict[str, Any]):
        """
        Emits:
        - DesiredWorkerCount
        - HealthyWorkerCount
        - ConfirmedStalledWorkerCount
        - UnknownWorkerCount
        Dimensions: ClusterName=blastgate-sandbox, ServiceName=blastgate-workers
        """
        dimensions = [
            {"Name": "ClusterName", "Value": CLUSTER_NAME},
            {"Name": "ServiceName", "Value": SERVICE_NAME},
        ]

        metric_data = [
            {"Namespace": self.namespace, "MetricName": "DesiredWorkerCount", "Value": float(evaluation["desired_count"]), "Unit": "Count", "Dimensions": dimensions},
            {"Namespace": self.namespace, "MetricName": "HealthyWorkerCount", "Value": float(evaluation["healthy_count"]), "Unit": "Count", "Dimensions": dimensions},
            {"Namespace": self.namespace, "MetricName": "ConfirmedStalledWorkerCount", "Value": float(evaluation["confirmed_stalled_count"]), "Unit": "Count", "Dimensions": dimensions},
            {"Namespace": self.namespace, "MetricName": "UnknownWorkerCount", "Value": float(evaluation["unknown_count"]), "Unit": "Count", "Dimensions": dimensions},
        ]

        self.emitted_metrics.extend(metric_data)

        if self.client:
            raw_metric_data = [
                {"MetricName": m["MetricName"], "Value": m["Value"], "Unit": m["Unit"], "Dimensions": m["Dimensions"]}
                for m in metric_data
            ]
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=raw_metric_data,
            )
