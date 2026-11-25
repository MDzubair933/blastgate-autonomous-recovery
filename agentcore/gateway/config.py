"""
BlastGate Gateway Configuration & Payload Factory
Generates validated Boto3 request payloads for CreateGateway and CreateGatewayTarget.
"""

import json
from pathlib import Path
from typing import Dict, Any

GATEWAY_DIR = Path(__file__).resolve().parent
TOOLS_DIR = GATEWAY_DIR / "tools"

APP_PREFIX = "blastgate"
AWS_ACCOUNT = "123456789012"
AWS_REGION = "us-east-1"

GATEWAY_NAME = f"{APP_PREFIX}-gateway"
GATEWAY_ROLE_ARN = f"arn:aws:iam::{AWS_ACCOUNT}:role/{APP_PREFIX}-gateway-role"
POLICY_ENGINE_NAME = f"{APP_PREFIX}_policy_engine"
POLICY_ENGINE_ARN = f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:policy-engine/{POLICY_ENGINE_NAME}"

DIAGNOSTICS_FUNCTION_ARN = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{APP_PREFIX}-diagnostics"
BROKER_FUNCTION_ARN = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT}:function:{APP_PREFIX}-remediation-broker"


def load_tool_schema(filename: str) -> Dict[str, Any]:
    with open(TOOLS_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def get_create_gateway_payload(
    gateway_name: str = GATEWAY_NAME,
    role_arn: str = GATEWAY_ROLE_ARN,
    policy_engine_arn: str = POLICY_ENGINE_ARN,
    enforce_policy: bool = True,
) -> Dict[str, Any]:
    """Generates validated input dictionary for Boto3 CreateGateway API."""
    payload = {
        "name": gateway_name,
        "roleArn": role_arn,
        "protocolType": "MCP",
        "authorizerType": "AWS_IAM",
        "description": "BlastGate AgentCore Gateway connecting to scoped diagnostics and remediation broker targets",
        "tags": {
            "Project": "BlastGate",
            "Environment": "sandbox",
            "ManagedBy": "AWS-CDK",
        },
    }
    if policy_engine_arn:
        payload["policyEngineConfiguration"] = {
            "arn": policy_engine_arn,
            "mode": "ENFORCE" if enforce_policy else "LOG_ONLY",
        }
    return payload


def get_diagnostics_target_payload(
    gateway_identifier: str = GATEWAY_NAME,
    function_arn: str = DIAGNOSTICS_FUNCTION_ARN,
) -> Dict[str, Any]:
    """Generates validated input dictionary for CreateGatewayTarget (Diagnostics)."""
    schema = load_tool_schema("diagnostics_tool.json")
    return {
        "gatewayIdentifier": gateway_identifier,
        "name": f"{APP_PREFIX}diag",
        "description": "Gateway target routing to read-only diagnostics microservice",
        "targetConfiguration": {
            "mcp": {
                "lambda": {
                    "lambdaArn": function_arn,
                    "toolSchema": {
                        "inlinePayload": [schema]
                    }
                }
            }
        },
        "credentialProviderConfigurations": [
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    }


def get_broker_target_payload(
    gateway_identifier: str = GATEWAY_NAME,
    function_arn: str = BROKER_FUNCTION_ARN,
) -> Dict[str, Any]:
    """Generates validated input dictionary for CreateGatewayTarget (Remediation Broker)."""
    schema = load_tool_schema("remediation_tool.json")
    return {
        "gatewayIdentifier": gateway_identifier,
        "name": f"{APP_PREFIX}broker",
        "description": "Gateway target routing to sovereign remediation broker",
        "targetConfiguration": {
            "mcp": {
                "lambda": {
                    "lambdaArn": function_arn,
                    "toolSchema": {
                        "inlinePayload": [schema]
                    }
                }
            }
        },
        "credentialProviderConfigurations": [
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    }
