
"""
Sayyed EdVantage AI Agent — AI Core 19
Lead-Aware Grounded Response Context Intelligence

Read-only response-context layer:
- synthesizes verified CRM facts, conversation context, AI intelligence,
  synchronization state, and conversation decision state
- creates a lead-specific response context without inventing facts
- keeps CRM facts distinguishable from conversational facts
- blocks normal response context when material state conflicts exist
- never sends messages, writes CRM, or performs external actions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

RESPONSE_CONTEXT_READY = "RESPONSE_CONTEXT_READY"
RESPONSE_CONTEXT_CLARIFICATION = "RESPONSE_CONTEXT_CLARIFICATION"
RESPONSE_CONTEXT_REVIEW = "RESPONSE_CONTEXT_REVIEW"
RESPONSE_CONTEXT_INSUFFICIENT = "RESPONSE_CONTEXT_INSUFFICIENT"
RESPONSE_CONTEXT_UNKNOWN = "RESPONSE_CONTEXT_UNKNOWN"

SOURCE_CRM = "CRM_READ"
SOURCE_CONVERSATION = "CONVERSATION_CONTEXT"
SOURCE_INTELLIGENCE = "AI_INTELLIGENCE"
SOURCE_SYNC = "STATE_SYNCHRONIZATION"
SOURCE_DECISION = "CONVERSATION_DECISION"

@dataclass
class ResponseFact:
    field: str
    value: Any
    source: str
    confidence: str = "verified_source"
    usable: bool = True
    note: str = ""

@dataclass
class LeadAwareResponseContext:
    lead_id: Optional[str]
    status: str
    facts: List[ResponseFact] = field(default_factory=list)
    course_ids: List[str] = field(default_factory=list)
    intent: Optional[str] = None
    lead_stage: Optional[str] = None
    response_allowed: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    provenance: List[str] = field(default_factory=list)
    excluded_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class ResponseContextResult:
    context: LeadAwareResponseContext
    recommended_response_mode: str = "NO_RESPONSE_CONTEXT"
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _add_fact(facts, field, value, source, confidence="verified_source", note=""):
    if value is not None:
        facts.append(ResponseFact(
            field=field, value=deepcopy(value), source=source,
            confidence=confidence, usable=True, note=note
        ))

def build_lead_aware_response_context(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    intelligence: Optional[Dict[str, Any]] = None,
    sync_result: Any = None,
    decision_result: Any = None,
) -> ResponseContextResult:
    crm = deepcopy(crm_snapshot or {})
    conv = deepcopy(conversation_context or {})
    intel = deepcopy(intelligence or {})

    sync_status = _get(sync_result, "status", "SYNC_UNKNOWN")
    decision = _get(decision_result, "decision")
    decision_code = _get(decision, "decision") if decision is not None else None
    response_allowed_by_decision = _get(decision, "response_allowed", None)

    lead_id = crm.get("lead_id") or conv.get("lead_id")
    course_ids = []
    ctx_courses = conv.get("active_course_ids")
    if isinstance(ctx_courses, list):
        course_ids = list(ctx_courses)
    elif crm.get("course_id"):
        course_ids = [crm["course_id"]]
    elif isinstance(crm.get("course_ids"), list):
        course_ids = list(crm["course_ids"])

    intent = conv.get("active_intent") or intel.get("intent") or crm.get("intent")
    stage = crm.get("stage")

    provenance = []
    if crm: provenance.append(SOURCE_CRM)
    if conv: provenance.append(SOURCE_CONVERSATION)
    if intel: provenance.append(SOURCE_INTELLIGENCE)
    if sync_result is not None: provenance.append(SOURCE_SYNC)
    if decision_result is not None: provenance.append(SOURCE_DECISION)

    facts = []
    _add_fact(facts, "lead_id", lead_id, SOURCE_CRM if crm.get("lead_id") else SOURCE_CONVERSATION)
    _add_fact(facts, "course_ids", course_ids, SOURCE_CONVERSATION if ctx_courses else SOURCE_CRM)
    _add_fact(facts, "intent", intent,
              SOURCE_CONVERSATION if conv.get("active_intent") else
              SOURCE_INTELLIGENCE if intel.get("intent") else SOURCE_CRM)
    _add_fact(facts, "lead_stage", stage, SOURCE_CRM)

    # Preserve useful CRM lead state without exposing arbitrary/unverified
    # fields from the CRM snapshot as facts.
    for field in ("region", "counselling", "follow_up", "pending_items"):
        if field in crm:
            _add_fact(facts, field, crm[field], SOURCE_CRM)

    clarification_questions = list(_get(sync_result, "clarification_questions", []))
    human_handoff = bool(_get(sync_result, "human_handoff_required", False))

    if sync_status == "SYNC_REVIEW":
        status = RESPONSE_CONTEXT_REVIEW
        response_allowed = False
        mode = "HUMAN_REVIEW"
        human_handoff = True
    elif sync_status == "SYNC_INSUFFICIENT":
        status = RESPONSE_CONTEXT_INSUFFICIENT
        response_allowed = False
        mode = "OBTAIN_CRM_STATE"
    elif sync_status == "SYNC_UNKNOWN":
        status = RESPONSE_CONTEXT_UNKNOWN
        response_allowed = False
        mode = "NO_RESPONSE_CONTEXT"
    elif sync_status == "SYNC_CLARIFICATION":
        status = RESPONSE_CONTEXT_CLARIFICATION
        response_allowed = False
        mode = "ASK_CLARIFICATION"
    else:
        status = RESPONSE_CONTEXT_READY
        response_allowed = True
        mode = "GROUNDED_RESPONSE"

    # A downstream decision can further restrict response use.
    if response_allowed_by_decision is False:
        response_allowed = False
        if decision_code == "DECISION_HUMAN_REVIEW":
            status = RESPONSE_CONTEXT_REVIEW
            mode = "HUMAN_REVIEW"
            human_handoff = True
        elif decision_code == "DECISION_CLARIFY":
            status = RESPONSE_CONTEXT_CLARIFICATION
            mode = "ASK_CLARIFICATION"
        elif decision_code == "DECISION_OBTAIN_CRM":
            status = RESPONSE_CONTEXT_INSUFFICIENT
            mode = "OBTAIN_CRM_STATE"
        elif decision_code == "DECISION_UNKNOWN":
            status = RESPONSE_CONTEXT_UNKNOWN
            mode = "NO_RESPONSE_CONTEXT"

    # If there is no lead identity and no meaningful source state, fail closed.
    if not lead_id and not facts:
        status = RESPONSE_CONTEXT_UNKNOWN
        response_allowed = False
        mode = "NO_RESPONSE_CONTEXT"

    return ResponseContextResult(
        context=LeadAwareResponseContext(
            lead_id=lead_id,
            status=status,
            facts=facts,
            course_ids=course_ids,
            intent=intent,
            lead_stage=stage,
            response_allowed=response_allowed,
            clarification_questions=clarification_questions,
            human_handoff_required=human_handoff,
            provenance=provenance,
            excluded_fields=[],
            errors=[],
        ),
        recommended_response_mode=mode,
    )

def run_lead_aware_response_context(
    crm_snapshot=None,
    conversation_context=None,
    intelligence=None,
    sync_result=None,
    decision_result=None,
):
    return build_lead_aware_response_context(
        crm_snapshot, conversation_context, intelligence,
        sync_result, decision_result
    )

def validate_response_context(result: ResponseContextResult) -> List[str]:
    errors = []
    c = result.context
    if c.response_allowed and c.status != RESPONSE_CONTEXT_READY:
        errors.append("Response may only be allowed in RESPONSE_CONTEXT_READY.")
    if c.status == RESPONSE_CONTEXT_REVIEW and not c.human_handoff_required:
        errors.append("Review context requires human handoff.")
    if c.status in {RESPONSE_CONTEXT_CLARIFICATION, RESPONSE_CONTEXT_INSUFFICIENT, RESPONSE_CONTEXT_UNKNOWN} and c.response_allowed:
        errors.append("Incomplete/unknown context cannot allow normal response.")
    for f in c.facts:
        if not f.usable:
            errors.append("All included response facts must be explicitly marked usable.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled"):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def response_context_to_dict(result: ResponseContextResult) -> Dict[str, Any]:
    c = result.context
    return {
        "context": {
            "lead_id": c.lead_id,
            "status": c.status,
            "facts": [
                {"field": f.field, "value": deepcopy(f.value), "source": f.source,
                 "confidence": f.confidence, "usable": f.usable, "note": f.note}
                for f in c.facts
            ],
            "course_ids": list(c.course_ids),
            "intent": c.intent,
            "lead_stage": c.lead_stage,
            "response_allowed": c.response_allowed,
            "clarification_questions": list(c.clarification_questions),
            "human_handoff_required": c.human_handoff_required,
            "provenance": list(c.provenance),
            "excluded_fields": list(c.excluded_fields),
            "errors": list(c.errors),
        },
        "recommended_response_mode": result.recommended_response_mode,
        "safety": dict(result.safety),
    }

def build_lead_aware_response_layer():
    return {
        "layer": "AI_CORE_19",
        "name": "Lead-Aware Grounded Response Context Intelligence",
        "read_only": True,
        "response_context_only": True,
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "execution_enabled": False,
        "fail_closed": True,
    }
