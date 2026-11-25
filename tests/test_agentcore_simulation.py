"""
BlastGate Step 5 Security Tests — Local AgentCore Simulation (S5-028 through S5-034)
Tests end-to-end integration: incident -> diagnostics -> proposal -> Cedar -> broker -> receipt.
Verifies safety boundaries, unexpected outage vs scale-to-zero, and simulation honesty.
"""

import pytest

from agentcore.simulation.fixtures import (
    SYNTHETIC_INCIDENT_NOMINAL_STALL,
    SYNTHETIC_INCIDENT_HEALTHY_TARGET,
    SYNTHETIC_INCIDENT_STALE_TELEMETRY,
    SYNTHETIC_ATTACK_UNALLOWLISTED_ACTION,
)
from agentcore.simulation.simulator import AgentCoreLocalSimulator
from watchdog.evaluator import WatchdogEvaluator
from telemetry.validator import TelemetryValidator
from telemetry.heartbeat_repository import MockHeartbeatRepository


def test_s5_028_valid_synthetic_incident_reaches_diagnostics():
    """S5-028: Valid incident reaches diagnostics microservice and retrieves structured report."""
    sim = AgentCoreLocalSimulator()
    result = sim.run_simulation("Nominal Diagnostics Run", SYNTHETIC_INCIDENT_NOMINAL_STALL)

    assert result.diagnostics_response is not None
    assert result.diagnostics_response.get("statusCode") == 200
    diag = result.diagnostics_response.get("diagnostics", {})
    assert diag.get("incident_id") == SYNTHETIC_INCIDENT_NOMINAL_STALL["incident_id"]
    assert diag.get("health_evidence", {}).get("processing_state") == "STALLED"
    assert diag.get("suggested_action", {}).get("action_id") == "REPLACE_UNHEALTHY_ECS_WORKER"


def test_s5_029_valid_synthetic_proposal_reaches_broker():
    """S5-029: Valid remediation proposal passes Cedar policy and is authorized by broker."""
    sim = AgentCoreLocalSimulator()
    result = sim.run_simulation("Nominal Remediation Run", SYNTHETIC_INCIDENT_NOMINAL_STALL)

    assert result.cedar_decision == "PERMIT"
    assert result.broker_decision == "ALLOW"
    assert result.broker_reason_code == "AUTH_APPROVED"
    assert result.is_mutation_authorized is True


def test_s5_030_unsafe_proposals_denied_by_broker():
    """S5-030: Proposals targeting healthy or stale tasks are rejected by broker."""
    sim = AgentCoreLocalSimulator()

    # Healthy target denied
    res_healthy = sim.run_simulation("Healthy Target Run", SYNTHETIC_INCIDENT_HEALTHY_TARGET)
    assert res_healthy.broker_decision == "DENY"
    assert res_healthy.is_mutation_authorized is False

    # Stale telemetry denied
    res_stale = sim.run_simulation("Stale Telemetry Run", SYNTHETIC_INCIDENT_STALE_TELEMETRY)
    assert res_stale.broker_decision == "DENY"
    assert res_stale.is_mutation_authorized is False


def test_s5_031_no_synthetic_scenario_causes_real_aws_mutation():
    """S5-031: Simulator operates completely in-memory with zero network AWS mutation calls."""
    sim = AgentCoreLocalSimulator()
    result = sim.run_simulation("Mock Test", SYNTHETIC_INCIDENT_NOMINAL_STALL)
    # aws_request_id must be from mock executor
    assert result.broker_receipt.get("aws_request_id") == "req-simulated-stop-task-1"
    assert result.is_live_aws_mutation is False
    assert result.model_source == "SYNTHETIC_FIXTURE"
    assert result.cedar_evaluation_source == "LOCAL_CEDAR_SEMANTIC_EVALUATOR"
    assert any("[SIMULATION - MOCK]" in t for t in result.traces)


def test_s5_032_structured_receipt_distinguishes_authorization_from_execution():
    """S5-032: DecisionReceipt explicitly separates authorization decision from execution status."""
    sim = AgentCoreLocalSimulator()
    result = sim.run_simulation("Nominal Receipt Structure", SYNTHETIC_INCIDENT_NOMINAL_STALL)

    receipt = result.broker_receipt
    assert "decision" in receipt
    assert "execution_status" in receipt
    assert receipt["decision"] == "ALLOW"
    assert receipt["execution_status"] == "SUBMITTED"
    assert receipt["reason_code"] == "AUTH_APPROVED"


def test_s5_033_watchdog_distinguishes_outage_from_scaled_to_zero():
    """S5-033: Watchdog explicitly distinguishes intentional scale-to-zero from unexpected outage."""
    repo = MockHeartbeatRepository()
    validator = TelemetryValidator(repository=repo)
    evaluator = WatchdogEvaluator(telemetry_validator=validator)

    # 1. Intentional scale-to-zero (desired == 0, running == 0)
    eval_zero = evaluator.evaluate_service_health({"desired_count": 0, "running_count": 0, "task_arns": []})
    assert eval_zero["is_scaled_to_zero"] is True
    assert eval_zero["is_total_outage"] is False
    assert eval_zero["confirmed_stalled_count"] == 0

    # 2. Unexpected total service outage (desired == 6, running == 0)
    eval_outage = evaluator.evaluate_service_health({"desired_count": 6, "running_count": 0, "task_arns": []})
    assert eval_outage["is_scaled_to_zero"] is False
    assert eval_outage["is_total_outage"] is True
    assert "CRITICAL" in eval_outage["outage_reason"]
    assert eval_outage["confirmed_stalled_count"] == 0  # No tasks running to stop


def test_s5_034_simulation_honesty_tagged_fixtures():
    """S5-034: All simulation fixtures and traces are explicitly documented as synthetic/mocked."""
    sim = AgentCoreLocalSimulator()
    result = sim.run_simulation("Honesty Check", SYNTHETIC_INCIDENT_NOMINAL_STALL)
    traces_str = " ".join(result.traces)
    assert "Starting scenario" in traces_str
    assert "[SIMULATION - MOCK]" in traces_str
    assert "Simulator" in sim.__class__.__doc__


def test_s5_035_simulation_does_not_pass_on_predetermined_labels_alone():
    """S5-035: Invariant verification is evaluated dynamically by broker rules, not fixture labels."""
    sim = AgentCoreLocalSimulator()

    # Create a dynamic fixture without 'expected_model_decision'
    dynamic_incident = {
        "incident_id": "inc-00000099",
        "proposal": {
            "incident_id": "inc-00000099",
            "action_id": "REPLACE_UNHEALTHY_ECS_WORKER",
            # Healthy worker ARN in mock inventory
            "target_task_arn": "arn:aws:ecs:us-east-1:123456789012:task/blastgate-sandbox/00000000000000000000000000000002",
        }
    }
    result = sim.run_simulation("Dynamic Evaluation", dynamic_incident)
    # The broker must actively evaluate health state and refuse with ERR_TARGET_NOT_UNHEALTHY
    assert result.broker_decision == "DENY"
    assert result.broker_reason_code == "ERR_TARGET_NOT_UNHEALTHY"
    assert result.is_mutation_authorized is False
