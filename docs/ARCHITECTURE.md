# BlastGate architecture

The control boundary is the deterministic broker, not the model's reasoning. The only recovery action is `REPLACE_UNHEALTHY_ECS_WORKER`, implemented as a scoped task stop; the ECS service supplies the replacement.

## Components and responsibilities

| AWS component | Responsibility | Source |
|---|---|---|
| ECS Fargate worker | Process batches, publish application progress/health, read the sandbox fault control | [worker](../src/worker/main.py) |
| DynamoDB heartbeats | Timestamped application health evidence | [repository](../src/telemetry/heartbeat_repository.py) |
| Watchdog Lambda | Evaluate fleet telemetry and publish a stalled-worker metric | [watchdog](../src/watchdog/handler.py) |
| CloudWatch | Metric, alarm, bounded log retention | [monitoring stack](../infrastructure/cdk/stacks/monitoring_stack.py) |
| Incident ingestion Lambda | Validate alarm transition, deduplicate incident, emit incident-open event | [ingestion](../src/incidents/handler.py) |
| EventBridge | Route alarm transitions and `BlastGate.IncidentOpened` events | [broker stack](../infrastructure/cdk/stacks/broker_stack.py) |
| Dispatcher Lambda | Validate incident, acquire atomic dispatch lock, check cooldown, invoke harness | [dispatcher](../src/dispatcher/handler.py) |
| SQS DLQ | Preserve undelivered EventBridge target events | [broker stack](../infrastructure/cdk/stacks/broker_stack.py) |
| AgentCore Managed Harness / Nova Micro | Diagnose and propose through two approved tools | [harness](../agentcore/harness/config.py) |
| Bedrock Guardrails | Input attack/content controls; defense in depth | [guardrails](../agentcore/guardrails/config.py) |
| AgentCore Gateway / Cedar | Scoped principal, resource and proposal-action authorization | [policy source](../agentcore/policies/cedar_policies.cedar), [deployment renderer](../scripts/deploy_agentcore.py) |
| Diagnostics Lambda | Read-only incident, task, heartbeat and bounded untrusted-log context | [diagnostics](../src/diagnostics/handler.py) |
| Broker Lambda | Independently authorize R1–R8 and execute the bounded mutation | [handler](../src/broker/handler.py) |
| DynamoDB state/audit | Cooldown, idempotency, conditional append-only audit | [budget](../src/broker/budget.py), [audit](../src/broker/audit.py) |
| IAM permissions boundary | Limit runtime roles and separate proposal from execution | [IAM stack](../infrastructure/cdk/stacks/iam_stack.py) |

## Authorization and verification

```mermaid
sequenceDiagram
  participant Agent as Untrusted proposal
  participant Gateway as Cedar Gateway
  participant Broker as Independent broker
  participant State as DynamoDB state/audit
  participant ECS as ECS service
  Agent->>Gateway: Approved tool + structured action
  Gateway->>Broker: Scoped invocation
  Broker->>State: Record evaluation; inspect idempotency
  Broker->>ECS: Read exact service inventory
  Note over Broker: Validate fresh target and sibling telemetry, missing capacity, catalog and quorum
  Broker->>State: Atomically reserve cooldown
  Broker->>State: Persist pre-mutation authorization evidence
  alt Validation, reservation or pre-mutation audit fails
    Broker-->>Agent: DENY / ERROR; no mutation
  else Authorized
    Broker->>ECS: StopTask for one approved worker
    ECS->>ECS: Launch service replacement
    Broker->>ECS: Verify stopped target and new replacement identity
    Broker->>State: Record execution state and persistence warning if needed
  end
```

Specific replacement verification uses a pre-mutation inventory snapshot; a pre-existing healthy sibling cannot satisfy it. Immediate verification may return `SUBMITTED` while recovery is still in progress. An `ALLOW` receipt does not itself prove a healthy replacement.

## Dispatch and failure boundaries

The deployed source sets EventBridge target retries to zero, a 15-minute maximum event age, and a referenced pre-provisioned DLQ. Incident locks suppress duplicate dispatches. The current dispatcher stack does not set reserved concurrency; an earlier report's proposed concurrency cap must not be described as deployed configuration. The broker's cluster cooldown remains authoritative regardless of dispatch behavior.

The dispatcher does not consume the returned harness event stream before completing the dispatch lock. A completed dispatch is therefore not itself proof that tools or recovery succeeded. The unattended recording additionally observes broker audit and replacement heartbeat outcomes.

Logs and model output are untrusted. The Python local policy evaluator is a project model of selected Cedar semantics, not the native Cedar service. Hash linking is sequential within an execution context; no global ledger, digital signature or independent checkpoint service is claimed.

## Presentation boundary

The Next.js app contains no cloud execution endpoint. Demo view models enrich synthetic data for UI purposes; they are not raw backend-schema receipts. The recorded view imports an allowlisted public JSON derivative. Neither view performs AWS polling or remediation.
