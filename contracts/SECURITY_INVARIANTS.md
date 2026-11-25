# BLASTGATE FORMAL SAFETY INVARIANTS & CAPACITY MODEL
**Standard Version:** 1.0.0  
**Status:** AUTHORITATIVE SPECIFICATION  
**Scope:** BlastGate Core Authorization Engine  

---

## 1. Core Safety Invariants

BlastGate enforces four fundamental system invariants. A request is authorized if and only if all invariants are satisfied simultaneously.

### Invariant 1: Action Set Containment (Mutation Allowlist)
Let $\mathcal{A}_{\text{approved}}$ be the set of valid, catalog-registered operations:
$$\mathcal{A}_{\text{approved}} = \{ \text{REPLACE\_UNHEALTHY\_ECS\_WORKER} \}$$
For any proposed action $a$:
$$a \in \mathcal{A}_{\text{approved}}$$
**Prohibited Operations:** Under no circumstances shall the BlastGate runtime authorize or execute:
- Any IAM mutation ($\text{iam:*}$)
- Any production database operation ($\text{rds:*}$, $\text{dynamodb:DeleteTable}$, etc.)
- Any out-of-scope compute mutation ($\text{ec2:TerminateInstances}$, unapproved ECS clusters)
- Arbitrary code execution, container shell execution, or policy changes.

### Invariant 2: Rolling Temporal Cooldown
Let $\tau_{\text{window}} = 600 \text{ seconds}$. Let $\mathcal{H}(t)$ be the set of all authorized remediation events timestamped within the interval $[t - \tau_{\text{window}}, t]$ across cluster $\mathcal{C}$:
$$|\mathcal{H}(t)| \le 1$$
No remediation event may be authorized if an authorized event has already occurred within the rolling 600-second window on the protected cluster.

### Invariant 3: Minimum Healthy Capacity & Quorum Safety
Let:
- $N \in \mathbb{N}^+$: The trusted desired service capacity from the active ECS service definition ($N = 6$ in baseline sandbox).
- $U \subset \mathcal{W}$: The set of currently unavailable or degraded workers in the service, confirmed via trusted infrastructure state.
- $T \subset \mathcal{W}$: The set of additional workers targeted by the proposed action ($|T| = 1$ for `REPLACE_UNHEALTHY_ECS_WORKER`).
- $H_{\min} \in \mathbb{N}^+$: The configured minimum healthy worker threshold ($H_{\min} = 4$).
- $P_{\max} \in [0, 100]$: The maximum allowable projected unavailability percentage ($P_{\max} = 20\%$).

We define:
$$\text{Projected Unavailable Workers} = |U \cup T|$$
$$\text{Projected Unavailable Percentage} = \frac{100 \cdot |U \cup T|}{N}$$
$$\text{Projected Healthy Capacity} = N - |U \cup T|$$

**Authorization Requirement:**
An action $T = \{w\}$ targeting worker $w$ is authorized only if:
1. $\text{Projected Healthy Capacity} \ge H_{\min}$ ($N - |U \cup T| \ge 4$)
2. $\text{Projected Unavailable Percentage} \le P_{\max}$ ($\frac{100 \cdot |U \cup T|}{N} \le 20\%$)
3. $w \in U$ (The targeted worker is a confirmed unhealthy member of the service, not an arbitrary or healthy worker).

### Invariant 4: Identity & Authority Isolation
Let $\mathcal{P}_{\text{agent}}$ be the set of permissions held by the Bedrock Agent runtime, and $\mathcal{P}_{\text{broker}}$ be the set of permissions held by the Lambda Remediation Broker:
$$\mathcal{P}_{\text{agent}} \cap \text{MutatingActions}(\text{AWS}) = \emptyset$$
$$\mathcal{P}_{\text{broker}} \subseteq \{ \text{ecs:StopTask}(\text{ARN} \in \text{SandboxTasks}) \}$$
The foundation model runtime holds zero direct infrastructure mutation permissions.

---

## 2. Conservative Nature & Scope of the Capacity Model

The capacity model is intentionally conservative:
- It assumes any worker in $T$ transitions immediately from healthy to fully stopped upon authorization, even before the ECS API completes.
- It treats partially degraded workers ($U$) as completely unavailable.
- It does not credit the service with un-bootstrapped replacement tasks until they pass container health checks.

### What the Model Does NOT Capture:
1. **In-Flight Cascades:** It cannot predict whether a currently healthy worker will crash 200ms after the authorization decision due to external load.
2. **Infrastructure-Level Outages:** It does not model AWS Fargate availability zone outages or host hardware failures.
3. **External Traffic Surges:** It evaluates container quorum, not upstream request volume.

---

## 3. Explicit Operational Assumptions

We explicitly document the engineering assumptions and distributed system boundaries:

| Dimension | System Assumption | Failure Mode & BlastGate Safeguard |
|---|---|---|
| **AWS Control-Plane Consistency** | ECS `DescribeTasks` API returns eventual consistency within a 2-second window. | Broker checks task status directly and fails closed (`DENY`) if inventory is ambiguous or task state is transitional (`PENDING`/`DEACTIVATING`). |
| **Independent Actors** | Human operators, Auto Scaling, or deployment pipelines may independently stop or start tasks. | Broker re-verifies service count $N$ and active task count immediately before executing `ecs:StopTask`. |
| **System Clocks & Drift** | Lambda execution environments may experience NTP drift ($\pm 50\text{ms}$). | DynamoDB TTL timestamps and conditional write expressions use epoch seconds with generous buffer margins. |
| **DynamoDB Atomicity** | DynamoDB conditional writes provide single-partition linearizability. | The cooldown lock is implemented as a conditional `attribute_not_exists(pk) OR expires_at < :now` update. |
| **ECS Task-State Transitions** | Target task may terminate before broker issues `ecs:StopTask`. | Handled as idempotent success or recorded as `VERIFIED` without secondary action. |
| **Application-Health Telemetry** | CloudWatch metrics and heartbeat timestamps are updated at $\le 60\text{s}$ cadence. | Telemetry older than 120 seconds is rejected as stale (`ERR_STALE_TELEMETRY`). |
| **Failures Between Decision & Execution** | Network timeout or IAM failure between reservation and ECS execution. | The cooldown lock is reserved atomically *before* mutation; failed executions do not clear the cooldown (fail closed). |

---

## 4. No Claims of Absolute Safety

BlastGate does NOT claim to provide "mathematically unbreakable" or "100% universally safe" cloud infrastructure. Real-world AWS infrastructure is subject to network partitions, AWS API throttling, hardware degradation, and external operator actions. 

BlastGate's verifiable guarantee is strictly bounded:
> *Within its controlled execution boundary, no infrastructure mutation can occur without passing deterministic catalog validation, live capacity quorum verification, and atomic cooldown reservation.*
