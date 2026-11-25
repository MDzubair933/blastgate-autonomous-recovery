# UI refinement — November 25, 2026

The public presentation pass keeps the existing dark canvas, gold accent and serif display identity. It replaces repeated cards with flat summary bands and ruled rows, increases spacing, and gives each focus page one clear outcome.

- **Overview:** cleaner fleet strip, shorter incident rows, shared security definitions and full lifecycle behind disclosures. Worker and incident navigation remain available.
- **Agent Console:** prominent ALLOW/DENY outcome; authorization and mutation remain visibly separate. Rule evaluations, metadata, step evidence and raw JSON are collapsed by default. Receipt selection and JSON copying remain available.
- **Adversarial Tests:** six compact scenario rows with dynamic filter counts. Local simulation, untested model responses and the untested cloud probe remain explicit. Expand a row for the complete explanation and payload.
- **Recorded AWS evidence:** recovery results lead the page. All eleven stages, source references, identifiers, original limitations and post-hardening checks remain accessible. Watchdog acceleration and Scenario 4's earlier live denial remain visible qualifications.
- **Deployment:** dated cleanup and reported verification totals lead. Cost remains “Not measured,” with assumptions behind a disclosure.
- **Shared navigation:** quieter mode controls, fewer status pills and no unrelated sidebar selection while viewing recorded evidence.

## Text density

Browser-measured words in the main content at 1440px, default state, including raw JSON when previously visible. This measures visible copy across the page, not just the first viewport. Detailed evidence remains available by expanding disclosures.

| View | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Overview | 237 | 113 | 52% |
| Agent Console | 777 | 118 | 85% |
| Adversarial Tests | 449 | 110 | 76% |
| Deployment | 201 | 105 | 48% |
| Recorded AWS evidence | 479 | 199 | 58% |

The larger reductions on technical pages come from collapsing JSON and repeated explanations. No evidence records were deleted.

## Screenshot selection

1. **Recorded AWS evidence** — strongest submission lead: actual captured recovery, broker decision and replacement outcome. Use [desktop preview](assets/recorded-preview.png) for a README hero; [full desktop](assets/recorded-desktop.png) includes scenario scope.
2. **Overview** — best product introduction and visual summary: [desktop](assets/overview-desktop.png), [phone](assets/overview-390.png).
3. **Adversarial Tests** — best compact safety demonstration: [desktop](assets/adversarial-tests-desktop.png). Keep “simulated” and “NOT TESTED” in frame.
4. **Agent Console** — best architecture explanation: [desktop](assets/agent-console-desktop.png). Capture the lifecycle with AUTH GATE and MUTATION visible.
5. **Deployment** — useful supporting record: [desktop](assets/deployment-desktop.png). Preserve the historical and unmeasured-cost labels.

Desktop captures use 1440 × 1000 viewports; phone and tablet checks use 390 × 844 and 768 × 1024. Full-page screenshots can be taller. Default disclosures are closed.

Google font faces were unavailable in the capture browser; these screenshots use the existing browser fallback font stacks.

## Verification and unchanged boundaries

- Frontend test suite: 21 tests passed. Production build and TypeScript validation passed.
- Five focus views checked on desktop, tablet and phone without horizontal page overflow. Mobile navigation closes after selection. Keyboard receipt disclosure and adversarial filtering verified in the rendered UI.
- SHA-256 comparison: all 121 protected backend, infrastructure, provider and evidence files unchanged, including the public evidence JSON copies.
- No backend logic, AWS resources, evidence values, test fixture outcomes or technical claims were changed. No AWS calls were made for this refinement.
- Existing typography was retained intentionally; the existing narrowly scoped font exceptions remain. No new design-hook suppressions were added in this pass.
