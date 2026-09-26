
"""
Sayyed EdVantage AI Agent — AI Core 20
CRM-Aware Grounded Response Orchestration

Read-only final conversational planning layer:
- combines lead-aware response context with prior intelligence outputs
- selects a safe response mode and evidence set
- keeps CRM facts, course knowledge, and conversation facts attributable
- preserves commercial/career/certification safety
- blocks response generation when state is conflicting or unknown
- never sends messages, writes CRM, or performs external actions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

RESPONSE_READY = "RESPONSE_READY"
RESPONSE_CLARIFICATION = "RESPONSE_CLARIFICATION"
RESPONSE_HUMAN_REVIEW = "RESPONSE_HUMAN_REVIEW"
RESPONSE_OBTAIN_STATE = "RESPONSE_OBTAIN_STATE"
RESPONSE_UNKNOWN = "RESPONSE_UNKNOWN"

MODE_GROUNDED = "GROUNDED_RESPONSE"
MODE_CLARIFY = "CLARIFICATION_RESPONSE"
MODE_HUMAN = "HUMAN_REVIEW"
MODE_OBTAIN_STATE = "OBTAIN_CRM_STATE"
MODE_NONE = "NO_RESPONSE"

@dataclass
class ResponseEvidence:
    field: str
    value: Any
    source: str
    course_id: Optional[str] = None
    safe_to_use: bool = True
    note: str = ""

@dataclass
class GroundedResponsePlan:
    status: str
    mode: str
    lead_id: Optional[str]
    course_ids: List[str]
    intent: Optional[str]
    lead_stage: Optional[str]
    response_goal: str
    evidence: List[ResponseEvidence] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    message_send_allowed: bool = False
    crm_write_allowed: bool = False
    errors: List[str] = field(default_factory=list)

@dataclass
class GroundedResponseResult:
    plan: GroundedResponsePlan
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

def _decision_obj(decision_result: Any):
    return _get(decision_result, "decision")

def _collect_facts(response_context: Any) -> List[ResponseEvidence]:
    facts = _get(response_context, "facts", []) or []
    out = []
    for f in facts:
        value = _get(f, "value")
        if value is None:
            continue
        out.append(ResponseEvidence(
            field=_get(f, "field", "unknown"),
            value=deepcopy(value),
            source=_get(f, "source", "UNKNOWN"),
            course_id=_get(f, "course_id"),
            safe_to_use=bool(_get(f, "usable", True)),
            note=_get(f, "note", ""),
        ))
    return out

def _default_prohibited_claims(intent: Optional[str]) -> List[str]:
    claims = [
        "Do not invent missing course, fee, eligibility, certification, or admissions facts.",
        "Do not promise admission, enrollment, employment, placement, salary, or income outcomes.",
        "Do not claim that an application, payment, enrollment, or CRM update has occurred unless independently verified.",
    ]
    if intent == "commercial":
        claims.append("For international students, do not substitute Indian pricing when international pricing is undefined.")
    return claims

def build_grounded_response_plan(
    response_context: Any = None,
    decision_result: Any = None,
    course_answer: Any = None,
    commercial_plan: Any = None,
    counselling_plan: Any = None,
    objection_plan: Any = None,
    enrollment_readiness: Any = None,
) -> GroundedResponseResult:
    ctx = response_context
    decision = _decision_obj(decision_result)

    status = _get(ctx, "status", "RESPONSE_CONTEXT_UNKNOWN")
    lead_id = _get(ctx, "lead_id")
    course_ids = list(_get(ctx, "course_ids", []) or [])
    intent = _get(ctx, "intent")
    stage = _get(ctx, "lead_stage")
    evidence = _collect_facts(ctx)
    provenance = list(_get(ctx, "provenance", []) or [])
    questions = list(_get(ctx, "clarification_questions", []) or [])
    prohibited = _default_prohibited_claims(intent)

    # Downstream decision is a restriction layer: it may reduce permissions,
    # never silently expand them.
    decision_code = _get(decision, "decision")
    decision_response_allowed = _get(decision, "response_allowed", None)
    decision_handoff = bool(_get(decision, "human_handoff_required", False))

    if status == "RESPONSE_CONTEXT_REVIEW" or decision_code == "DECISION_HUMAN_REVIEW" or decision_handoff:
        final_status, mode, goal = RESPONSE_HUMAN_REVIEW, MODE_HUMAN, "Resolve conflicting lead state through human review."
        allowed = False
        handoff = True
    elif status == "RESPONSE_CONTEXT_INSUFFICIENT" or decision_code == "DECISION_OBTAIN_CRM":
        final_status, mode, goal = RESPONSE_OBTAIN_STATE, MODE_OBTAIN_STATE, "Obtain authoritative CRM lead state before responding."
        allowed = False
        handoff = False
    elif status == "RESPONSE_CONTEXT_UNKNOWN" or decision_code == "DECISION_UNKNOWN":
        final_status, mode, goal = RESPONSE_UNKNOWN, MODE_NONE, "Do not invent missing lead state."
        allowed = False
        handoff = False
    elif status == "RESPONSE_CONTEXT_CLARIFICATION" or decision_code == "DECISION_CLARIFY":
        final_status, mode, goal = RESPONSE_CLARIFICATION, MODE_CLARIFY, "Clarify the minimum missing or ambiguous lead-state information."
        allowed = False
        handoff = False
    else:
        final_status, mode, goal = RESPONSE_READY, MODE_GROUNDED, "Prepare a grounded response using only supported evidence."
        allowed = True
        handoff = False

    if decision_response_allowed is False:
        allowed = False
        if decision_code == "DECISION_HUMAN_REVIEW":
            final_status, mode, goal, handoff = RESPONSE_HUMAN_REVIEW, MODE_HUMAN, "Resolve conflicting lead state through human review.", True
        elif decision_code == "DECISION_CLARIFY":
            final_status, mode, goal = RESPONSE_CLARIFICATION, MODE_CLARIFY, "Clarify the minimum missing or ambiguous lead-state information."
        elif decision_code == "DECISION_OBTAIN_CRM":
            final_status, mode, goal = RESPONSE_OBTAIN_STATE, MODE_OBTAIN_STATE, "Obtain authoritative CRM lead state before responding."
        elif decision_code == "DECISION_UNKNOWN":
            final_status, mode, goal = RESPONSE_UNKNOWN, MODE_NONE, "Do not invent missing lead state."

    # Bring in only attributable, non-executing planning evidence.
    auxiliary = [
        ("COURSE_ANSWER", course_answer),
        ("COMMERCIAL_PLAN", commercial_plan),
        ("COUNSELLING_PLAN", counselling_plan),
        ("OBJECTION_PLAN", objection_plan),
        ("ENROLLMENT_READINESS", enrollment_readiness),
    ]
    for source, obj in auxiliary:
        if obj is not None:
            provenance.append(source)

    return GroundedResponseResult(
        plan=GroundedResponsePlan(
            status=final_status,
            mode=mode,
            lead_id=lead_id,
            course_ids=course_ids,
            intent=intent,
            lead_stage=stage,
            response_goal=goal,
            evidence=evidence,
            clarification_questions=questions,
            prohibited_claims=prohibited,
            provenance=list(dict.fromkeys(provenance)),
            human_handoff_required=handoff,
            message_send_allowed=False,
            crm_write_allowed=False,
            errors=[],
        )
    )

def run_grounded_response_orchestration(
    response_context=None, decision_result=None, course_answer=None,
    commercial_plan=None, counselling_plan=None, objection_plan=None,
    enrollment_readiness=None
):
    return build_grounded_response_plan(
        response_context, decision_result, course_answer, commercial_plan,
        counselling_plan, objection_plan, enrollment_readiness
    )

def validate_grounded_response(result: GroundedResponseResult) -> List[str]:
    errors = []
    p = result.plan
    if p.message_send_allowed is not False:
        errors.append("Message sending must remain disabled.")
    if p.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if p.status == RESPONSE_READY and p.mode != MODE_GROUNDED:
        errors.append("READY status requires grounded response mode.")
    if p.status == RESPONSE_HUMAN_REVIEW and not p.human_handoff_required:
        errors.append("Human review requires handoff.")
    if p.status in {RESPONSE_CLARIFICATION, RESPONSE_OBTAIN_STATE, RESPONSE_UNKNOWN, RESPONSE_HUMAN_REVIEW} and p.mode == MODE_GROUNDED:
        errors.append("Restricted states cannot use normal grounded response mode.")
    for e in p.evidence:
        if not e.safe_to_use:
            errors.append("Unsafe evidence cannot be included as usable response evidence.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled"):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def grounded_response_to_dict(result: GroundedResponseResult) -> Dict[str, Any]:
    p = result.plan
    return {
        "plan": {
            "status": p.status,
            "mode": p.mode,
            "lead_id": p.lead_id,
            "course_ids": list(p.course_ids),
            "intent": p.intent,
            "lead_stage": p.lead_stage,
            "response_goal": p.response_goal,
            "evidence": [
                {"field": e.field, "value": deepcopy(e.value), "source": e.source,
                 "course_id": e.course_id, "safe_to_use": e.safe_to_use, "note": e.note}
                for e in p.evidence
            ],
            "clarification_questions": list(p.clarification_questions),
            "prohibited_claims": list(p.prohibited_claims),
            "provenance": list(p.provenance),
            "human_handoff_required": p.human_handoff_required,
            "message_send_allowed": p.message_send_allowed,
            "crm_write_allowed": p.crm_write_allowed,
            "errors": list(p.errors),
        },
        "safety": dict(result.safety),
    }

def build_grounded_response_layer():
    return {
        "layer": "AI_CORE_20",
        "name": "CRM-Aware Grounded Response Orchestration",
        "read_only": True,
        "response_planning": True,
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "execution_enabled": False,
        "external_actions_enabled": False,
        "fail_closed": True,
    }
