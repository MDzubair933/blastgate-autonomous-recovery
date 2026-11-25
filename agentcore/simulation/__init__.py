"""
BlastGate AgentCore Simulation Package
Deterministic local orchestrator simulating the full AgentCore Harness -> Gateway -> Cedar -> Broker boundary.
"""

from .fixtures import (
    SYNTHETIC_INCIDENT_NOMINAL_STALL,
    SYNTHETIC_INCIDENT_HEALTHY_TARGET,
    SYNTHETIC_INCIDENT_STALE_TELEMETRY,
    SYNTHETIC_ATTACK_POISONED_LOG,
    SYNTHETIC_ATTACK_EXECUTIVE_OVERRIDE,
    SYNTHETIC_ATTACK_UNALLOWLISTED_ACTION,
)
from .simulator import AgentCoreLocalSimulator, SimulationResult

__all__ = [
    "SYNTHETIC_INCIDENT_NOMINAL_STALL",
    "SYNTHETIC_INCIDENT_HEALTHY_TARGET",
    "SYNTHETIC_INCIDENT_STALE_TELEMETRY",
    "SYNTHETIC_ATTACK_POISONED_LOG",
    "SYNTHETIC_ATTACK_EXECUTIVE_OVERRIDE",
    "SYNTHETIC_ATTACK_UNALLOWLISTED_ACTION",
    "AgentCoreLocalSimulator",
    "SimulationResult",
]
