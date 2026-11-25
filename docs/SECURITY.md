# Security, privacy and honest limits

## Trust model

Operator instructions, application logs, retrieved prose and model output cannot grant recovery authority. The model can access scoped diagnostics and proposal tools. Cedar controls Gateway access; the broker independently validates target membership, fresh application health, sibling health, capacity, catalog binding, cooldown and idempotency before scoped ECS execution.

The backend is frozen for this finalization. See the existing [operational rules](../contracts/OPERATIONAL_RULES.md), [security invariants](../contracts/SECURITY_INVARIANTS.md) and [threat model](../contracts/threat_model.md). Those specifications include historical language; where evidence coverage differs, the scoped [evidence index](EVIDENCE.md) governs what this presentation claims to demonstrate.

## Residual limits

- AWS control-plane consistency, network failures, telemetry delivery and independent operators remain distributed-system risks. No future fleet availability guarantee is made.
- The sandbox relies on trusted worker telemetry and deployment configuration. A fully compromised worker or administrator is outside the demonstrated model-output attack boundary.
- The agent has no direct ECS mutation authority. Other roles legitimately write telemetry, incidents, locks and logs; saying only the broker can perform **any** AWS mutation would be inaccurate.
- SHA-256 events provide tamper-evidence within the execution context. They are not digital signatures, a globally chained ledger or protection against an account administrator replacing both data and controls.
- Pre-execution audit failure blocks mutation. Post-execution failure must preserve the authentic execution status and expose `audit_persisted` / `audit_warning`; it cannot undo a task stop.
- Dispatch lock completion is not end-to-end recovery confirmation. EventBridge delivery policy and Lambda application-error handling are different boundaries. No guaranteed automatic retry after cooldown is claimed.
- A zero-worker cleanup snapshot is historical. Billing is not connected. No current zero-spend or hard billing cutoff claim is made.

## Publication handling

Private raw evidence, old account-only-redacted files, operational reports, local environments, generated packages and caches are excluded from the curated public snapshot. Public evidence is a reviewed allowlisted projection, with aliases and limitations. Original evidence remains private and unchanged.

The source snapshot replaces original deployment account/resource bindings and workstation paths with examples. These copies are for review and require operator configuration before deployment. Source digests, dependencies and third-party notices need their own provenance review.

Pattern scans help identify likely credentials and identifiers; they do not prove absence of secrets. Archive contents, Git history, dependencies, screenshots, logs, personal information and account-specific configuration require review. This workspace has no Git metadata, so history/remotes cannot be cleared here.

The owner selected MIT; the root license records that choice. Report suspected security defects privately to the project owner; no public vulnerability-contact address is invented here.
