
"""
Sayyed EdVantage AI Agent — AI Core 21
Unified Agent Turn Composition & CRM-Aware Response Contract

Read-only integration layer:
- composes the outputs of CRM-aware response orchestration into one agent-turn contract
- preserves lead/course/intent/stage and provenance
- distinguishes response-ready, clarification, CRM-state, and human-review outcomes
- carries forward commercial/career/certification safety
- never sends messages, writes CRM, performs external actions, or executes workflows
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

TURN_READY = "TURN_READY"
TURN_CLARIFICATION = "TURN_CLARIFICATION"
TURN_HUMAN_REVIEW = "TURN_HUMAN_REVIEW"
TURN_OBTAIN_STATE = "TURN_OBTAIN_STATE"
TURN_UNKNOWN = "TURN_UNKNOWN"

MODE_RESPONSE = "RESPOND"
MODE_CLARIFY = "CLARIFY"
MODE_HUMAN = "HUMAN_REVIEW"
MODE_OBTAIN_STATE = "OBTAIN_STATE"
MODE_NONE = "NO_ACTION"

@dataclass
class TurnEvidence:
    field: str
    value: Any
    source: str
    course_id: Optional[str] = None
    safe_to_use: bool = True
    note: str = ""

@dataclass
class AgentTurnContract:
    turn_status: str
    mode: str
    lead_id: Optional[str]
    course_ids: List[str]
    intent: Optional[str]
    lead_stage: Optional[str]
    response_goal: str
    evidence: List[TurnEvidence] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    response_preparation_allowed: bool = False
    message_send_allowed: bool = False
    crm_write_allowed: bool = False
    external_action_allowed: bool = False
    errors: List[str] = field(default_factory=list)

@dataclass
class AgentTurnResult:
    contract: AgentTurnContract
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

def _plan_obj(plan_result: Any):
    if plan_result is None:
        return None
    # Accept either a serialized plan dict or a wrapper containing "plan".
    if isinstance(plan_result, dict):
        return plan_result.get("plan", plan_result)
    return _get(plan_result, "plan", plan_result)

def _facts(response_context: Any) -> List[TurnEvidence]:
    raw = _get(response_context, "facts", []) or []
    out = []
    for f in raw:
        value = _get(f, "value")
        if value is None:
            continue
        out.append(TurnEvidence(
            field=_get(f, "field", "unknown"),
            value=deepcopy(value),
            source=_get(f, "source", "UNKNOWN"),
            course_id=_get(f, "course_id"),
            safe_to_use=bool(_get(f, "usable", True)),
            note=_get(f, "note", ""),
        ))
    return out

def compose_agent_turn(
    response_context: Any = None,
    response_plan: Any = None,
    crm_decision: Any = None,
    conversation_context: Any = None,
    intelligence: Any = None,
) -> AgentTurnResult:
    ctx = response_context
    plan = _plan_obj(response_plan) if response_plan is not None else response_plan
    decision = _get(crm_decision, "decision") if crm_decision is not None else None
    conv = conversation_context or {}
    intel = intelligence or {}

    lead_id = _get(ctx, "lead_id")
    course_ids = list(_get(ctx, "course_ids", []) or [])
    intent = _get(ctx, "intent")
    stage = _get(ctx, "lead_stage")
    provenance = list(_get(ctx, "provenance", []) or [])
    evidence = _facts(ctx)
    questions = list(_get(ctx, "clarification_questions", []) or [])
    prohibited = list(_get(plan, "prohibited_claims", []) or [])

    ctx_status = _get(ctx, "status", "RESPONSE_CONTEXT_UNKNOWN")
    plan_status = _get(plan, "status", None)
    decision_code = _get(decision, "decision", None)

    # Strict precedence: material conflict/human review > missing state >
    # unknown > clarification > normal response.
    if ctx_status == "RESPONSE_CONTEXT_REVIEW" or plan_status == "RESPONSE_HUMAN_REVIEW" or decision_code == "DECISION_HUMAN_REVIEW":
        turn_status, mode, goal, handoff = TURN_HUMAN_REVIEW, MODE_HUMAN, "Resolve lead-state conflict through human review.", True
        prep = False
    elif ctx_status == "RESPONSE_CONTEXT_INSUFFICIENT" or plan_status == "RESPONSE_OBTAIN_STATE" or decision_code == "DECISION_OBTAIN_CRM":
        turn_status, mode, goal, handoff = TURN_OBTAIN_STATE, MODE_OBTAIN_STATE, "Obtain authoritative CRM state before continuing.", False
        prep = False
    elif ctx_status == "RESPONSE_CONTEXT_UNKNOWN" or plan_status == "RESPONSE_UNKNOWN" or decision_code == "DECISION_UNKNOWN":
        turn_status, mode, goal, handoff = TURN_UNKNOWN, MODE_NONE, "Do not invent missing lead state.", False
        prep = False
    elif ctx_status == "RESPONSE_CONTEXT_CLARIFICATION" or plan_status == "RESPONSE_CLARIFICATION" or decision_code == "DECISION_CLARIFY":
        turn_status, mode, goal, handoff = TURN_CLARIFICATION, MODE_CLARIFY, "Clarify the minimum missing or ambiguous lead information.", False
        prep = False
    else:
        turn_status, mode, goal, handoff = TURN_READY, MODE_RESPONSE, "Prepare a grounded response using supported evidence.", False
        prep = True

    # The downstream plan can only restrict preparation.
    if _get(plan, "mode") in {"HUMAN_REVIEW", "OBTAIN_CRM_STATE", "NO_RESPONSE", "ASK_CLARIFICATION"}:
        prep = False

    for src, obj in [
        ("RESPONSE_PLAN", response_plan),
        ("CRM_DECISION", crm_decision),
        ("CONVERSATION_CONTEXT", conversation_context),
        ("AI_INTELLIGENCE", intelligence),
    ]:
        if obj is not None:
            provenance.append(src)

    return AgentTurnResult(
        contract=AgentTurnContract(
            turn_status=turn_status,
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
            response_preparation_allowed=prep,
            message_send_allowed=False,
            crm_write_allowed=False,
            external_action_allowed=False,
            errors=[],
        )
    )

def run_agent_turn_composition(
    response_context=None,
    response_plan=None,
    crm_decision=None,
    conversation_context=None,
    intelligence=None,
):
    return compose_agent_turn(
        response_context, response_plan, crm_decision,
        conversation_context, intelligence
    )

def validate_agent_turn(result: AgentTurnResult) -> List[str]:
    errors = []
    c = result.contract
    if c.message_send_allowed is not False:
        errors.append("Message sending must remain disabled.")
    if c.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if c.external_action_allowed is not False:
        errors.append("External actions must remain disabled.")
    if c.turn_status == TURN_READY:
        if c.mode != MODE_RESPONSE:
            errors.append("TURN_READY requires RESPOND mode.")
        if c.response_preparation_allowed is not True:
            errors.append("TURN_READY requires response preparation permission.")
    if c.turn_status == TURN_HUMAN_REVIEW:
        if not c.human_handoff_required:
            errors.append("Human-review turn requires handoff.")
        if c.response_preparation_allowed:
            errors.append("Human-review turn cannot permit normal response preparation.")
    if c.turn_status in {TURN_CLARIFICATION, TURN_OBTAIN_STATE, TURN_UNKNOWN} and c.response_preparation_allowed:
        errors.append("Restricted turn cannot permit normal response preparation.")
    if any(not e.safe_to_use for e in c.evidence):
        errors.append("Unsafe evidence cannot be included in a turn contract.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled"):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def agent_turn_to_dict(result: AgentTurnResult) -> Dict[str, Any]:
    c = result.contract
    return {
        "contract": {
            "turn_status": c.turn_status,
            "mode": c.mode,
            "lead_id": c.lead_id,
            "course_ids": list(c.course_ids),
            "intent": c.intent,
            "lead_stage": c.lead_stage,
            "response_goal": c.response_goal,
            "evidence": [
                {"field": e.field, "value": deepcopy(e.value), "source": e.source,
                 "course_id": e.course_id, "safe_to_use": e.safe_to_use, "note": e.note}
                for e in c.evidence
            ],
            "clarification_questions": list(c.clarification_questions),
            "prohibited_claims": list(c.prohibited_claims),
            "provenance": list(c.provenance),
            "human_handoff_required": c.human_handoff_required,
            "response_preparation_allowed": c.response_preparation_allowed,
            "message_send_allowed": c.message_send_allowed,
            "crm_write_allowed": c.crm_write_allowed,
            "external_action_allowed": c.external_action_allowed,
            "errors": list(c.errors),
        },
        "safety": dict(result.safety),
    }

def build_agent_turn_composition_layer():
    return {
        "layer": "AI_CORE_21",
        "name": "Unified Agent Turn Composition & CRM-Aware Response Contract",
        "read_only": True,
        "response_preparation": True,
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "execution_enabled": False,
        "fail_closed": True,
    }
