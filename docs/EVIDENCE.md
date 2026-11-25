# Evidence index and provenance

Public artifact: [recorded-evidence.json](../evidence/public/recorded-evidence.json). The same bytes are bundled into the dashboard and its downloadable public asset.

| Evidence | Supported claim | Qualification |
|---|---|---|
| Step 6 historical report | Live harness diagnostics, scoped broker approval, ECS task stop and replacement | Historical narrative; does not establish automatic dispatch |
| Step 7 saved JSON | Eight recorded adversarial checks spanning live services and local engines | Mixed-layer suite, not eight complete live end-to-end attacks |
| Post-hardening saved JSON | Exact service rejection, sibling-health capacity rejection, nominal replacement and audit observations | Direct-service test run, separate from Step 7 |
| Unattended recovery saved JSON | Incident/session correlation, ALLOW, eight rule flags, target stopped, distinct healthy replacement, zero-worker cleanup | Watchdog acceleration is possible; intermediate traces are not fully retained |
| Local test suites | Deterministic implementation behavior and selected policy semantics | Not live service enforcement |
| Dashboard fixtures | Explain investigation and decision UX | Synthetic; no cloud outcomes can be inferred |

## Unattended run

Captured run timestamp: **2026-11-25T13:33:07Z**. Cleanup verification: **2026-11-25T13:36:50Z**. Public aliases `incident-unattended-01`, `session-unattended-01`, `worker-original-01` and `worker-replacement-01` refer consistently to the private run's identifiers.

The compact file records an `ALLOW`, all R1–R8 flags true, target stopped, replacement healthy, and desired/running/pending zero after cleanup. Its `reason_code` field contains the action ID, because the runner can fall back to `requested_action`; the public derivative preserves it verbatim rather than inventing `AUTH_APPROVED`. The stored audit digest may identify the cooldown authorization record rather than the final mutation record.

The runner does not call `invoke_harness` or directly invoke the broker. It can invoke the watchdog while awaiting an incident. Consequently this run supports automatic incident-to-agent-to-broker recovery; it does not independently establish a scheduled-watchdog-only experiment.

## Scenario distinctions

1. Live Guardrail and harness interception. A blocked input is not model compliance.
2. Live inventory denial plus a separate local healthy-target validation check.
3. Direct broker action rejection plus policy inspection; no captured unauthorized-action Gateway trace in this scenario.
4. **Local capacity quorum refusal. Live broker denied earlier with `ERR_TARGET_NOT_ALLOWLISTED` at zero fleet capacity.** The historical Scenario 4 does not prove a live broker quorum-branch denial.
5. Direct DynamoDB cooldown refusal plus broker rejection of an extra schema field.
6. Cached live broker replay receipt plus one historical mutation audit observation. ALLOW here is a cached result, not another task stop.
7. Local handling of synthetic poisoned logs and a live Guardrail call; no complete poisoned-CloudWatch-to-agent experiment.
8. Live Gateway MCP policy denial `-32002`. The signed caller is the configured developer identity, not the hypothetical role named in one evidence field.

The separate post-hardening run captures `ERR_CAPACITY_QUORUM_VIOLATION` from a direct live broker test. It does not rewrite Scenario 4's history. Saved Step 7 JSON and the prose report contain some identifiers from different runs; public summaries use the saved JSON outcomes rather than merging identifiers.

## Private originals and external report

Private originals remain unchanged under `evidence/step7/`, `evidence/post_hardening/`, and `evidence/unattended_recovery/`. Historical reports remain unchanged locally. They are not included in the curated release snapshot.

The final unattended verification report was found in Antigravity's external companion-artifact directory; the repository checkpoint only points outside the repository. It reports 251 passing tests and extra timing, audit and deployment details. The public docs summarize the captured JSON and inspected code instead of copying that report's unsupported signature, full-passivity, concurrency or cost language. The exact external location remains in the private checkpoint for the project owner.

## Redaction method

`python scripts/prepare_public_evidence.py` performs an offline allowlisted projection from private input files. It omits account IDs, ARNs, endpoints, role IDs, request IDs, original task/incident/session identifiers and attack payload text. Stable public aliases preserve run correlation; outcomes, timestamps and limitations remain.

These are derivative summaries, **not raw AWS responses**. Removing or replacing fields changes a payload's hash. No public derivative is asserted to validate a private event's original hash chain or carry an AWS digital signature. Original-source integrity and public-summary integrity are separate questions.
