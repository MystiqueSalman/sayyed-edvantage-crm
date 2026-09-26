
"""
Sayyed EdVantage AI Agent — AI Core 16
CRM-Aware Agent Orchestration & Action Authorization

Read-only orchestration layer:
- combines conversation/intelligence state with CRM facts
- evaluates authorization-aware action eligibility
- distinguishes recommended actions from authorized actions
- fails closed for missing/expired/revoked/denied authorization
- never sends messages, performs external actions, or writes CRM data
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

STATUS_READY = "CRM_AWARE_READY"
STATUS_CLARIFICATION = "CRM_AWARE_CLARIFICATION"
STATUS_HANDOFF = "CRM_AWARE_HANDOFF"
STATUS_BLOCKED = "CRM_AWARE_BLOCKED"
STATUS_UNKNOWN = "CRM_AWARE_UNKNOWN"

AUTH_UNKNOWN = "UNKNOWN"
AUTH_REQUESTED = "REQUESTED"
AUTH_GRANTED = "GRANTED"
AUTH_DENIED = "DENIED"
AUTH_REVOKED = "REVOKED"
AUTH_EXPIRED = "EXPIRED"

ACTION_RECOMMENDED = "ACTION_RECOMMENDED"
ACTION_AUTHORIZED = "ACTION_AUTHORIZED"
ACTION_BLOCKED = "ACTION_BLOCKED"
ACTION_HUMAN_REVIEW = "ACTION_HUMAN_REVIEW"
ACTION_NOT_APPLICABLE = "ACTION_NOT_APPLICABLE"

SAFE_ACTIONS = {
    "NO_ACTION",
    "PREPARE_RESPONSE",
    "PREPARE_FOLLOWUP",
    "REQUEST_HUMAN_REVIEW",
    "REQUEST_AUTHORIZATION",
}

EXECUTION_ACTIONS = {
    "SEND_MESSAGE",
    "UPDATE_CRM",
    "CREATE_APPLICATION",
    "RECORD_PAYMENT",
    "ENROLL_STUDENT",
    "EXTERNAL_ACTION",
}


@dataclass
class AuthorizationSnapshot:
    state: str = AUTH_UNKNOWN
    authorization_granted: bool = False
    execution_authorized: bool = False
    send_status: str = "NOT_SENT"
    expires_at: Optional[str] = None
    source: str = "authorization_state"
    evidence: List[str] = field(default_factory=list)


@dataclass
class CRMActionDecision:
    action: str
    status: str
    reason: str
    recommended: bool = False
    authorized: bool = False
    executable: bool = False
    requires_human_review: bool = False
    authorization_state: str = AUTH_UNKNOWN
    crm_write_allowed: bool = False
    message_send_allowed: bool = False
    evidence: List[str] = field(default_factory=list)


@dataclass
class CRMAwareAgentContext:
    lead_id: Optional[str]
    crm_snapshot: Dict[str, Any]
    conversation_context: Dict[str, Any]
    intelligence: Dict[str, Any]
    authorization: AuthorizationSnapshot
    active_course_ids: List[str] = field(default_factory=list)
    active_intent: Optional[str] = None
    status: str = STATUS_READY
    errors: List[str] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)


@dataclass
class CRMAwareAgentResult:
    status: str
    context: CRMAwareAgentContext
    action_decisions: List[CRMActionDecision] = field(default_factory=list)
    recommended_next_step: str = "NO_ACTION"
    human_handoff_required: bool = False
    authorization_required: bool = False
    errors: List[str] = field(default_factory=list)
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })


def normalize_authorization(value: Any) -> AuthorizationSnapshot:
    if isinstance(value, AuthorizationSnapshot):
        return deepcopy(value)
    if not isinstance(value, dict):
        return AuthorizationSnapshot()
    state = str(value.get("state", AUTH_UNKNOWN)).upper()
    granted = bool(value.get("authorization_granted", False))
    execution = bool(value.get("execution_authorized", False))
    send_status = str(value.get("send_status", "NOT_SENT"))
    # Fail closed for terminal negative states regardless of inconsistent flags.
    if state in {AUTH_REVOKED, AUTH_EXPIRED, AUTH_DENIED}:
        granted = False
        execution = False
        send_status = "NOT_SENT"
    return AuthorizationSnapshot(
        state=state,
        authorization_granted=granted,
        execution_authorized=execution,
        send_status=send_status,
        expires_at=value.get("expires_at"),
        source=str(value.get("source", "authorization_state")),
        evidence=list(value.get("evidence", [])),
    )


def build_crm_aware_context(
    lead_id: Optional[str] = None,
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    intelligence: Optional[Dict[str, Any]] = None,
    authorization: Any = None,
) -> CRMAwareAgentContext:
    crm = deepcopy(crm_snapshot or {})
    conv = deepcopy(conversation_context or {})
    intel = deepcopy(intelligence or {})
    auth = normalize_authorization(authorization)

    course_ids = list(
        conv.get("active_course_ids")
        or intel.get("course_ids")
        or crm.get("course_ids")
        or ([crm.get("course_id")] if crm.get("course_id") else [])
    )
    intent = conv.get("active_intent") or intel.get("intent")
    provenance = []
    if crm:
        provenance.append("CRM_READ")
    if conv:
        provenance.append("CONVERSATION_CONTEXT")
    if intel:
        provenance.append("AI_INTELLIGENCE")
    provenance.append(auth.source)

    return CRMAwareAgentContext(
        lead_id=lead_id or crm.get("lead_id"),
        crm_snapshot=crm,
        conversation_context=conv,
        intelligence=intel,
        authorization=auth,
        active_course_ids=course_ids,
        active_intent=intent,
        provenance=provenance,
    )


def evaluate_action(
    action: str,
    context: CRMAwareAgentContext,
    recommended: bool = True,
) -> CRMActionDecision:
    action = str(action).upper()
    auth = context.authorization
    evidence = list(auth.evidence)

    if action in {"NO_ACTION", "PREPARE_RESPONSE", "PREPARE_FOLLOWUP"}:
        return CRMActionDecision(
            action=action,
            status=ACTION_RECOMMENDED if recommended else ACTION_NOT_APPLICABLE,
            reason="Planning/preparation only; no execution is enabled in this layer.",
            recommended=recommended,
            authorized=False,
            executable=False,
            authorization_state=auth.state,
            evidence=evidence,
        )

    if action == "REQUEST_AUTHORIZATION":
        return CRMActionDecision(
            action=action,
            status=ACTION_RECOMMENDED,
            reason="Authorization may be requested separately; this layer does not grant authorization.",
            recommended=True,
            authorized=False,
            executable=False,
            authorization_state=auth.state,
            evidence=evidence,
        )

    if action == "REQUEST_HUMAN_REVIEW":
        return CRMActionDecision(
            action=action,
            status=ACTION_HUMAN_REVIEW,
            reason="Human review is required; no action is executed.",
            recommended=True,
            authorized=False,
            executable=False,
            requires_human_review=True,
            authorization_state=auth.state,
            evidence=evidence,
        )

    if action in EXECUTION_ACTIONS:
        if auth.state in {AUTH_REVOKED, AUTH_EXPIRED, AUTH_DENIED}:
            return CRMActionDecision(
                action=action, status=ACTION_BLOCKED,
                reason=f"Action blocked because authorization state is {auth.state}.",
                recommended=recommended, authorized=False, executable=False,
                authorization_state=auth.state, evidence=evidence,
            )
        if not auth.authorization_granted or not auth.execution_authorized:
            return CRMActionDecision(
                action=action, status=ACTION_BLOCKED,
                reason="Action blocked because explicit execution authorization is absent.",
                recommended=recommended, authorized=False, executable=False,
                authorization_state=auth.state, evidence=evidence,
            )
        # Even with upstream authorization, Core 16 remains an orchestration gate.
        return CRMActionDecision(
            action=action, status=ACTION_BLOCKED,
            reason="Execution remains disabled in the read-only agent layer; authorization does not itself execute an action.",
            recommended=recommended, authorized=True, executable=False,
            authorization_state=auth.state, evidence=evidence,
        )

    return CRMActionDecision(
        action=action,
        status=ACTION_BLOCKED,
        reason="Unknown action is blocked by fail-closed policy.",
        recommended=recommended,
        authorized=False,
        executable=False,
        authorization_state=auth.state,
        evidence=evidence,
    )


def orchestrate_crm_aware_agent(
    lead_id: Optional[str] = None,
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    intelligence: Optional[Dict[str, Any]] = None,
    authorization: Any = None,
    requested_action: Optional[str] = None,
) -> CRMAwareAgentResult:
    context = build_crm_aware_context(
        lead_id, crm_snapshot, conversation_context, intelligence, authorization
    )
    errors = []
    if not context.lead_id and context.crm_snapshot:
        errors.append("CRM snapshot is missing lead_id.")
    if requested_action:
        decision = evaluate_action(requested_action, context)
    else:
        decision = evaluate_action("PREPARE_RESPONSE", context)
    decisions = [decision]

    handoff = decision.requires_human_review
    auth_required = decision.status == ACTION_BLOCKED and decision.action in EXECUTION_ACTIONS
    status = STATUS_READY

    if handoff:
        status = STATUS_HANDOFF
    elif auth_required:
        status = STATUS_BLOCKED
    elif context.status != STATUS_READY:
        status = context.status

    context.status = status
    context.errors.extend(errors)

    return CRMAwareAgentResult(
        status=status,
        context=context,
        action_decisions=decisions,
        recommended_next_step=decision.action,
        human_handoff_required=handoff,
        authorization_required=auth_required,
        errors=errors,
    )


def validate_authorization_snapshot(auth: AuthorizationSnapshot) -> List[str]:
    errors = []
    if auth.state in {AUTH_REVOKED, AUTH_EXPIRED, AUTH_DENIED}:
        if auth.authorization_granted:
            errors.append("Terminal negative authorization state cannot be granted.")
        if auth.execution_authorized:
            errors.append("Terminal negative authorization state cannot authorize execution.")
        if auth.send_status != "NOT_SENT":
            errors.append("Terminal negative authorization state must remain NOT_SENT.")
    if auth.execution_authorized and not auth.authorization_granted:
        errors.append("Execution authorization cannot be true without authorization granted.")
    return errors


def validate_crm_aware_result(result: CRMAwareAgentResult) -> List[str]:
    errors = []
    errors.extend(validate_authorization_snapshot(result.context.authorization))
    if result.safety.get("execution_enabled") is not False:
        errors.append("execution_enabled must remain False.")
    if result.safety.get("messaging_enabled") is not False:
        errors.append("messaging_enabled must remain False.")
    if result.safety.get("external_actions_enabled") is not False:
        errors.append("external_actions_enabled must remain False.")
    if result.safety.get("crm_writes_enabled") is not False:
        errors.append("crm_writes_enabled must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    for d in result.action_decisions:
        if d.executable:
            errors.append("No Core 16 action may be executable.")
        if d.action in EXECUTION_ACTIONS and d.status != ACTION_BLOCKED:
            errors.append("Execution actions must remain blocked in Core 16.")
    return errors


def crm_aware_result_to_dict(result: CRMAwareAgentResult) -> Dict[str, Any]:
    return {
        "status": result.status,
        "context": {
            "lead_id": result.context.lead_id,
            "crm_snapshot": deepcopy(result.context.crm_snapshot),
            "conversation_context": deepcopy(result.context.conversation_context),
            "intelligence": deepcopy(result.context.intelligence),
            "authorization": {
                "state": result.context.authorization.state,
                "authorization_granted": result.context.authorization.authorization_granted,
                "execution_authorized": result.context.authorization.execution_authorized,
                "send_status": result.context.authorization.send_status,
                "expires_at": result.context.authorization.expires_at,
                "source": result.context.authorization.source,
                "evidence": list(result.context.authorization.evidence),
            },
            "active_course_ids": list(result.context.active_course_ids),
            "active_intent": result.context.active_intent,
            "status": result.context.status,
            "errors": list(result.context.errors),
            "provenance": list(result.context.provenance),
        },
        "action_decisions": [
            {
                "action": d.action,
                "status": d.status,
                "reason": d.reason,
                "recommended": d.recommended,
                "authorized": d.authorized,
                "executable": d.executable,
                "requires_human_review": d.requires_human_review,
                "authorization_state": d.authorization_state,
                "crm_write_allowed": d.crm_write_allowed,
                "message_send_allowed": d.message_send_allowed,
                "evidence": list(d.evidence),
            } for d in result.action_decisions
        ],
        "recommended_next_step": result.recommended_next_step,
        "human_handoff_required": result.human_handoff_required,
        "authorization_required": result.authorization_required,
        "errors": list(result.errors),
        "safety": dict(result.safety),
    }


def build_crm_aware_agent_layer() -> Dict[str, Any]:
    return {
        "layer": "AI_CORE_16",
        "name": "CRM-Aware Agent Orchestration & Action Authorization",
        "read_only": True,
        "authorization_aware": True,
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "fail_closed": True,
    }
