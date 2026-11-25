# BlastGate demonstration

Run the local dashboard with no AWS credentials. A suggested four-minute walkthrough:

1. **Problem (30s):** Explain that ECS `RUNNING` does not prove the processing loop is healthy. The model proposes a replacement; an independent broker controls the mutation.
2. **Simulated operations (60s):** Inspect stalled `task-0001`, its fresh STALLED telemetry, linked incident and untrusted logs. Open the decision timeline. Distinguish authorization from simulated execution and simulated verification. Select a resolved incident without a receipt to demonstrate the honest empty state.
3. **Rules (30s):** Open Security Rules. R2 combines ≥4 projected healthy workers and ≤20% unavailability. R4 is a 600-second cluster reservation; no executive or prompt override can grant authority.
4. **Recorded AWS evidence (90s):** Switch modes. Follow fault → watchdog → alarm → incident → EventBridge → dispatcher → harness → Gateway → broker → replacement → healthy heartbeat. Select stages to see the exact evidence category. Show correlated aliases and captured cleanup timestamp. Disclose watchdog acceleration, missing intermediate timestamps and absent complete transcript.
5. **Adversarial proof (30s):** Show Scenario 4 expanded by default. Explain local quorum refusal versus earlier live inventory refusal, then the separate post-hardening live capacity test. Show the live Gateway denial separately from local policy tests.
6. **Close (30s):** The dashboard cannot mutate AWS. Show recorded cleanup, usage-dependent cost disclosure and public JSON download. Describe residual distributed-system and privileged-operator limitations.

## Screenshots and recording

Screenshots in `docs/assets/` are captures of the actual local dashboard, not AWS Console screenshots. Each recorded-evidence screen displays its source and historical nature. Do not remove the mode label when preparing slides or video. A live dashboard fixture is not evidence that AWS ran at capture time.

Suggested frames: desktop overview, recorded recovery, Scenario 4 scope, worker/incident detail, mobile recorded view. Use the exact existing recording; do not replay animations with invented AWS timings or fabricated console transactions.

## Submission materials

Use the README as the project brief, the architecture diagram as the system explanation, the public evidence JSON as the inspectable derivative, and this script as narration. Confirm current event requirements in the submission portal before submission; historical hackathon research documents are not a current rules guarantee. Publication and submission are handled separately by the owner through Antigravity.
