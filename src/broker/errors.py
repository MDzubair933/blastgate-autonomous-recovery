"""
BlastGate Broker Error Hierarchy
Maps domain and security validation errors directly to authoritative decision receipt reason codes.
"""

from typing import Optional, Dict, Any


class BrokerError(Exception):
    """Base exception for all Remediation Broker refusals and errors."""
    def __init__(
        self,
        message: str,
        reason_code: str = "ERR_INTERNAL_EXCEPTION",
        decision: str = "DENY",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.decision = decision
        self.details = details or {}


class RequestValidationError(BrokerError):
    """Raised when an incoming proposal violates remediation_request.schema.json."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_UNAUTHORIZED_ACTION",
            decision="DENY",
            details=details
        )


class UnauthorizedActionError(BrokerError):
    """Raised when requested action is not registered in the authoritative catalog (Rule R1 / R5)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_UNAUTHORIZED_ACTION",
            decision="DENY",
            details=details
        )


class TargetNotAllowlistedError(BrokerError):
    """Raised when target cluster, service, or ARN is outside the sandbox perimeter (Rule R1)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_TARGET_NOT_ALLOWLISTED",
            decision="DENY",
            details=details
        )


class CapacityQuorumError(BrokerError):
    """Raised when proposed action violates healthy worker quorum or max unavailable percent (Rule R2)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_CAPACITY_QUORUM_VIOLATION",
            decision="DENY",
            details=details
        )


class TargetNotUnhealthyError(BrokerError):
    """Raised when target worker is not confirmed unhealthy by trusted telemetry (Rule R3)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_TARGET_NOT_UNHEALTHY",
            decision="DENY",
            details=details
        )


class StaleTelemetryError(BrokerError):
    """Raised when application health telemetry is older than the freshness threshold (Rule R3)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_STALE_TELEMETRY",
            decision="DENY",
            details=details
        )


class CooldownActiveError(BrokerError):
    """Raised when a remediation occurred within the rolling 600-second window (Rule R4)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_COOLDOWN_ACTIVE",
            decision="DENY",
            details=details
        )


class UnregisteredProcedureError(BrokerError):
    """Raised when requested runbook or action configuration does not match catalog (Rule R5)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_UNREGISTERED_PROCEDURE",
            decision="DENY",
            details=details
        )


class AuditWriteError(BrokerError):
    """Raised when a mandatory immutable audit write fails (Rule R6)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_AUDIT_WRITE_FAILED",
            decision="DENY",
            details=details
        )


class FailClosedTimeoutError(BrokerError):
    """Raised when a distributed check or lock operation exceeds the timeout threshold."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_FAIL_CLOSED_TIMEOUT",
            decision="DENY",
            details=details
        )


class InternalBrokerError(BrokerError):
    """Raised on internal system or unexpected operational exceptions."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            reason_code="ERR_INTERNAL_EXCEPTION",
            decision="ERROR",
            details=details
        )
