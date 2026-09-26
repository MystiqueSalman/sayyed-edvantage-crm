
"""
Sayyed EdVantage AI Agent — AI Core 22
CRM-Aware Admission Journey Intelligence

Read-only admission-journey layer:
- interprets verified CRM stage and conversational readiness
- maps lead state to the safest next admission journey step
- distinguishes interest/application/payment/enrollment readiness
- preserves human-review and authorization boundaries
- never claims that an application, payment, or enrollment occurred
- never writes CRM, sends messages, or executes external actions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

JOURNEY_INTERESTED = "JOURNEY_INTERESTED"
JOURNEY_APPLICATION = "JOURNEY_APPLICATION"
JOURNEY_PAYMENT = "JOURNEY_PAYMENT"
JOURNEY_ENROLLMENT = "JOURNEY_ENROLLMENT"
JOURNEY_CLARIFICATION = "JOURNEY_CLARIFICATION"
JOURNEY_REVIEW = "JOURNEY_REVIEW"
JOURNEY_UNKNOWN = "JOURNEY_UNKNOWN"

NEXT_DISCUSS = "DISCUSS_AND_QUALIFY"
NEXT_APPLICATION = "PREPARE_APPLICATION_GUIDANCE"
NEXT_PAYMENT = "PREPARE_PAYMENT_GUIDANCE"
NEXT_ENROLLMENT = "PREPARE_ENROLLMENT_GUIDANCE"
NEXT_CLARIFY = "CLARIFY"
NEXT_REVIEW = "HUMAN_REVIEW"
NEXT_OBTAIN_STATE = "OBTAIN_STATE"
NEXT_NONE = "NO_ACTION"

@dataclass
class JourneyEvidence:
    field: str
    value: Any
    source: str
    verified: bool = True
    note: str = ""

@dataclass
class AdmissionJourneyPlan:
    status: str
    next_step: str
    lead_id: Optional[str]
    course_ids: List[str]
    crm_stage: Optional[str]
    readiness_status: Optional[str]
    rationale: str
    evidence: List[JourneyEvidence] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    application_occurred: bool = False
    payment_occurred: bool = False
    enrollment_occurred: bool = False
    crm_write_allowed: bool = False
    message_send_allowed: bool = False
    external_action_allowed: bool = False
    prohibited_claims: List[str] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class AdmissionJourneyResult:
    plan: AdmissionJourneyPlan
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

def _readiness_obj(value: Any):
    if isinstance(value, dict):
        return value.get("readiness", value)
    return value

def _stage_to_journey(stage: Optional[str]) -> Optional[str]:
    if not stage:
        return None
    s = str(stage).strip().lower()
    mapping = {
        "new": JOURNEY_INTERESTED,
        "contacted": JOURNEY_INTERESTED,
        "counselling": JOURNEY_INTERESTED,
        "interested": JOURNEY_INTERESTED,
        "application": JOURNEY_APPLICATION,
        "payment pending": JOURNEY_PAYMENT,
        "enrolled": JOURNEY_ENROLLMENT,
        "lost": JOURNEY_UNKNOWN,
    }
    return mapping.get(s)

def _claims() -> List[str]:
    return [
        "Do not claim that an application has been submitted unless independently verified.",
        "Do not claim that payment has been received unless independently verified.",
        "Do not claim that enrollment has occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "Do not perform or imply CRM updates, messaging, or external actions from this read-only layer.",
    ]

def build_admission_journey_plan(
    crm_snapshot: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
    readiness: Any = None,
    response_turn: Any = None,
    sync_result: Any = None,
) -> AdmissionJourneyResult:
    crm = deepcopy(crm_snapshot or {})
    ctx = deepcopy(conversation_context or {})
    ready = _readiness_obj(readiness)

    lead_id = crm.get("lead_id") or ctx.get("lead_id")
    course_ids = list(ctx.get("active_course_ids") or [])
    if not course_ids and crm.get("course_id"):
        course_ids = [crm["course_id"]]

    stage = crm.get("stage")
    readiness_status = _get(ready, "status")
    sync_status = _get(sync_result, "status")
    turn_status = _get(response_turn, "turn_status")

    evidence = []
    if lead_id:
        evidence.append(JourneyEvidence("lead_id", lead_id,
            "CRM_READ" if crm.get("lead_id") else "CONVERSATION_CONTEXT"))
    if stage:
        evidence.append(JourneyEvidence("crm_stage", stage, "CRM_READ"))
    if course_ids:
        evidence.append(JourneyEvidence("course_ids", course_ids,
            "CONVERSATION_CONTEXT" if ctx.get("active_course_ids") else "CRM_READ"))
    if readiness_status:
        evidence.append(JourneyEvidence("readiness_status", readiness_status, "ADMISSION_READINESS"))

    provenance = []
    if crm: provenance.append("CRM_READ")
    if ctx: provenance.append("CONVERSATION_CONTEXT")
    if readiness is not None: provenance.append("ADMISSION_READINESS")
    if response_turn is not None: provenance.append("AGENT_TURN")
    if sync_result is not None: provenance.append("STATE_SYNCHRONIZATION")

    # Safety precedence: review/conflict first.
    if sync_status == "SYNC_REVIEW" or turn_status == "TURN_HUMAN_REVIEW":
        status, next_step, rationale = JOURNEY_REVIEW, NEXT_REVIEW, \
            "Lead state requires human review before progressing the admission journey."
        handoff = True
        questions = list(_get(sync_result, "clarification_questions", []) or [])
    elif sync_status in {"SYNC_INSUFFICIENT", "SYNC_UNKNOWN"} or turn_status in {"TURN_OBTAIN_STATE", "TURN_UNKNOWN"}:
        status, next_step, rationale = JOURNEY_UNKNOWN, NEXT_OBTAIN_STATE, \
            "Authoritative lead state is insufficient for a safe admission-journey decision."
        handoff = False
        questions = []
    elif sync_status == "SYNC_CLARIFICATION" or turn_status == "TURN_CLARIFICATION":
        status, next_step, rationale = JOURNEY_CLARIFICATION, NEXT_CLARIFY, \
            "Clarify the minimum lead-state information before advancing the journey."
        handoff = False
        questions = list(_get(sync_result, "clarification_questions", []) or [])
    else:
        mapped = _stage_to_journey(stage)
        if readiness_status in {"ENROLLMENT_FLOW_READY", "ADMISSION_READY"}:
            if mapped == JOURNEY_ENROLLMENT or str(stage).lower() == "enrolled":
                status, next_step, rationale = JOURNEY_ENROLLMENT, NEXT_ENROLLMENT, \
                    "The lead is at an enrollment-ready journey state; prepare guidance only."
            elif mapped == JOURNEY_PAYMENT or str(stage).lower() == "payment pending":
                status, next_step, rationale = JOURNEY_PAYMENT, NEXT_PAYMENT, \
                    "The lead is at a payment-ready journey state; prepare payment guidance only."
            elif mapped == JOURNEY_APPLICATION or str(stage).lower() == "application":
                status, next_step, rationale = JOURNEY_APPLICATION, NEXT_APPLICATION, \
                    "The lead is at an application-ready journey state; prepare application guidance only."
            else:
                status, next_step, rationale = JOURNEY_APPLICATION, NEXT_APPLICATION, \
                    "Admission readiness is available; prepare the next verified application step."
        elif mapped == JOURNEY_PAYMENT:
            status, next_step, rationale = JOURNEY_PAYMENT, NEXT_PAYMENT, \
                "CRM indicates payment-pending stage; prepare guidance without claiming payment."
        elif mapped == JOURNEY_APPLICATION:
            status, next_step, rationale = JOURNEY_APPLICATION, NEXT_APPLICATION, \
                "CRM indicates application stage; prepare guidance without claiming submission."
        elif mapped == JOURNEY_ENROLLMENT:
            status, next_step, rationale = JOURNEY_ENROLLMENT, NEXT_ENROLLMENT, \
                "CRM indicates enrollment stage; do not claim enrollment beyond verified CRM facts."
        elif mapped == JOURNEY_INTERESTED:
            status, next_step, rationale = JOURNEY_INTERESTED, NEXT_DISCUSS, \
                "Lead remains in interest/qualification journey; continue grounded counselling."
        else:
            status, next_step, rationale = JOURNEY_UNKNOWN, NEXT_NONE, \
                "No supported admission journey state is established."
        handoff = False
        questions = []

    return AdmissionJourneyResult(
        plan=AdmissionJourneyPlan(
            status=status,
            next_step=next_step,
            lead_id=lead_id,
            course_ids=course_ids,
            crm_stage=stage,
            readiness_status=readiness_status,
            rationale=rationale,
            evidence=evidence,
            clarification_questions=questions,
            human_handoff_required=handoff,
            application_occurred=False,
            payment_occurred=False,
            enrollment_occurred=False,
            crm_write_allowed=False,
            message_send_allowed=False,
            external_action_allowed=False,
            prohibited_claims=_claims(),
            provenance=list(dict.fromkeys(provenance)),
            errors=[],
        )
    )

def run_admission_journey_intelligence(
    crm_snapshot=None, conversation_context=None, readiness=None,
    response_turn=None, sync_result=None
):
    return build_admission_journey_plan(
        crm_snapshot, conversation_context, readiness, response_turn, sync_result
    )

def validate_admission_journey(result: AdmissionJourneyResult) -> List[str]:
    errors = []
    p = result.plan
    if p.application_occurred:
        errors.append("Application occurrence must remain False in read-only journey intelligence.")
    if p.payment_occurred:
        errors.append("Payment occurrence must remain False in read-only journey intelligence.")
    if p.enrollment_occurred:
        errors.append("Enrollment occurrence must remain False in read-only journey intelligence.")
    if p.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if p.message_send_allowed is not False:
        errors.append("Message sending must remain disabled.")
    if p.external_action_allowed is not False:
        errors.append("External actions must remain disabled.")
    if p.status == JOURNEY_REVIEW and not p.human_handoff_required:
        errors.append("Review status requires human handoff.")
    for e in p.evidence:
        if not e.verified:
            errors.append("Unverified evidence cannot be used as verified journey evidence.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled"):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def admission_journey_to_dict(result: AdmissionJourneyResult) -> Dict[str, Any]:
    p = result.plan
    return {
        "plan": {
            "status": p.status,
            "next_step": p.next_step,
            "lead_id": p.lead_id,
            "course_ids": list(p.course_ids),
            "crm_stage": p.crm_stage,
            "readiness_status": p.readiness_status,
            "rationale": p.rationale,
            "evidence": [
                {"field":e.field,"value":deepcopy(e.value),"source":e.source,
                 "verified":e.verified,"note":e.note}
                for e in p.evidence
            ],
            "clarification_questions": list(p.clarification_questions),
            "human_handoff_required": p.human_handoff_required,
            "application_occurred": p.application_occurred,
            "payment_occurred": p.payment_occurred,
            "enrollment_occurred": p.enrollment_occurred,
            "crm_write_allowed": p.crm_write_allowed,
            "message_send_allowed": p.message_send_allowed,
            "external_action_allowed": p.external_action_allowed,
            "prohibited_claims": list(p.prohibited_claims),
            "provenance": list(p.provenance),
            "errors": list(p.errors),
        },
        "safety": dict(result.safety),
    }

def build_admission_journey_layer():
    return {
        "layer": "AI_CORE_22",
        "name": "CRM-Aware Admission Journey Intelligence",
        "read_only": True,
        "admission_journey_intelligence": True,
        "crm_writes_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "execution_enabled": False,
        "fail_closed": True,
    }
