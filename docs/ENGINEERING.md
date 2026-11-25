# Engineering challenges and solutions

## A running task can be a stalled application

The worker reports processing progress independently of ECS task state. A fresh heartbeat can report STALLED even while the container is RUNNING. Old heartbeat evidence is rejected rather than treated as sufficient authorization to stop a task.

## Diagnosis and mutation require different authority

The harness has two scoped tools. Gateway principal/action controls and a separate broker prevent model text from becoming execution authority. The broker checks exact service membership and live application-health evidence instead of trusting model-provided capacity or emergency claims.

## Capacity arithmetic needs complete inputs

An early implementation checked the target but did not fully account for missing desired workers and unhealthy siblings. Backend hardening added missing-capacity accounting and fresh telemetry checks for running siblings. The public evidence preserves both the original Scenario 4 limitation and the later separate live capacity denial.

## Replacement must mean a new task

Existing healthy siblings cannot prove recovery. The hardened broker snapshots pre-mutation task identities and requires a genuinely new healthy replacement. The recorded unattended result identifies a distinct replacement; its public alias is consistently separate from the original worker.

## A dispatcher closes the incident-to-agent gap

Incident ingestion emits an EventBridge incident-open event. A dedicated dispatcher uses an atomic incident lock, checks cooldown and invokes the Managed Harness. It does not obtain ECS mutation authority. The unattended runner did not invoke the harness or broker, although watchdog acceleration remains a disclosed experimental qualification.

## AWS integration details matter

The historical deployment reports describe Nova Micro tool-name compatibility, namespaced allowed-tool selectors, Guardrail topic limits, Cedar principal matching and Linux/Python 3.12 Lambda dependency packaging including `typing_extensions`. These are implementation lessons from the original AWS work, not operations repeated during frontend finalization.

## Evidence needs its own model

Synthetic receipts, local policy checks, direct Lambda/DynamoDB tests and complete recovery observations answer different questions. The dashboard now distinguishes them explicitly. Public projections preserve captured codes and limitations; hashes are not called signatures, and missing per-stage timestamps are not replaced with invented timings.
