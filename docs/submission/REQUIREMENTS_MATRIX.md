# Official submission requirements matrix

Reviewed November 25, 2026 against the current event [About page](https://builder.aws.com/build/hackathons/61c39fba-1383-37e7-bd5c-3f9d889d89fc/agents-your-rules-bedrock-managed-agents-build) and [Rules tab](https://builder.aws.com/build/hackathons/61c39fba-1383-37e7-bd5c-3f9d889d89fc/agents-your-rules-bedrock-managed-agents-build?tab=rules). Rules were read in the rendered interface. They supersede historical planning documents.

**Adversarial prompt requirement satisfied:** 8 genuine adversarial Harness executions recorded (5 verified in-context model inference refusals + 3 pre-inference Guardrail blocks). See [ADVERSARIAL_EVIDENCE_AUDIT.md](ADVERSARIAL_EVIDENCE_AUDIT.md).

| Mandatory item | State | BlastGate artifact or remaining action |
| --- | --- | --- |
| Supported managed-agent platform; one defined job | Evidenced & Verified | AgentCore Harness configuration, source, [recorded Step 6 trace](evidence/step6-execution-trace.json), and unattended closed-loop recovery verification; replace an unhealthy sandbox ECS worker. |
| Plain-language access, refusal and edge-case rules | Prepared | R1–R8 in [submission draft](BUILDER_CENTER_DRAFT.md), [contract](../../contracts/OPERATIONAL_RULES.md) and [security notes](../SECURITY.md). |
| Rule enforcement and architecture | Prepared | Per-rule table in draft; [architecture SVG](assets/architecture.svg) and [PNG](assets/architecture.png). |
| At least five adversarial agent prompts with actual responses | **Verified (100%)** | 8 genuine Harness prompt executions recorded (5 verified model inference responses from Nova Micro + 3 pre-inference Guardrail blocks). Full prompts, session IDs, responses, and thinking captured in [audit](ADVERSARIAL_EVIDENCE_AUDIT.md) and [evidence projection](evidence/adversarial-prompt-audit.json). |
| Include prompt injection | **Verified (100%)** | Fully evidenced by `ADV-01` (payload-embedded injection analyzed and safely refused by model) and `AP-01` (instruction override blocked at input perimeter). |
| Explain each attack and response | **Verified (100%)** | Comprehensive attack explanations, security boundaries, and model thinking/responses documented in [audit](ADVERSARIAL_EVIDENCE_AUDIT.md). |
| Build process and failures/fixes | Prepared | Draft engineering section and [engineering notes](../ENGINEERING.md). |
| Working-agent screenshot | Recorded evidence asset prepared; acceptance unconfirmed | [Actual saved AWS execution viewer capture](assets/agentcore-recorded-execution.png), explicitly historical and derivative. No accessible authenticated AWS Console trace or original running-session screenshot was found in the inspected sources. A contemporaneous console/running-session capture remains the strongest way to remove ambiguity. |
| Repository or demo link | **Missing** | Public repository URL not supplied or published. Placeholder is explicit. Local dashboard is not a public demo. |
| OSI-approved license if using repository | Prepared locally | MIT [LICENSE](../../LICENSE) included; repository must actually be public when submitted. |
| Written Builder Center project with all required content | Draft prepared; publication pending | [Draft](BUILDER_CENTER_DRAFT.md) and [field mapping](BUILDER_CENTER_FIELDS.json). No post created. |
| Original, not previously published agent | Owner confirmation needed | No public publication was performed in this work; that does not establish the project's entire publication history or originality. |
| Submit within event window | Owner action pending | Deadline December 2, 2026, 11:59 p.m. Pacific: December 3, 2026, 13:29 IST. Publication remains intentionally stopped. |
| Builder Center profile, AWS account, adult eligibility | Owner confirmation needed | Profile/account/age eligibility not established by project files. Event interface shows “Join”; registration not performed. |
| Residence and employment eligibility | Owner confirmation needed | Owner must check current Rules exclusions, including Amazon/affiliate employment, immediate family and household restrictions. No residence inferred from timezone. |
| One entry; team size at most five | Owner confirmation needed | Team roster and other entries not verified. |
| Rights to project and included material | Owner confirmation needed | Locally authored diagram/cover and genuine dashboard captures prepared; third-party ownership/permissions require owner confirmation. |
| Public video and media rights if video used | Not applicable currently | No video prepared. If later used, ensure visibility and rights to included third-party media. |
| Finalist verification / prize obligations if selected | Conditional owner action | Rules describe identity/eligibility verification and prize/tax requirements. Not needed to fabricate or collect those records in this local package. |

The rules make qualification pass/fail. The four scoring categories are equally weighted: innovation, craft, usefulness and storytelling. The draft addresses them through independent enforcement, an observed recovery, a concrete operations problem and documented failures. No score or qualification is promised.

## Editor and taxonomy verification

The event's “Your project” tab requires joining. No terms were accepted and no draft was saved on AWS. Therefore, the only field limit used here is the requested short-description limit of 512 characters; other editor limits and mandatory form controls remain unverified.

Recommended topic slugs are from the current [Builder Center taxonomy](https://builder.aws.com/learn/topics/amazon-bedrock-agents?tab=article): `amazon-bedrock-agents`, `amazon-bedrock`, `agentic-ai`, `aws-lambda`, `devops`. The actual editor's selectable subset and tag limit must still be checked. Do not invent a required event tag beyond what the form offers.
