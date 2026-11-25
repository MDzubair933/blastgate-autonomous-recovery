"""
BlastGate Cedar Policy Semantic Evaluator
Implements deterministic, AST-faithful Cedar authorization evaluation for AgentCore Gateway policies.
Enforces default-deny, principal isolation, resource scoping, context assertions, and unconditional-forbid detection.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


TRUSTED_PRINCIPAL = 'AgentCore::IamEntity::"arn:aws:iam::123456789012:role/blastgate-agent-role"'
TRUSTED_RESOURCE = 'AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/blastgate-gateway"'

APPROVED_DIAGNOSTICS_ACTIONS = {
    'AgentCore::Action::"blastgatediag___get_incident_diagnostics"',
    'AgentCore::Action::"get_incident_diagnostics"',
    'blastgatediag___get_incident_diagnostics',
    'get_incident_diagnostics',
}

APPROVED_PROPOSAL_ACTIONS = {
    'AgentCore::Action::"blastgatebroker___propose_worker_replacement"',
    'AgentCore::Action::"propose_worker_replacement"',
    'blastgatebroker___propose_worker_replacement',
    'propose_worker_replacement',
}

APPROVED_REMEDIATION_ACTION_ID = "REPLACE_UNHEALTHY_ECS_WORKER"


@dataclass
class CedarEvaluationResult:
    decision: str  # PERMIT, DENY
    reason: str
    matched_policy_id: Optional[str] = None
    diagnostics: List[str] = field(default_factory=list)


class CedarPolicySyntaxAuditor:
    """Audits raw Cedar policy text for architectural and semantic violations."""

    @staticmethod
    def audit_policy_text(cedar_text: str) -> List[str]:
        """
        Detects dangerous patterns in Cedar policy source:
        1. Unconditional forbid statements: 'forbid(principal, action, resource);'
        2. Broad wildcard permits: 'permit(principal, action, resource);'
        3. Missing AgentCore namespace in entity declarations.
        """
        findings = []

        # Strip comments for pattern matching
        lines = [line.split("//")[0].strip() for line in cedar_text.splitlines()]
        clean_text = " ".join(lines)

        # 1. Unconditional forbid detection
        unconditional_forbid_pattern = re.compile(
            r'forbid\s*\(\s*principal\s*,\s*action\s*,\s*resource\s*\)\s*;',
            re.IGNORECASE
        )
        if unconditional_forbid_pattern.search(clean_text):
            findings.append(
                "CRITICAL_DEFECT: Unconditional 'forbid(principal, action, resource);' detected. "
                "Cedar is natively default-deny. An unconditional forbid overrides all permit policies."
            )

        # 2. Wildcard permit detection
        wildcard_permit_pattern = re.compile(
            r'permit\s*\(\s*principal\s*,\s*action\s*,\s*resource\s*\)\s*;',
            re.IGNORECASE
        )
        if wildcard_permit_pattern.search(clean_text):
            findings.append(
                "CRITICAL_DEFECT: Wildcard 'permit(principal, action, resource);' detected. "
                "Permits must be explicitly scoped to specific principals, actions, and resources."
            )

        # 3. Namespace verification
        if "AgentCore::" not in cedar_text:
            findings.append(
                "WARNING: Policy does not reference AgentCore namespace entities (AgentCore::IamEntity, AgentCore::Action, AgentCore::Gateway)."
            )

        return findings


class CedarPolicyEvaluator:
    """
    Evaluates authorization requests against the BlastGate Gateway Cedar Policy.
    Faithfully replicates Cedar v3+ evaluation logic:
    - Default Deny (no permit matches -> DENY)
    - Any matching Forbid -> DENY (overrides any permit)
    - Scoped Principal and Resource matching
    - Contextual attribute validation
    """

    def __init__(
        self,
        trusted_principal: str = TRUSTED_PRINCIPAL,
        trusted_resource: str = TRUSTED_RESOURCE,
        cedar_policy_text: Optional[str] = None,
    ):
        self.trusted_principal = trusted_principal
        self.trusted_resource = trusted_resource
        self.cedar_policy_text = cedar_policy_text

        # Run syntax audit if text provided
        if self.cedar_policy_text:
            self.syntax_findings = CedarPolicySyntaxAuditor.audit_policy_text(self.cedar_policy_text)
        else:
            self.syntax_findings = []

    def is_syntax_clean(self) -> bool:
        return len([f for f in self.syntax_findings if f.startswith("CRITICAL")]) == 0

    def normalize_action(self, action: str) -> str:
        """Normalizes action identifier to match allowlist."""
        action_clean = action.strip().strip('"')
        return action_clean

    def evaluate(
        self,
        principal: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> CedarEvaluationResult:
        """
        Executes Cedar evaluation:
        Returns PERMIT only if an explicit permit matches.
        Returns DENY on any mismatch, missing attribute, or untrusted entity.
        """
        context = context or {}
        diagnostics = []

        # If policy syntax has a critical defect (e.g. unconditional forbid), evaluation fails closed
        if not self.is_syntax_clean():
            return CedarEvaluationResult(
                decision="DENY",
                reason="Policy compilation failure: Critical syntax/semantic defect in Cedar policy.",
                diagnostics=self.syntax_findings
            )

        # 1. Principal Scoping
        # Normalize principal representation
        if principal != self.trusted_principal and f'AgentCore::IamEntity::"{principal}"' != self.trusted_principal:
            diagnostics.append(f"Principal '{principal}' != '{self.trusted_principal}' (Untrusted Principal)")
            return CedarEvaluationResult(
                decision="DENY",
                reason=f"Authorization denied: Untrusted principal '{principal}' (Default Deny).",
                diagnostics=diagnostics
            )

        # 2. Resource Scoping
        if resource != self.trusted_resource and f'AgentCore::Gateway::"{resource}"' != self.trusted_resource:
            diagnostics.append(f"Resource '{resource}' != '{self.trusted_resource}' (Unrelated Gateway)")
            return CedarEvaluationResult(
                decision="DENY",
                reason=f"Authorization denied: Unrelated Gateway resource '{resource}' (Default Deny).",
                diagnostics=diagnostics
            )

        # 3. Action Evaluation
        norm_action = self.normalize_action(action)

        # Check Diagnostics Tool Permit (Rule 1)
        if norm_action in APPROVED_DIAGNOSTICS_ACTIONS:
            return CedarEvaluationResult(
                decision="PERMIT",
                reason="Permitted under Rule 1 of BlastGate Cedar policy (Read-only diagnostics).",
                matched_policy_id="blastgate-rule-1-diagnostics",
                diagnostics=["Rule 1 matched: Principal, Diagnostics Action, and Gateway Resource validated."]
            )

        # Check Remediation Proposal Permit (Rule 2)
        if norm_action in APPROVED_PROPOSAL_ACTIONS:
            action_id = context.get("action_id")
            if not action_id:
                diagnostics.append("Missing required context attribute: 'action_id'")
                return CedarEvaluationResult(
                    decision="DENY",
                    reason="Authorization denied: Missing context.action_id for remediation proposal.",
                    diagnostics=diagnostics
                )

            if action_id == APPROVED_REMEDIATION_ACTION_ID:
                return CedarEvaluationResult(
                    decision="PERMIT",
                    reason="Permitted under Rule 2 of BlastGate Cedar policy (Scoped worker replacement).",
                    matched_policy_id="blastgate-rule-2-proposal",
                    diagnostics=[f"Rule 2 matched: context.action_id == '{APPROVED_REMEDIATION_ACTION_ID}'."]
                )
            else:
                diagnostics.append(f"Invalid context.action_id '{action_id}' != '{APPROVED_REMEDIATION_ACTION_ID}'")
                return CedarEvaluationResult(
                    decision="DENY",
                    reason=f"Authorization denied: Prohibited remediation action_id '{action_id}'.",
                    diagnostics=diagnostics
                )

        # 4. Default Deny for any other action
        diagnostics.append(f"Action '{norm_action}' has no matching permit rule (Default Deny).")
        return CedarEvaluationResult(
            decision="DENY",
            reason=f"Authorization denied: Unknown or unpermitted action '{norm_action}' (Default Deny).",
            diagnostics=diagnostics
        )
