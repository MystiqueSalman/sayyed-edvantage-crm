
"""
Sayyed EdVantage AI Agent — AI Core 18
CRM-Aware Conversation Decision & Response Planning Intelligence

Read-only decision layer:
- consumes CRM/conversation synchronization state
- combines current lead stage, intent and AI intelligence
- selects a safe conversational next step
- separates response preparation from CRM/action execution
- conflicts and uncertain state never get silently resolved
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

DECISION_CONTINUE = "DECISION_CONTINUE"
DECISION_CLARIFY = "DECISION_CLARIFY"
DECISION_HUMAN_REVIEW = "DECISION_HUMAN_REVIEW"
DECISION_OBTAIN_CRM = "DECISION_OBTAIN_CRM"
DECISION_UNKNOWN = "DECISION_UNKNOWN"

NEXT_RESPONSE = "PREPARE_RESPONSE"
NEXT_CLARIFICATION = "ASK_CLARIFICATION"
NEXT_REVIEW = "REQUEST_HUMAN_REVIEW"
NEXT_CRM_STATE = "OBTAIN_CRM_STATE"
NEXT_NO_ACTION = "NO_ACTION"

@dataclass
class ConversationDecision:
    decision: str
    next_step: str
    rationale: str
    response_allowed: bool = True
    crm_write_required: bool = False
    crm_write_allowed: bool = False
    message_send_allowed: bool = False
    human_handoff_required: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

@dataclass
class CRMConversationDecisionResult:
    lead_id: Optional[str]
    decision: ConversationDecision
    sync_status: str
    lead_stage: Optional[str] = None
    active_course_ids: List[str] = field(default_factory=list)
    active_intent: Optional[str] = None
    provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _sync_value(sync: Any, name: str, default: Any = None) -> Any:
    if sync is None:
        return default
    if isinstance(sync, dict):
        return sync.get(name, default)
    return getattr(sync, name, default)

def _crm_value(crm: Dict[str, Any], name: str) -> Any:
    return deepcopy(crm.get(name))

def _course_ids(crm: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    vals = context.get("active_course_ids")
    if isinstance(vals, list) and vals:
        return list(vals)
    if crm.get("course_id"):
        return [crm["course_id"]]
    vals = crm.get("course_ids")
    return list(vals) if isinstance(vals, list) else []

def build_conversation_decision(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    sync_result: Any = None,
    intelligence: Optional[Dict[str, Any]] = None,
) -> CRMConversationDecisionResult:
    crm = deepcopy(crm_snapshot or {})
    ctx = deepcopy(conversation_context or {})
    intel = deepcopy(intelligence or {})

    sync_status = _sync_value(sync_result, "status", "SYNC_UNKNOWN")
    lead_id = crm.get("lead_id") or ctx.get("lead_id")
    stage = crm.get("stage")
    courses = _course_ids(crm, ctx)
    intent = ctx.get("active_intent") or intel.get("intent") or crm.get("intent")

    provenance = []
    if crm:
        provenance.append("CRM_READ")
    if ctx:
        provenance.append("CONVERSATION_CONTEXT")
    if intel:
        provenance.append("AI_INTELLIGENCE")
    if sync_result is not None:
        provenance.append("STATE_SYNCHRONIZATION")

    if sync_status == "SYNC_REVIEW":
        questions = list(_sync_value(sync_result, "clarification_questions", []))
        decision = ConversationDecision(
            DECISION_HUMAN_REVIEW, NEXT_REVIEW,
            "CRM and conversation state contain a material conflict; do not silently choose a state.",
            response_allowed=False, crm_write_required=True, crm_write_allowed=False,
            message_send_allowed=False, human_handoff_required=True,
            clarification_questions=questions,
            evidence=["STATE_CONFLICT"],
        )
    elif sync_status == "SYNC_INSUFFICIENT":
        decision = ConversationDecision(
            DECISION_OBTAIN_CRM, NEXT_CRM_STATE,
            "CRM state is unavailable; obtain authoritative lead state before CRM-aware decisions.",
            response_allowed=False, crm_write_required=False, crm_write_allowed=False,
            message_send_allowed=False, human_handoff_required=False,
            evidence=["CRM_STATE_UNAVAILABLE"],
        )
    elif sync_status == "SYNC_UNKNOWN":
        decision = ConversationDecision(
            DECISION_UNKNOWN, NEXT_NO_ACTION,
            "Lead state is insufficiently known; do not invent missing CRM or conversation facts.",
            response_allowed=False, crm_write_required=False, crm_write_allowed=False,
            message_send_allowed=False, human_handoff_required=False,
            evidence=["LEAD_STATE_UNKNOWN"],
        )
    elif sync_status == "SYNC_CLARIFICATION":
        decision = ConversationDecision(
            DECISION_CLARIFY, NEXT_CLARIFICATION,
            "CRM contains lead state not established in the conversation; clarify only when needed.",
            response_allowed=True, crm_write_required=False, crm_write_allowed=False,
            message_send_allowed=False, human_handoff_required=False,
            evidence=["STATE_PARTIALLY_ALIGNED"],
        )
    else:
        # Synchronized state: prepare a response, never execute an action.
        evidence = ["STATE_ALIGNED"]
        if stage:
            evidence.append(f"CRM_STAGE:{stage}")
        if courses:
            evidence.append("COURSE_STATE_AVAILABLE")
        if intent:
            evidence.append(f"INTENT:{intent}")
        decision = ConversationDecision(
            DECISION_CONTINUE, NEXT_RESPONSE,
            "CRM and conversation state are sufficiently aligned for a grounded conversational response.",
            response_allowed=True, crm_write_required=False, crm_write_allowed=False,
            message_send_allowed=False, human_handoff_required=False,
            evidence=evidence,
        )

    return CRMConversationDecisionResult(
        lead_id=lead_id,
        decision=decision,
        sync_status=sync_status,
        lead_stage=stage,
        active_course_ids=courses,
        active_intent=intent,
        provenance=provenance,
    )

def run_crm_conversation_decision(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    sync_result: Any = None,
    intelligence: Optional[Dict[str, Any]] = None,
) -> CRMConversationDecisionResult:
    return build_conversation_decision(
        crm_snapshot, conversation_context, sync_result, intelligence
    )

def validate_conversation_decision(result: CRMConversationDecisionResult) -> List[str]:
    errors = []
    d = result.decision
    if d.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if d.message_send_allowed is not False:
        errors.append("Message sending must remain disabled.")
    if d.decision == DECISION_HUMAN_REVIEW and not d.human_handoff_required:
        errors.append("Human-review decision must require human handoff.")
    if d.decision == DECISION_HUMAN_REVIEW and d.response_allowed:
        errors.append("Material state conflict must not authorize response composition as normal flow.")
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
    return errors

def decision_to_dict(result: CRMConversationDecisionResult) -> Dict[str, Any]:
    d = result.decision
    return {
        "lead_id": result.lead_id,
        "decision": {
            "decision": d.decision,
            "next_step": d.next_step,
            "rationale": d.rationale,
            "response_allowed": d.response_allowed,
            "crm_write_required": d.crm_write_required,
            "crm_write_allowed": d.crm_write_allowed,
            "message_send_allowed": d.message_send_allowed,
            "human_handoff_required": d.human_handoff_required,
            "clarification_questions": list(d.clarification_questions),
            "evidence": list(d.evidence),
        },
        "sync_status": result.sync_status,
        "lead_stage": result.lead_stage,
        "active_course_ids": list(result.active_course_ids),
        "active_intent": result.active_intent,
        "provenance": list(result.provenance),
        "errors": list(result.errors),
        "safety": dict(result.safety),
    }

def build_crm_conversation_decision_layer() -> Dict[str, Any]:
    return {
        "layer": "AI_CORE_18",
        "name": "CRM-Aware Conversation Decision & Response Planning Intelligence",
        "read_only": True,
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "execution_enabled": False,
        "fail_closed": True,
    }
