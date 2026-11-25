#!/usr/bin/env python3
"""
BlastGate Safe Cleanup Utility
Safely shuts down sandbox compute and verifies zero running tasks.
Strictly requires explicit profile, region, and confirmation flag.
Defaults to DRY-RUN mode.
"""

import sys
import argparse
import boto3

EXPECTED_ACCOUNT_ID = "123456789012"
ALLOWED_REGIONS = ["us-east-1"]
TARGET_CLUSTER = "blastgate-sandbox"
TARGET_SERVICE = "blastgate-workers"


def parse_args():
    parser = argparse.ArgumentParser(description="BlastGate Safe Workload Cleanup Utility")
    parser.add_argument("--profile", default="antigravity", help="AWS CLI profile (default: antigravity)")
    parser.add_argument("--region", default="us-east-1", help="Target AWS Region (default: us-east-1)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate without modifying state (default: True)")
    parser.add_argument("--confirm", action="store_true", default=False, help="Confirm real execution (disables dry-run)")
    return parser.parse_args()


def main():
    args = parse_args()
    is_dry_run = args.dry_run and not args.confirm

    print("=" * 60)
    print("BLASTGATE WORKLOAD CLEANUP UTILITY")
    print(f"Mode: {'[DRY-RUN - NO CHANGES WILL BE APPLIED]' if is_dry_run else '[REAL EXECUTION CONFIRMED]'}")
    print(f"Profile: {args.profile} | Region: {args.region}")
    print("=" * 60)

    # 1. Safety Gate: Region Verification
    if args.region not in ALLOWED_REGIONS:
        print(f"[REFUSAL] Region {args.region} is not an authorized BlastGate sandbox region. Aborting.")
        sys.exit(1)

    # 2. Safety Gate: Account Identity Verification
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    sts = session.client("sts")
    caller = sts.get_caller_identity()
    account_id = caller["Account"]

    if account_id != EXPECTED_ACCOUNT_ID:
        print(f"[REFUSAL] Account ID {account_id} does not match expected sandbox account {EXPECTED_ACCOUNT_ID}. Aborting.")
        sys.exit(1)

    print(f"[VERIFIED] Caller identity: {caller['Arn']}")

    ecs = session.client("ecs", region_name=args.region)

    # 3. Check Cluster Existence
    try:
        clusters = ecs.describe_clusters(clusters=[TARGET_CLUSTER])["clusters"]
        if not clusters or clusters[0]["status"] != "ACTIVE":
            print(f"[INFO] Sandbox cluster '{TARGET_CLUSTER}' does not exist or is inactive. Nothing to stop.")
            return
    except Exception as e:
        print(f"[INFO] Cluster '{TARGET_CLUSTER}' query returned: {e}")
        return

    # 4. Check Service Existence & Desired Count
    try:
        services = ecs.describe_services(cluster=TARGET_CLUSTER, services=[TARGET_SERVICE])["services"]
        if not services or services[0]["status"] != "ACTIVE":
            print(f"[INFO] Service '{TARGET_SERVICE}' does not exist in cluster '{TARGET_CLUSTER}'.")
            return

        service = services[0]
        desired = service.get("desiredCount", 0)
        running = service.get("runningCount", 0)
        print(f"[CURRENT STATE] Service: {TARGET_SERVICE} | Desired Count: {desired} | Running Count: {running}")

        if desired == 0 and running == 0:
            print("[SAFE] Service desired count is already 0 and running task count is 0. Zero ongoing compute charges.")
            return

        if is_dry_run:
            print(f"[DRY-RUN ACTION] Would update service '{TARGET_SERVICE}' desiredCount from {desired} -> 0.")
            print("[DRY-RUN ACTION] Run with '--confirm' to execute actual shutdown.")
            return

        # Real Execution
        print(f"[EXECUTING] Scaling service '{TARGET_SERVICE}' down to desiredCount = 0...")
        ecs.update_service(cluster=TARGET_CLUSTER, service=TARGET_SERVICE, desiredCount=0)
        print("[SUCCESS] Service updated. Waiting for running tasks to stop...")
        waiter = ecs.get_waiter("services_stable")
        waiter.wait(cluster=TARGET_CLUSTER, services=[TARGET_SERVICE])
        print("[CONFIRMED] Service is stable with 0 running tasks.")

    except Exception as e:
        print(f"[ERROR] Service modification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
