"""
BlastGate Worker Application Entrypoint
Starts the processing loop and the independent health supervisor heartbeat loop.
"""

import json
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path

# Add worker directory to path only when run standalone as entrypoint
if __package__ is None or __package__ == "":
    WORKER_DIR = Path(__file__).resolve().parent
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))

try:
    from .processor import WorkProcessor
    from .health import HealthSupervisor
    from .heartbeat import HeartbeatPublisher
    from .config import (
        HEARTBEAT_INTERVAL_SECONDS,
        PROCESSOR_INTERVAL_SECONDS,
        HEARTBEAT_TABLE_NAME,
        ENABLE_FAULT_INJECTION,
        STALL_THRESHOLD_SECONDS,
    )
except (ImportError, ValueError):
    from processor import WorkProcessor
    from health import HealthSupervisor
    from heartbeat import HeartbeatPublisher
    from config import (
        HEARTBEAT_INTERVAL_SECONDS,
        PROCESSOR_INTERVAL_SECONDS,
        HEARTBEAT_TABLE_NAME,
        ENABLE_FAULT_INJECTION,
        STALL_THRESHOLD_SECONDS,
    )


def resolve_task_arn() -> str:
    """Resolves real ECS Task ARN via Metadata v4 in Fargate or explicit env override."""
    if os.environ.get("ECS_TASK_ARN"):
        return os.environ["ECS_TASK_ARN"]

    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if metadata_uri:
        try:
            with urllib.request.urlopen(f"{metadata_uri}/task", timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                task_arn = data.get("TaskARN")
                if task_arn:
                    return task_arn
        except Exception as e:
            print(f"[WARN] Failed to fetch ECS Metadata v4 TaskARN: {e}")

    return f"arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/{os.getpid():032x}"


def check_fault_injection_signal(ddb_client, task_arn: str, processor: WorkProcessor) -> None:
    """Checks controlled DynamoDB fault-injection trigger targeting this specific task ARN."""
    if not ENABLE_FAULT_INJECTION or ddb_client is None:
        return
    try:
        resp = ddb_client.get_item(
            TableName=HEARTBEAT_TABLE_NAME,
            Key={"task_arn": {"S": "CONTROL#FAULT_INJECTION"}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return
        target = item.get("target_task_arn", {}).get("S", "")
        inject = item.get("inject_stall", {}).get("BOOL", False)
        reason = item.get("reason", {}).get("S", "Controlled Step 6 stall injection")
        if inject and target == task_arn and not processor.is_stalled:
            print(f"[FAULT-INJECTION] Triggering controlled stall on target task: {task_arn}")
            processor.trigger_controlled_stall(reason=reason)
        elif (not inject or target != task_arn) and processor.is_stalled:
            processor.reset_stall()
    except Exception as e:
        print(f"[WARN] Fault-injection check error: {e}")


def main():
    print("=" * 60)
    print("BLASTGATE WORKER APPLICATION STARTUP")
    print("=" * 60)

    task_arn = resolve_task_arn()
    print(f"Task ARN: {task_arn}")

    ddb_client = None
    is_live = bool(os.environ.get("ECS_CONTAINER_METADATA_URI_V4") or os.environ.get("BLASTGATE_USE_LIVE_AWS"))
    if is_live:
        import boto3
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        ddb_client = boto3.client("dynamodb", region_name=region)
        print(f"[LIVE] DynamoDB heartbeat client initialized for table '{HEARTBEAT_TABLE_NAME}' in {region}")

    processor = WorkProcessor(interval_seconds=PROCESSOR_INTERVAL_SECONDS)
    supervisor = HealthSupervisor(processor=processor, stall_threshold_seconds=STALL_THRESHOLD_SECONDS)
    publisher = HeartbeatPublisher(
        task_arn=task_arn,
        supervisor=supervisor,
        dynamodb_client=ddb_client,
        table_name=HEARTBEAT_TABLE_NAME,
    )

    stop_flag = False

    def handle_signal(sig, frame):
        nonlocal stop_flag
        print(f"Received signal {sig}. Initiating graceful shutdown...")
        stop_flag = True
        processor.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    processor.start()
    print("Processing loop started.")

    try:
        while not stop_flag:
            check_fault_injection_signal(ddb_client, task_arn, processor)
            try:
                rec = publisher.publish_once()
                state = rec["processing_state"]
                print(f"[HEARTBEAT] state={state} | age={rec['processing_age']:.1f}s | count={rec['processed_count']}")
            except Exception as e:
                print(f"[ERROR] Failed to publish heartbeat: {e}")
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
    finally:
        processor.stop()
        print("Worker stopped.")


if __name__ == "__main__":
    main()
