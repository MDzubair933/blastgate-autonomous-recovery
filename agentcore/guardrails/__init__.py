"""
BlastGate Bedrock Guardrails Package
"""

from .config import (
    GUARDRAIL_NAME,
    BLOCKED_INPUT_MESSAGE,
    BLOCKED_OUTPUT_MESSAGE,
    get_create_guardrail_payload,
)

__all__ = [
    "GUARDRAIL_NAME",
    "BLOCKED_INPUT_MESSAGE",
    "BLOCKED_OUTPUT_MESSAGE",
    "get_create_guardrail_payload",
]
