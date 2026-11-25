"""
BlastGate Managed Harness Configuration & Payload Factory
Generates validated Boto3 request payloads for CreateHarness API.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from agentcore.prompts.system_prompt import get_harness_system_prompt_blocks

APP_PREFIX = "blastgate"
AWS_ACCOUNT = "123456789012"
AWS_REGION = "us-east-1"

HARNESS_NAME = f"{APP_PREFIX}_recovery_harness"
HARNESS_ROLE_ARN = f"arn:aws:iam::{AWS_ACCOUNT}:role/{APP_PREFIX}-agent-role"
GATEWAY_ARN = f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT}:gateway/{APP_PREFIX}-gateway"

DEFAULT_MODEL_ID = "amazon.nova-micro-v1:0"
MAX_ITERATIONS = 10
MAX_TOKENS = 2048
TIMEOUT_SECONDS = 60

# MANDATORY SECURITY RESTRICTION: Only explicitly approved Gateway tools are allowed.
# Supports both MCP server-namespaced convention (@server/tool or server/tool) and direct name.
# Built-in tools (shell, file_operations, code_interpreter, browser) are strictly omitted
# and excluded via allowedTools whitelist.
ALLOWED_TOOLS = [
    "@blastgate_gateway/blastgatediag___get_incident_diagnostics",
    "@blastgate_gateway/blastgatebroker___propose_worker_replacement",
]


def get_create_harness_payload(
    harness_name: str = HARNESS_NAME,
    execution_role_arn: str = HARNESS_ROLE_ARN,
    gateway_arn: str = GATEWAY_ARN,
    model_id: str = DEFAULT_MODEL_ID,
    max_iterations: int = MAX_ITERATIONS,
    max_tokens: int = MAX_TOKENS,
    timeout_seconds: int = TIMEOUT_SECONDS,
    guardrail_identifier: Optional[str] = None,
    guardrail_version: str = "1",
) -> Dict[str, Any]:
    """Generates validated input dictionary for Boto3 CreateHarness API."""
    bedrock_cfg: Dict[str, Any] = {
        "modelId": model_id,
        "maxTokens": max_tokens,
        "temperature": 0.0,
        "topP": 0.9,
        "apiFormat": "converse_stream",
    }
    if guardrail_identifier:
        bedrock_cfg["additionalParams"] = {
            "guardrailConfig": {
                "guardrailIdentifier": guardrail_identifier,
                "guardrailVersion": guardrail_version,
            }
        }
    return {
        "harnessName": harness_name,
        "executionRoleArn": execution_role_arn,
        "model": {
            "bedrockModelConfig": bedrock_cfg
        },
        "systemPrompt": get_harness_system_prompt_blocks(),
        "tools": [
            {
                "type": "agentcore_gateway",
                "name": "blastgate_gateway",
                "config": {
                    "agentCoreGateway": {
                        "gatewayArn": gateway_arn,
                        "outboundAuth": {
                            "awsIam": {}
                        }
                    }
                }
            }
        ],
        "allowedTools": ALLOWED_TOOLS,
        "memory": {"disabled": {}},
        "maxIterations": max_iterations,
        "maxTokens": max_tokens,
        "timeoutSeconds": timeout_seconds,
        "tags": {
            "Project": "BlastGate",
            "Environment": "sandbox",
            "ManagedBy": "AWS-CDK",
            "SecurityModel": "Diagnostic-And-Proposal-Only",
        },
    }
