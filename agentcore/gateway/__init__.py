"""
BlastGate AgentCore Gateway Package
Manages Gateway configuration, tool definitions, and Lambda target bindings.
"""

from .config import (
    GATEWAY_NAME,
    GATEWAY_ROLE_ARN,
    DIAGNOSTICS_FUNCTION_ARN,
    BROKER_FUNCTION_ARN,
    POLICY_ENGINE_ARN,
    get_create_gateway_payload,
    get_diagnostics_target_payload,
    get_broker_target_payload,
)

__all__ = [
    "GATEWAY_NAME",
    "GATEWAY_ROLE_ARN",
    "DIAGNOSTICS_FUNCTION_ARN",
    "BROKER_FUNCTION_ARN",
    "POLICY_ENGINE_ARN",
    "get_create_gateway_payload",
    "get_diagnostics_target_payload",
    "get_broker_target_payload",
]
