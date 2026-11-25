#!/usr/bin/env python3
"""
BlastGate Worker Image Builder via AWS CodeBuild
Used when local Docker Engine is unavailable on the developer workstation.
Packages src/worker/, triggers a single ephemeral Linux/AMD64 Docker build in CodeBuild,
pushes versioned tag + fetches immutable SHA-256 ECR digest, and deletes the temporary
CodeBuild project and S3 build archive immediately after completion.
"""

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3

HACKATHON_ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = HACKATHON_ROOT / "src" / "worker"
ACCOUNT_ID = "123456789012"
REGION = "us-east-1"
ECR_REPO_NAME = "blastgate-worker"
CODEBUILD_PROJECT_NAME = "blastgate-worker-image-builder"
CODEBUILD_ROLE_NAME = "blastgate-codebuild-role"
BOOTSTRAP_BUCKET = f"cdk-hnb659fds-assets-{ACCOUNT_ID}-{REGION}"
SOURCE_S3_KEY = "worker-build/worker-source.zip"


def build_worker_source_zip() -> bytes:
    """Packages src/worker files and buildspec.yml into an in-memory ZIP."""
    buildspec = f"""version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region {REGION} | docker login --username AWS --password-stdin {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com
  build:
    commands:
      - docker build --platform linux/amd64 -t {ECR_REPO_NAME}:$IMAGE_TAG .
      - docker tag {ECR_REPO_NAME}:$IMAGE_TAG {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:$IMAGE_TAG
      - docker tag {ECR_REPO_NAME}:$IMAGE_TAG {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:latest
  post_build:
    commands:
      - docker push {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:$IMAGE_TAG
      - docker push {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:latest
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("buildspec.yml", buildspec)
        for file_path in WORKER_DIR.rglob("*"):
            if file_path.is_file() and "__pycache__" not in file_path.parts:
                zf.write(file_path, str(file_path.relative_to(WORKER_DIR)).replace("\\", "/"))
    return buf.getvalue()


def ensure_codebuild_role(iam_client) -> str:
    """Creates or reuses the scoped CodeBuild service role."""
    try:
        resp = iam_client.get_role(RoleName=CODEBUILD_ROLE_NAME)
        role_arn = resp["Role"]["Arn"]
    except iam_client.exceptions.NoSuchEntityException:
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }
        resp = iam_client.create_role(
            RoleName=CODEBUILD_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Scoped role for BlastGate temporary worker image CodeBuild",
        )
        role_arn = resp["Role"]["Arn"]
        time.sleep(8)

    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CodeBuildLogs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:/aws/codebuild/{CODEBUILD_PROJECT_NAME}*",
            },
            {
                "Sid": "ReadSourceZip",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:GetObjectVersion", "s3:GetBucketLocation"],
                "Resource": [f"arn:aws:s3:::{BOOTSTRAP_BUCKET}", f"arn:aws:s3:::{BOOTSTRAP_BUCKET}/{SOURCE_S3_KEY}"],
            },
            {
                "Sid": "EcrAuthAndPush",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Sid": "EcrRepoPush",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:CompleteLayerUpload",
                    "ecr:InitiateLayerUpload",
                    "ecr:PutImage",
                    "ecr:UploadLayerPart",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                "Resource": f"arn:aws:ecr:{REGION}:{ACCOUNT_ID}:repository/{ECR_REPO_NAME}",
            },
        ],
    }
    iam_client.put_role_policy(
        RoleName=CODEBUILD_ROLE_NAME,
        PolicyName="blastgate-codebuild-ecr-policy",
        PolicyDocument=json.dumps(inline_policy),
    )
    time.sleep(5)
    return role_arn


def main():
    parser = argparse.ArgumentParser(description="Build & push BlastGate worker container via CodeBuild")
    parser.add_argument("--profile", default="antigravity")
    parser.add_argument("--tag", default="v1.0.0")
    parser.add_argument("--confirm", action="store_true", help="Actually execute AWS CodeBuild creation and build")
    args = parser.parse_args()

    zip_bytes = build_worker_source_zip()
    print(f"[STAGED] Worker source archive size: {len(zip_bytes):,} bytes")

    if not args.confirm:
        print("[DRY-RUN] Re-run with --confirm after explicit deployment approval to execute CodeBuild.")
        return

    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    sts = session.client("sts")
    ident = sts.get_caller_identity()
    assert ident["Account"] == ACCOUNT_ID, f"Unexpected account: {ident['Account']}"
    print(f"[IDENTITY] {ident['Arn']}")

    iam = session.client("iam")
    s3 = session.client("s3")
    cb = session.client("codebuild")
    ecr = session.client("ecr")

    role_arn = ensure_codebuild_role(iam)
    print(f"[ROLE] {role_arn}")

    s3.put_object(Bucket=BOOTSTRAP_BUCKET, Key=SOURCE_S3_KEY, Body=zip_bytes)
    print(f"[S3] Uploaded s3://{BOOTSTRAP_BUCKET}/{SOURCE_S3_KEY}")

    try:
        try:
            cb.delete_project(name=CODEBUILD_PROJECT_NAME)
        except Exception:
            pass

        cb.create_project(
            name=CODEBUILD_PROJECT_NAME,
            description="Ephemeral Linux/AMD64 Docker builder for blastgate-worker",
            source={
                "type": "S3",
                "location": f"{BOOTSTRAP_BUCKET}/{SOURCE_S3_KEY}",
            },
            artifacts={"type": "NO_ARTIFACTS"},
            environment={
                "type": "LINUX_CONTAINER",
                "image": "aws/codebuild/standard:7.0",
                "computeType": "BUILD_GENERAL1_SMALL",
                "privilegedMode": True,
                "environmentVariables": [
                    {"name": "IMAGE_TAG", "value": args.tag, "type": "PLAINTEXT"},
                ],
            },
            serviceRole=role_arn,
            timeoutInMinutes=10,
            logsConfig={
                "cloudWatchLogs": {
                    "status": "ENABLED",
                    "groupName": f"/aws/codebuild/{CODEBUILD_PROJECT_NAME}",
                }
            },
        )
        build_resp = cb.start_build(projectName=CODEBUILD_PROJECT_NAME)
        build_id = build_resp["build"]["id"]
        print(f"[CODEBUILD] Started build: {build_id}")

        while True:
            time.sleep(10)
            b = cb.batch_get_builds(ids=[build_id])["builds"][0]
            status = b["buildStatus"]
            phase = b.get("currentPhase", "")
            print(f"[CODEBUILD] status={status} phase={phase}")
            if status != "IN_PROGRESS":
                if status != "SUCCEEDED":
                    raise RuntimeError(f"CodeBuild failed with status: {status}")
                break

        imgs = ecr.describe_images(repositoryName=ECR_REPO_NAME, imageIds=[{"imageTag": args.tag}])["imageDetails"]
        digest = imgs[0]["imageDigest"]
        print(f"[SUCCESS] Published {ECR_REPO_NAME}:{args.tag} with immutable digest: {digest}")
    finally:
        # Clean up ephemeral build resources immediately
        try:
            cb.delete_project(name=CODEBUILD_PROJECT_NAME)
            print(f"[CLEANUP] Deleted temporary CodeBuild project: {CODEBUILD_PROJECT_NAME}")
        except Exception as e:
            print(f"[WARN] Could not delete CodeBuild project: {e}")
        try:
            s3.delete_object(Bucket=BOOTSTRAP_BUCKET, Key=SOURCE_S3_KEY)
            print(f"[CLEANUP] Deleted temporary source zip: {SOURCE_S3_KEY}")
        except Exception as e:
            print(f"[WARN] Could not delete S3 source zip: {e}")


if __name__ == "__main__":
    main()
