# Final screenshot gallery

These ten 1600×900 captures are the authoritative Stage 2 gallery. Screens 01–05 are genuine browser captures of local, public-safe views of authentic saved AWS records. They are **not AWS Console screenshots**. Screens 06–10 are captures of the actual BlastGate dashboard, with its recorded/simulated labels preserved. No AWS workload was run to capture these images.

![Final screenshot contact sheet](assets/final/contact-sheet.png)

| # | Screenshot | Caption and scope |
| --- | --- | --- |
| 01 | [AgentCore recorded execution](assets/final/01-agentcore-recorded.png) | Recorded AWS Execution. Selected original Step 6 Harness stream fields; manually invoked earlier session, separate from unattended recovery. ALLOW/AUTH_APPROVED returned SUBMITTED, with verification still required. |
| 02 | [Actual adversarial answer](assets/final/02-adversarial-agent-response.png) | Recorded AWS Execution, ADV-03. Exact prompt and returned visible answer. The agent reports a missing incident; this does not establish a reached external-target validation branch. |
| 03 | [Actual Guardrail block](assets/final/03-guardrail-block.png) | Recorded AWS Execution, ADV-04. Actual saved input and Harness block, with guardrail_intervened. The source marks it pre-inference; it is not a model-generated refusal. |
| 04 | [Dispatcher observation](assets/final/04-dispatcher-recorded.png) | Recorded AWS Execution. Incident and dispatch-session aliases from the unattended run. The runner could accelerate the watchdog; no complete dispatcher log or intermediate timing is claimed. |
| 05 | [ECS replacement and health](assets/final/05-ecs-recovery-recorded.png) | Recorded AWS Execution. Original stopped, distinct replacement healthy, eight rule flags true. Cleanup is dated historical state. Captured reason_code contains the action ID. |
| 06 | [Dashboard Overview](assets/final/06-overview-simulated.png) | Simulated operations. Synthetic pre-remediation fleet and incident snapshot, not live AWS state. |
| 07 | [Recorded AWS Recovery](assets/final/07-recorded-aws-recovery.png) | Actual offline dashboard showing historical recorded AWS results. This view makes no AWS calls. |
| 08 | [R1–R8 Security Rules](assets/final/08-rules-simulated.png) | Explanatory dashboard definitions and local verification references. PASS labels here are not eight new live test results. |
| 09 | [Adversarial Tests dashboard](assets/final/09-adversarial-local-fixtures.png) | Local synthetic fixtures; model responses NOT TESTED. Separate from the newer saved Harness prompt runs. |
| 10 | [Audit Explorer](assets/final/10-audit-simulated.png) | Simulated audit records and hashes. This is not a live DynamoDB or global-ledger verification screen. |

The architecture [PNG](assets/architecture.png)/[SVG](assets/architecture.svg) and [1200×675 cover](assets/cover-1200x675.png) are reused after review. They are authored illustrations, not console evidence. [Exact placement guide](PLACEMENT_GUIDE.md) · [Media readiness](MEDIA_READINESS_REPORT.md).

Supplement: [all eight rules in one full-page capture](assets/final/rules-all-full.png). This taller image preserves every rule row; the standard 1600×900 frame shows the top of the same list.
