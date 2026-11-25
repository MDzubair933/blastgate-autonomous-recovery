"""
BlastGate Diagnostics Lambda Handler
Entrypoint for the read-only diagnostics microservice.
Operation: get_incident_diagnostics(incident_id)
"""

import os
from typing import Dict, Any, Optional
try:
    from .incident_reader import IncidentReader
    from .ecs_reader import EcsStateReader
    from .health_reader import HealthStateReader
    from .log_reader import LogReader
    from .response_builder import DiagnosticsResponseBuilder
except (ImportError, ValueError):
    from incident_reader import IncidentReader
    from ecs_reader import EcsStateReader
    from health_reader import HealthStateReader
    from log_reader import LogReader
    from response_builder import DiagnosticsResponseBuilder


def _is_live_aws_runtime() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))


def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    incident_reader: Optional[IncidentReader] = None,
    ecs_reader: Optional[EcsStateReader] = None,
    health_reader: Optional[HealthStateReader] = None,
    log_reader: Optional[LogReader] = None,
    response_builder: Optional[DiagnosticsResponseBuilder] = None,
) -> Dict[str, Any]:
    """Retrieves trusted diagnostic package for an operational incident."""
    incident_id = event.get("incident_id")
    if not incident_id:
        return {"statusCode": 400, "error": "Missing required field: incident_id"}

    if _is_live_aws_runtime() and incident_reader is None:
        import boto3
        try:
            from telemetry.heartbeat_repository import DynamoDbHeartbeatRepository
        except ImportError:
            from ..telemetry.heartbeat_repository import DynamoDbHeartbeatRepository

        region = os.environ.get("AWS_REGION", "us-east-1")
        ddb = boto3.client("dynamodb", region_name=region)
        ecs = boto3.client("ecs", region_name=region)
        logs = boto3.client("logs", region_name=region)
        inc_table = os.environ.get("INCIDENT_TABLE_NAME", "blastgate-incidents")
        hb_table = os.environ.get("HEARTBEAT_TABLE_NAME", "blastgate-heartbeats")

        inc_reader = IncidentReader(dynamodb_client=ddb, table_name=inc_table)
        ecs_rd = ecs_reader or EcsStateReader(ecs_client=ecs)
        hb_repo = DynamoDbHeartbeatRepository(dynamodb_client=ddb, table_name=hb_table)
        hlth_rd = health_reader or HealthStateReader(repository=hb_repo)
        log_rd = log_reader or LogReader(logs_client=logs)
    else:
        inc_reader = incident_reader or IncidentReader()
        ecs_rd = ecs_reader or EcsStateReader()
        hlth_rd = health_reader or HealthStateReader()
        log_rd = log_reader or LogReader()

    builder = response_builder or DiagnosticsResponseBuilder()

    incident = inc_reader.get_incident(incident_id)
    if not incident:
        return {
            "statusCode": 404,
            "error": f"Incident '{incident_id}' not found in incident store.",
        }

    target_task_arn = incident.get("target_task_arn", "")
    cluster_name = incident.get("cluster_name", os.environ.get("CLUSTER_NAME", "blastgate-sandbox"))

    ecs_state = ecs_rd.get_task_state(cluster_name, target_task_arn) if target_task_arn else None
    health_evidence = hlth_rd.get_health_evidence(target_task_arn) if target_task_arn else {"is_valid_evidence": False}
    raw_logs = event.get("mock_logs") if "mock_logs" in event else None
    log_evidence = log_rd.get_bounded_log_excerpts(target_task_arn, raw_logs=raw_logs)

    report = builder.build_response(
        incident=incident,
        ecs_state=ecs_state,
        health_evidence=health_evidence,
        log_evidence=log_evidence,
    )

    return {
        "statusCode": 200,
        "diagnostics": report,
    }
