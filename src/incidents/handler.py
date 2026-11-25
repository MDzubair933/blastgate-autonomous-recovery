"""
BlastGate Incident Ingestion Lambda Handler
Triggered by EventBridge when a CloudWatch Alarm state changes.
Emits BlastGate.IncidentOpened event to EventBridge upon creating an OPEN incident.
"""

import json
import os
import time
from typing import Dict, Any, Optional
try:
    from .validator import AlarmEventValidator
    from .deduplication import IncidentDeduplicator
    from .repository import MockIncidentRepository, DynamoDbIncidentRepository, IncidentRepository
except (ImportError, ValueError):
    from validator import AlarmEventValidator
    from deduplication import IncidentDeduplicator
    from repository import MockIncidentRepository, DynamoDbIncidentRepository, IncidentRepository


def _is_live_aws_runtime() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))


def emit_incident_opened_event(incident, events_client=None) -> Optional[Dict[str, Any]]:
    """Emits BlastGate.IncidentOpened event to default EventBridge bus."""
    if events_client is None and _is_live_aws_runtime():
        import boto3
        region = os.environ.get("AWS_REGION", "us-east-1")
        events_client = boto3.client("events", region_name=region)

    if events_client is None:
        return None

    detail = {
        "incident_id": incident.incident_id,
        "alarm_name": incident.alarm_name,
        "status": incident.status,
        "state": incident.state,
        "target_task_arn": incident.target_task_arn,
        "cluster_name": getattr(incident, "cluster_name", "blastgate-sandbox"),
        "service_name": getattr(incident, "service_name", "blastgate-workers"),
        "timestamp": getattr(incident, "created_timestamp", time.time()),
    }
    entry = {
        "Source": "blastgate.incidents",
        "DetailType": "BlastGate.IncidentOpened",
        "Detail": json.dumps(detail),
        "EventBusName": "default",
    }
    try:
        resp = events_client.put_events(Entries=[entry])
        failed_count = resp.get("FailedEntryCount", 0)
        if failed_count > 0:
            failed_entries = resp.get("Entries", [])
            print(f"[ERROR] EventBridge PutEvents failed for {failed_count} entries: {failed_entries}")
            if hasattr(incident, "details") and isinstance(incident.details, dict):
                incident.details["event_dispatch_failed"] = True
                incident.details["event_dispatch_error"] = str(failed_entries)
            return None
        return resp
    except Exception as e:
        print(f"[WARN] Failed to emit BlastGate.IncidentOpened to EventBridge: {e}")
        if hasattr(incident, "details") and isinstance(incident.details, dict):
            incident.details["event_dispatch_failed"] = True
            incident.details["event_dispatch_error"] = str(e)
        return None


def lambda_handler(
    event: Dict[str, Any],
    context: Any = None,
    validator: Optional[AlarmEventValidator] = None,
    deduplicator: Optional[IncidentDeduplicator] = None,
    events_client: Any = None,
) -> Dict[str, Any]:
    """Processes CloudWatch Alarm State Change events."""
    val = validator or AlarmEventValidator()
    check = val.validate_event(event)

    if not check["is_valid"]:
        return {
            "statusCode": 400,
            "processed": False,
            "error": check["error"],
        }

    live_repo = None
    if deduplicator is not None:
        dedup = deduplicator
    elif _is_live_aws_runtime():
        import boto3
        region = os.environ.get("AWS_REGION", "us-east-1")
        ddb = boto3.client("dynamodb", region_name=region)
        inc_table = os.environ.get("INCIDENT_TABLE_NAME", "blastgate-incidents")
        live_repo = DynamoDbIncidentRepository(dynamodb_client=ddb, table_name=inc_table)
        dedup = IncidentDeduplicator(repository=live_repo)
    else:
        dedup = IncidentDeduplicator(repository=MockIncidentRepository())

    now = time.time()

    alarm_name = check["alarm_name"]
    new_state = check["new_state"]

    # Extract target task ARN if embedded in alarm configuration/description
    target_arn = None
    config = check.get("configuration", {})
    desc = config.get("description", "")
    if "arn:aws:ecs:" in desc:
        import re
        match = re.search(r"arn:aws:ecs:[a-z0-9-]+:[0-9]{12}:task/[a-zA-Z0-9_-]+/[a-f0-9]{32}", desc)
        if match:
            target_arn = match.group(0)

    # In live AWS, CloudWatch Alarm description is static; look up confirmed stalled task from heartbeats
    if target_arn is None and new_state == "ALARM" and live_repo is not None:
        hb_table = os.environ.get("HEARTBEAT_TABLE_NAME", "blastgate-heartbeats")
        target_arn = live_repo.find_latest_stalled_task_arn(heartbeat_table_name=hb_table)

    incident = dedup.process_alarm_transition(
        alarm_name=alarm_name,
        new_state=new_state,
        target_task_arn=target_arn,
        timestamp=now,
    )

    event_emitted = False
    if new_state == "ALARM" and incident.status == "OPEN":
        emit_resp = emit_incident_opened_event(incident, events_client=events_client)
        event_emitted = emit_resp is not None
        if not event_emitted and dedup is not None and getattr(dedup, "repository", None) is not None:
            # If EventBridge emission failed, persist failure details in DynamoDB
            # so the incident record is not silently lost
            incident.details["event_dispatch_failed"] = True
            dedup.repository.save_incident(incident)

    return {
        "statusCode": 200,
        "processed": True,
        "incident_id": incident.incident_id,
        "status": incident.status,
        "state": incident.state,
        "target_task_arn": incident.target_task_arn,
        "event_emitted": event_emitted,
    }
