/**
 * BlastGate Evidence Dashboard - Type Definitions
 * UI view models adapted from contracts/OPERATIONAL_RULES.md, action_catalog.json,
 * decision_receipt.schema.json, and audit_schema.json. These enriched demo models are not raw backend receipts.
 * 
 * STRICT COMPLIANCE NOTE:
 * All displayed records represent deterministic local contract fixtures and simulated
 * safety broker invariant evaluations. No live AWS Bedrock models, live ECS tasks, or
 * live DynamoDB tables were mutated during local verification.
 */

export type WorkerState = "HEALTHY" | "STALLED" | "RECOVERING" | "UNKNOWN";

export interface WorkerRecord {
  task_arn: string;
  short_id: string;
  cluster_name: string;
  service_name: string;
  task_family: string;
  state: WorkerState;
  is_unhealthy: boolean;
  heartbeat_age_sec: number;
  processed_count: number;
  cpu_reservation: number; // 256
  memory_limit_mb: number; // 512
  ip_address: string;
  uptime_sec: number;
  incident_id?: string;
  last_error?: string;
}

export type IncidentStatus = "OPEN" | "RESOLVED" | "UNKNOWN";
export type IncidentState = "ALARM" | "OK" | "INSUFFICIENT_DATA";

export interface IncidentRecord {
  incident_id: string;
  alarm_name: string;
  cluster_name: string;
  service_name: string;
  target_task_arn: string;
  target_short_id: string;
  state: IncidentState;
  status: IncidentStatus;
  created_at: string;
  updated_at: string;
  resolved_timestamp?: string;
  summary: string;
  untrusted_logs: {
    log_lines: string[];
    is_untrusted_data: boolean;
    boundary_note: string;
  };
  approved_action: string; // REPLACE_UNHEALTHY_ECS_WORKER
  runbook_id: string; // RB-ECS-001
}

export type DecisionType = "ALLOW" | "DENY" | "ERROR" | "UNKNOWN";
export type ExecutionStatus = "SIMULATED_EXECUTION" | "SIMULATED_REFUSAL" | "UNATTEMPTED";

export interface RuleEvaluationResult {
  rule_id: string;
  name: string;
  evaluated: boolean;
  passed: boolean;
  message: string;
}

export interface DecisionReceipt {
  decision_id: string;
  incident_id: string;
  action_id: string;
  target_task_arn: string;
  target_short_id: string;
  catalog_version: string;
  policy_version: string;
  decision: DecisionType;
  reason_code: string;
  execution_status: ExecutionStatus;
  aws_request_id: string;
  recorded_at: string;
  rule_results: Record<string, RuleEvaluationResult>;
  recovery_verified: boolean;
  timeline_steps: {
    step_number: number;
    name: string;
    description: string;
    status: "COMPLETE" | "DENIED" | "FAILED" | "PENDING";
    timestamp: string;
    details: string;
  }[];
}

export interface SecurityRule {
  rule_id: string;
  name: string;
  security_objective: string;
  plain_meaning: string;
  enforcement_layer: string;
  allowed_behavior: string;
  forbidden_behavior: string;
  independent_mechanism: string;
  expected_refusal_code: string;
  test_ids: string[];
  status: "ENFORCED" | "ACTIVE";
  current_result: "PASS" | "DENIED";
  evidence_summary: string;
}

export type ModelBehaviorVerdict = "NOT TESTED";

export type SyntheticFixtureBehavior =
  | "SYNTHETIC: PROMPT INJECTION BYPASS"
  | "SYNTHETIC: INDIRECT LOG POISONING"
  | "SYNTHETIC: FORGED CISO OVERRIDE"
  | "SYNTHETIC: IAM ESCALATION PROPOSAL"
  | "SYNTHETIC: CONCURRENT STORM PROPOSAL"
  | "SYNTHETIC: READ-ONLY AUDIT PROBE";

export type InfrastructureVerdict =
  | "SIMULATED BROKER: BLOCKED"
  | "SIMULATED BROKER: SANITIZED & BLOCKED"
  | "SIMULATED BROKER: SERIALIZED & BLOCKED"
  | "NOT TESTED";

export interface AdversarialScenario {
  scenario_id: string;
  name: string;
  attack_vector: string;
  description: string;
  injection_payload: string;
  model_verdict: ModelBehaviorVerdict; // Always NOT TESTED (no live Bedrock invoked)
  model_verdict_explanation: string;
  synthetic_fixture_behavior: SyntheticFixtureBehavior; // Synthetic test harness injection role
  synthetic_fixture_explanation: string;
  infrastructure_verdict: InfrastructureVerdict; // Simulated broker invariant result
  infrastructure_explanation: string;
  enforced_rules: string[];
  test_reference: string;
  live_status: "SIMULATED LOCAL CONTRACT" | "NOT TESTED IN CLOUD";
}

export interface AuditEvent {
  event_id: string;
  event_type: "AUTHORIZATION_DECISION" | "MUTATION_EXECUTION" | "SYSTEM_REFUSAL" | "COOLDOWN_RESERVATION";
  incident_id: string;
  decision_id: string;
  actor_type: "AGENT_GATEWAY" | "LAMBDA_BROKER" | "SYSTEM_WATCHDOG";
  requested_action: string;
  authorization_decision: DecisionType;
  execution_status: ExecutionStatus;
  timestamp: string;
  sha256_hash: string;
  parent_hash: string;
  canonical_string: string;
  details: Record<string, any>;
}

export interface FleetCapacity {
  cluster_name: string;
  service_name: string;
  desired_count: number; // 6
  running_count: number;
  healthy_count: number;
  stalled_count: number;
  recovering_count: number;
  unknown_count: number;
  min_healthy_threshold: number; // 4
  max_unavailable_percent: number; // 20.0
  quorum_satisfied: boolean;
  remediation_allowed_by_capacity: boolean;
}

export interface DeploymentCostStatus {
  region: string;
  recorded_at: string;
  cleanup: {desired: number; running: number; pending: number};
  backend_tests_reported: number;
  lambda_packages: number;
}

export type TabId =
  | "overview"
  | "workers"
  | "incidents"
  | "decision-console"
  | "security-rules"
  | "adversarial"
  | "audit-explorer"
  | "deployment-cost";

