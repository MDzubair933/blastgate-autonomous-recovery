# Submission asset inventory and placement

> Stage 2: [Final ten-screen gallery](GALLERY.md), [placement guide](PLACEMENT_GUIDE.md) and [media readiness report](MEDIA_READINESS_REPORT.md) supersede the screenshot selection below. Older assets are retained as historical captures.

All screenshots are genuine captures of the named interface. Architecture and cover graphics are authored illustrations, not execution evidence. Captions below are ready to reuse.

| File | Placement | Caption / evidence boundary |
| --- | --- | --- |
| [cover-1200x675.png](assets/cover-1200x675.png) | Optional project cover | “BlastGate — Autonomous Recovery. Provable Boundaries.” Authored cover graphic; no result claims. 1200×675, below 2 MB. |
| [architecture.png](assets/architecture.png), [SVG](assets/architecture.svg) | After architecture introduction | “Source architecture: Guardrails, tool allowlist, Cedar, independent broker and scoped IAM. Architectural order, not a live execution trace.” |
| [agentcore-recorded-execution.png](assets/agentcore-recorded-execution.png) | After recovery demonstration | “Actual saved AgentCore Harness execution, displayed in a local evidence viewer. Historical manually invoked Step 6 session; public aliases; not an AWS Console screenshot or a new execution.” |
| [recorded-recovery.png](assets/recorded-recovery.png) | Lead evidence image | “Historical November 25 AWS recovery in BlastGate's offline recorded-evidence view. Original target stopped; distinct replacement healthy. This interface makes no AWS calls.” |
| [adversarial-recorded-results.png](assets/adversarial-recorded-results.png) | Stress-test scope section | “Eight saved mixed-layer security checks, expanded to show scope. Only Scenario 1 retains an adversarial Harness response; these are not five agent prompt-response tests.” |
| [overview-simulated.png](assets/overview-simulated.png) | Optional product/UX image | “BlastGate simulated operations overview. Synthetic pre-remediation snapshot, not live AWS telemetry.” |
| [adversarial-local-fixtures.png](assets/adversarial-local-fixtures.png) | Optional supporting UI image | “Local synthetic adversarial fixtures. Model responses NOT TESTED; simulated broker outcomes are separate from AWS recordings.” |

The recorded-results image is a full-page capture and is intentionally long. Use the complete image or preserve the visible scope qualifications when choosing a publishing crop. Do not crop away “simulated,” “not tested” or historical labels.

## What the AgentCore image proves

The screenshot is of [recorded-execution-viewer.html](recorded-execution-viewer.html), a standalone local interface backed by [step6-execution-trace.json](evidence/step6-execution-trace.json) and [adversarial-prompt-audit.json](evidence/adversarial-prompt-audit.json). The first source derives selected values from the original saved Step 6 Harness event stream: diagnostics, proposal result and final assistant reply. It preserves SUBMITTED as the returned execution status and separates later recovery observations. The second source preserves the one genuine Step 7 input/block pair.

The original stream and operational logs remain private. Thinking blocks, account IDs, ARNs, endpoints and original incident/session/request/decision identifiers are omitted. Decision and request identifiers in the final assistant reply are replaced by explicit public aliases. Text and values are otherwise selected from the saved records. No console chrome, live status or agent response was invented.

No authenticated AWS Console session or original running-agent screenshot was accessible in the inspected browser surfaces and saved project assets. The recorded viewer does not claim to be a contemporaneous screenshot of an agent running. An authenticated historical trace capture, or a screenshot during an approved qualifying run, would remove uncertainty about the event's screenshot requirement.

## Capture and export notes

- Dashboard images: actual local Next.js interface, 1440px desktop width. Existing browser fallback fonts render where Google font faces are unavailable.
- AgentCore evidence viewer: actual rendered local interface at 1440px width, backed by the minimal recorded derivative. This adds no dashboard feature or backend endpoint.
- Architecture: authored SVG exported to a 1600×1000 PNG using the browser renderer. Source is retained for editable vector use.
- Cover: authored SVG exported at exactly 1200×675. It uses the existing BlastGate mark and palette, without third-party logo artwork.
- All files are checked for PNG dimensions and size, and manually reviewed as rendered. No image is a screenshot of private raw logs.
- The browser supplied JPEG-encoded screenshot bytes despite the requested filenames. Files were decoded and saved as genuine PNGs without visual edits; PNG signatures and dimensions are checked rather than trusting extensions.

Use [ASSET_MANIFEST.json](ASSET_MANIFEST.json) for exact dimensions, byte sizes and SHA-256 fingerprints. Fingerprints establish the packaged file bytes; they are not AWS signatures.
