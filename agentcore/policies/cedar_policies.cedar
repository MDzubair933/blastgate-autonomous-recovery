// ==============================================================================
// BlastGate AgentCore Gateway Cedar Authorization Policy
// Language: Cedar v3+
// Security Model: Native Default Deny, Explicit Scoped Permits Only
//
// CRITICAL SECURITY INVARIANT:
// 1. Cedar is default-deny by design. Any request that does not match an explicit
//    'permit' policy is DENIED.
// 2. An unconditional 'forbid(principal, action, resource);' statement MUST NOT
//    be present because in Cedar any matching forbid overrides all permits.
// 3. All entities strictly use the AgentCore namespace and valid ARN formats.
// ==============================================================================

// RULE 1: Explicit Scoped Permit for Read-Only Diagnostics Microservice
// Permitted ONLY for the trusted BlastGate Harness role, targeting the approved
// BlastGate Gateway, for the read-only diagnostics action.
permit (
    principal == AgentCore::IamEntity::"arn:aws:iam::123456789012:role/blastgate-agent-role",
    action in [
        AgentCore::Action::"blastgatediag___get_incident_diagnostics",
        AgentCore::Action::"get_incident_diagnostics"
    ],
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/blastgate-gateway"
);

// RULE 2: Explicit Scoped Permit for Sovereign Remediation Proposal Tool
// Permitted ONLY for the trusted BlastGate Harness role, targeting the approved
// BlastGate Gateway, when the remediation context strictly equals the single
// allowlisted catalog action "REPLACE_UNHEALTHY_ECS_WORKER".
permit (
    principal == AgentCore::IamEntity::"arn:aws:iam::123456789012:role/blastgate-agent-role",
    action in [
        AgentCore::Action::"blastgatebroker___propose_worker_replacement",
        AgentCore::Action::"propose_worker_replacement"
    ],
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/blastgate-gateway"
)
when {
    context.action_id == "REPLACE_UNHEALTHY_ECS_WORKER"
};
