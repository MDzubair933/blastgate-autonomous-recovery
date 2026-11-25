# Public release preparation

The owner selected **MIT** during finalization; see [LICENSE](../LICENSE). Dependencies retain their own licenses. No publication, Git initialization, push or hackathon submission is performed by this workflow.

## Deliverable

`release/blastgate-review/` and `release/blastgate-review.zip` are separate curated derivatives. Prepare them with `python scripts/prepare_release.py` after public evidence, docs and screenshots are finalized. The archive contains a file-level SHA-256 manifest.

The original working tree is **not** a safe upload target. It retains private evidence and historical operational reports. `.gitignore` is preventive hygiene, not a substitute for a reviewed allowlist or Git-history inspection.

Included: backend/source/contracts/tests, CDK source, selected operator scripts, dashboard source and npm lockfile, current public docs, MIT license, genuine dashboard screenshots, and public evidence derivatives. Original deployment account/resource bindings and personal workstation paths are replaced by examples in the copied source only. Review/configure these substitutions before deployment; the original frozen backend remains unchanged.

Excluded: raw AWS evidence, older account-only-redacted files, external companion artifacts, historical operational reports, support and personal-account material, credentials, local environments, node_modules, .next, CDK output, Lambda ZIPs/staging, caches, logs and local input payloads. The generated review ZIP is the only intended archive; it is itself inspected by the local publication checks.

## Review gates

1. Confirm the MIT notice and contributor attribution meet the owner's requirements.
2. Review the file manifest and archive contents, not the whole workspace folder.
3. Verify public JSON outcomes match the private originals without copying identifiers or treating derivative hashes as original event signatures.
4. Inspect screenshot content and mode labels. These are local dashboard captures, not AWS Console proof.
5. Review secrets, identifiers, personal data, dependency advisories and third-party license obligations. A regex pass cannot guarantee security.
6. Configure and test the example source separately if a clean-account cloud deployment is intended. It was not redeployed during this work.
7. Antigravity/the owner should inspect the actual Git repository and its history before pushing. This workspace has no Git metadata to audit.

Any unresolved verification or dependency advisory gap remains explicit in [the finalization report](FINALIZATION_REPORT.md). Do not convert “prepared for review” into an unconditional security clearance.
