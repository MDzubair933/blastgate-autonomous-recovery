# Local reproduction and operator deployment

## Dashboard without AWS

Use Node.js 24 (verified locally: 24.18.0), or Node.js 22.12+ with npm. The working project has a lockfile; a clean machine needs dependency installation:

```powershell
cd dashboard
npm ci
npm test
npx tsc --noEmit --incremental false
npm run build
npm start -- --hostname 127.0.0.1
```

For editing use `npm run dev -- --hostname 127.0.0.1`. The application runs at [localhost](http://127.0.0.1:3000). Build and development servers should not share the same `.next` directory concurrently. All source files are UTF-8. The public recording is bundled; original private evidence is unnecessary to run the dashboard.

## Python tests

The verified workstation uses Python 3.14.7, boto3/botocore 1.43.126 and pytest 9.2.0. Lambda and worker deployment target Python 3.12. The older minimum boto3 version in requirements does not alone guarantee that new AgentCore Harness APIs are available.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r infrastructure/cdk/requirements.txt -r src/broker/requirements.txt pytest
.\.venv\Scripts\python.exe -m pip install boto3==1.43.126 botocore==1.43.126
$env:AWS_EC2_METADATA_DISABLED = 'true'
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

The full suite expects generated CloudFormation templates in `infrastructure/cdk/cdk.out` and Lambda archives in `dist/lambda`. A clean checkout must generate these before full regression. Some smoke tests automatically build archives if absent; that performs a dependency installation. For a code-only offline pass select tests that do not require generated assets, for example `tests/test_backend_hardening.py tests/test_dispatcher.py tests/test_broker_capacity.py`.

Generation commands, run locally after dependency/tool setup:

```powershell
python scripts/package_lambdas.py
cd infrastructure/cdk
npx cdk synth --quiet
```

Install a compatible CDK CLI matching the installed cloud-assembly schema before that command; no CLI version or fresh installation is verified here. `cdk synth` may perform context lookups when context is missing. Review the app and context before using credentials. This finalization did not synthesize or install CDK.

## Deploying to a separate AWS sandbox

Deployment is an operator-controlled, billable activity. It was not executed during frontend finalization. The public source snapshot substitutes example deployment identifiers; it is not a deploy-as-is connection to the original account.

1. Choose an isolated account and region; configure AWS credentials outside the repository. Review account constants, ARNs, Gateway/harness identifiers, Cedar role principal binding, image digest and local paths throughout `infrastructure`, `agentcore`, `src` and deployment scripts.
2. Review runtime and CloudFormation execution boundaries. Do not follow superseded historical AdministratorAccess bootstrap advice. Apply the reviewed restricted execution policy and runtime boundary with the account operator.
3. Install Python dependencies and compatible CDK CLI, build all five Lambda archives, then synthesize and inspect the six templates.
4. Deploy foundation stacks in dependency order: network/storage/monitoring/IAM. Build and push the worker image through the reviewed CodeBuild script; configure its immutable digest before activating workers.
5. Deploy worker service at desired count zero and broker/diagnostics/watchdog/ingestion. Account for dispatcher prerequisites: the stack references an existing encrypted dispatch DLQ and the configured harness ARN.
6. Review `scripts/deploy_agentcore.py` dry-run output. Its `--confirm` path creates Guardrails, policy engine, Gateway targets and harness. Provisioning order must account for the broker/dispatcher/harness references; inspect outputs before connecting the final dispatcher configuration.
7. Verify the actual Gateway ARN, principal role ID, Guardrail version, policy `ENFORCE` mode and narrow allowed tools. Do not reuse example or original-account identifiers.
8. Enable the incident dispatch wiring only after IAM, cooldown and failure-path review. EventBridge retries are zero; a DLQ is not automatic recovery from application-level failures returned with Lambda HTTP-style status fields.
9. A controlled live test can scale to six, inject one stall, observe recovery and restore zero tasks. Review `scripts/run_unattended_recovery_test.py` first: it mutates AWS, can invoke the watchdog, writes private evidence and runs cleanup in `finally`. Never run it as an ordinary local test.
10. Verify zero desired/running/pending tasks and absent fault injection afterward. `scripts/cleanup.py` defaults to dry-run; review `--confirm` separately. Scale-down is not destruction of all resources or proof of a zero bill.

Private reports retain original deployment commands and identifiers for the owner. The public snapshot deliberately requires account-specific configuration and operator review; clean-account cloud deployment was not revalidated in this work.
