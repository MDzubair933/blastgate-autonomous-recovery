"""
BlastGate Watchdog Lambda Handler
Scheduled monitoring task (invoked every 1 minute via EventBridge schedule).
"""

import os
from typing import Dict, Any, Optional
try:
    from .inventory import WatchdogInventoryReader
    from .evaluator import WatchdogEvaluator
    from .metrics import WatchdogMetricsEmitter
    from .incidents import WatchdogIncidentDetector
    from .config import CLUSTER_NAME, SERVICE_NAME, HEARTBEAT_TABLE_NAME, CLOUDWATCH_NAMESPACE
except (ImportError, ValueError):
    from inventory import WatchdogInventoryReader
    from evaluator import WatchdogEvaluator
    from metrics import WatchdogMetricsEmitter
    from incidents import WatchdogIncidentDetector
    from config import CLUSTER_NAME, SERVICE_NAME, HEARTBEAT_TABLE_NAME, CLOUDWATCH_NAMESPACE


def _is_live_aws_runtime() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))


def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    inventory_reader: Optional[WatchdogInventoryReader] = None,
    evaluator: Optional[WatchdogEvaluator] = None,
    metrics_emitter: Optional[WatchdogMetricsEmitter] = None,
    detector: Optional[WatchdogIncidentDetector] = None,
) -> Dict[str, Any]:
    """Watchdog execution cycle."""
    if _is_live_aws_runtime() and inventory_reader is None and evaluator is None and metrics_emitter is None:
        import boto3
        try:
            from telemetry.heartbeat_repository import DynamoDbHeartbeatRepository
            from telemetry.validator import TelemetryValidator
        except ImportError:
            from ..telemetry.heartbeat_repository import DynamoDbHeartbeatRepository
            from ..telemetry.validator import TelemetryValidator

        region = os.environ.get("AWS_REGION", "us-east-1")
        ecs = boto3.client("ecs", region_name=region)
        ddb = boto3.client("dynamodb", region_name=region)
        cw = boto3.client("cloudwatch", region_name=region)

        inv = WatchdogInventoryReader(ecs_client=ecs, cluster_name=CLUSTER_NAME, service_name=SERVICE_NAME)
        hb_repo = DynamoDbHeartbeatRepository(dynamodb_client=ddb, table_name=HEARTBEAT_TABLE_NAME)
        ev = WatchdogEvaluator(telemetry_validator=TelemetryValidator(repository=hb_repo))
        emitter = WatchdogMetricsEmitter(cloudwatch_client=cw, namespace=CLOUDWATCH_NAMESPACE)
    else:
        inv = inventory_reader or WatchdogInventoryReader()
        ev = evaluator
        emitter = metrics_emitter or WatchdogMetricsEmitter()

    det = detector or WatchdogIncidentDetector()

    # 1. Fetch live service inventory
    inventory = inv.get_service_inventory()

    # 2. Evaluate worker health (if evaluator provided)
    if ev:
        evaluation = ev.evaluate_service_health(inventory)
    else:
        evaluation = {
            "desired_count": inventory.get("desired_count", 0),
            "healthy_count": 0,
            "confirmed_stalled_count": 0,
            "unknown_count": 0,
            "stalled_task_arns": [],
        }

    # 3. Publish CloudWatch metrics
    emitter.emit_metrics(evaluation)

    # 4. Check for incident
    incident_info = det.check_for_incident(evaluation)

    return {
        "statusCode": 200,
        "evaluation": evaluation,
        "incident_detected": incident_info is not None,
        "incident_info": incident_info,
    }
