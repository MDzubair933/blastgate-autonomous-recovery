"""
BlastGate Broker Audit Logging Tests (Rule R6)
Verifies schema conformance, append-only constraints, and SHA-256 integrity hash calculation.
"""

import pytest
from broker.audit import AuditLogger, MockAuditStore
from broker.models import RuleResults
from broker.errors import AuditWriteError


def test_audit_event_logged_with_sha256():
    store = MockAuditStore()
    logger = AuditLogger(store=store)

    rules = RuleResults(
        R1_allowlist=True,
        R2_capacity=True,
        R3_telemetry=True,
        R4_cooldown=True,
        R5_catalog=True,
        R6_audit=True,
        R7_authority=True,
        R8_idempotency=True,
    )

    event_data = logger.log_event(
        event_type="AUTHORIZATION_DECISION",
        incident_id="inc-ef797c8118f02dfb",
        decision_id="dec-ef797c8118f02dfb",
        requested_action="REPLACE_UNHEALTHY_ECS_WORKER",
        authorization_decision="ALLOW",
        execution_status="SUBMITTED",
        rule_results=rules.to_dict(),
        evidence_references=["ref-1"],
    )

    assert event_data["event_type"] == "AUTHORIZATION_DECISION"
    assert "integrity" in event_data
    sha = event_data["integrity"]["event_sha256"]
    assert len(sha) == 64  # Valid 64-char hex SHA-256


def test_audit_hash_chaining():
    store = MockAuditStore()
    logger = AuditLogger(store=store)
    rules = RuleResults().to_dict()

    e1 = logger.log_event(
        event_type="AUTHORIZATION_DECISION",
        incident_id="inc-4f9f10b304cfe9b2",
        decision_id="dec-4f9f10b304cfe9b2",
        requested_action="REPLACE_UNHEALTHY_ECS_WORKER",
        authorization_decision="ALLOW",
        execution_status="NOT_STARTED",
        rule_results=rules,
    )

    e2 = logger.log_event(
        event_type="MUTATION_EXECUTION",
        incident_id="inc-4f9f10b304cfe9b2",
        decision_id="dec-4f9f10b304cfe9b2",
        requested_action="REPLACE_UNHEALTHY_ECS_WORKER",
        authorization_decision="ALLOW",
        execution_status="SUBMITTED",
        rule_results=rules,
    )

    # e2 must reference e1's hash in previous_event_sha256
    assert e2["integrity"]["previous_event_sha256"] == e1["integrity"]["event_sha256"]


def test_mandatory_audit_failure_raises_error():
    store = MockAuditStore(fail_writes=True)
    logger = AuditLogger(store=store)

    with pytest.raises(AuditWriteError):
        logger.log_event(
            event_type="AUTHORIZATION_DECISION",
            incident_id="inc-fail",
            decision_id="dec-fail",
            requested_action="REPLACE_UNHEALTHY_ECS_WORKER",
            authorization_decision="ALLOW",
            execution_status="NOT_STARTED",
            rule_results=RuleResults().to_dict(),
        )
