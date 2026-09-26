
"""
Sayyed EdVantage AI Agent — AI Core 23
CRM-Aware Admission Action Readiness & Verification Intelligence

Read-only boundary layer between admission-journey guidance and any future
authorized action executor. It determines whether a proposed application,
payment, or enrollment step is sufficiently verified and authorized to be
handed to an executor. It never executes the action, sends messages, writes
CRM, or claims that an action occurred.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

ACTION_APPLICATION = "APPLICATION"
ACTION_PAYMENT = "PAYMENT"
ACTION_ENROLLMENT = "ENROLLMENT"
ACTION_NONE = "NONE"

STATUS_READY = "ACTION_READINESS_READY"
STATUS_CLARIFICATION = "ACTION_READINESS_CLARIFICATION"
STATUS_REVIEW = "ACTION_READINESS_REVIEW"
STATUS_BLOCKED = "ACTION_READINESS_BLOCKED"
STATUS_UNKNOWN = "ACTION_READINESS_UNKNOWN"

DECISION_PREPARE = "PREPARE_FOR_AUTHORIZED_EXECUTION"
DECISION_CLARIFY = "CLARIFY_BEFORE_EXECUTION"
DECISION_REVIEW = "HUMAN_REVIEW_BEFORE_EXECUTION"
DECISION_BLOCK = "BLOCK_EXECUTION"
DECISION_OBTAIN_STATE = "OBTAIN_VERIFIED_STATE"
DECISION_NONE = "NO_ACTION"

AUTH_UNKNOWN = "UNKNOWN"
AUTH_REQUESTED = "REQUESTED"
AUTH_GRANTED = "GRANTED"
AUTH_DENIED = "DENIED"
AUTH_REVOKED = "REVOKED"
AUTH_EXPIRED = "EXPIRED"

@dataclass
class ActionReadinessEvidence:
    field: str
    value: Any
    source: str
    verified: bool = True
    required: bool = False
    note: str = ""

@dataclass
class AdmissionActionReadiness:
    status: str
    decision: str
    proposed_action: str
    lead_id: Optional[str]
    course_ids: List[str]
    crm_stage: Optional[str]
    authorization_state: str
    rationale: str
    evidence: List[ActionReadinessEvidence] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    execution_authorized: bool = False
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
class AdmissionActionReadinessResult:
    plan: AdmissionActionReadiness
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _plan_obj(obj):
    if isinstance(obj, dict) and "plan" in obj:
        return obj["plan"]
    return obj

def _norm(v):
    return str(v).strip().lower() if v is not None else ""

def _auth_value(authorization):
    if authorization is None:
        return AUTH_UNKNOWN
    p = _plan_obj(authorization)
    v = _get(p, "authorization_state")
    if v is None:
        v = _get(p, "status")
    v = str(v).upper() if v is not None else AUTH_UNKNOWN
    aliases = {
        "GRANTED":"GRANTED", "REQUESTED":"REQUESTED", "DENIED":"DENIED",
        "REVOKED":"REVOKED", "EXPIRED":"EXPIRED", "UNKNOWN":"UNKNOWN",
        "AUTHORIZATION_GRANTED":"GRANTED",
        "AUTHORIZATION_REQUESTED":"REQUESTED",
        "AUTHORIZATION_DENIED":"DENIED",
        "AUTHORIZATION_REVOKED":"REVOKED",
        "AUTHORIZATION_EXPIRED":"EXPIRED",
    }
    return aliases.get(v, AUTH_UNKNOWN)

def _stage_action(stage):
    s = _norm(stage)
    if s == "application":
        return ACTION_APPLICATION
    if s == "payment pending":
        return ACTION_PAYMENT
    if s == "enrolled":
        return ACTION_ENROLLMENT
    return ACTION_NONE

def _claims():
    return [
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "Do not execute, send, or write CRM from this read-only intelligence layer.",
    ]

def build_admission_action_readiness(
    journey_result=None,
    crm_snapshot=None,
    authorization=None,
    commercial_plan=None,
    response_turn=None,
):
    journey = _plan_obj(journey_result)
    crm = deepcopy(crm_snapshot or {})
    auth = _auth_value(authorization)

    lead_id = crm.get("lead_id") or _get(journey, "lead_id")
    course_ids = list(_get(journey, "course_ids", []) or [])
    if not course_ids and crm.get("course_id"):
        course_ids = [crm["course_id"]]

    stage = crm.get("stage") or _get(journey, "crm_stage")
    proposed = _stage_action(stage)

    evidence = []
    provenance = []

    if journey_result is not None:
        provenance.append("ADMISSION_JOURNEY")
    if crm:
        provenance.append("CRM_READ")
    if authorization is not None:
        provenance.append("AUTHORIZATION")
    if commercial_plan is not None:
        provenance.append("COMMERCIAL_CONVERSATION")
    if response_turn is not None:
        provenance.append("AGENT_TURN")

    if lead_id:
        evidence.append(ActionReadinessEvidence(
            "lead_id", lead_id,
            "CRM_READ" if crm.get("lead_id") else "ADMISSION_JOURNEY"
        ))
    if stage:
        evidence.append(ActionReadinessEvidence(
            "crm_stage", stage,
            "CRM_READ" if crm.get("stage") else "ADMISSION_JOURNEY"
        ))
    if course_ids:
        evidence.append(ActionReadinessEvidence(
            "course_ids", course_ids,
            "ADMISSION_JOURNEY" if _get(journey, "course_ids") else "CRM_READ"
        ))
    if auth != AUTH_UNKNOWN:
        evidence.append(ActionReadinessEvidence(
            "authorization_state", auth, "AUTHORIZATION"
        ))

    missing = []
    questions = []
    errors = []
    human = False
    status = STATUS_UNKNOWN
    decision = DECISION_OBTAIN_STATE
    rationale = "Verified state is insufficient to determine a safe admission action boundary."

    # Safety precedence: upstream review/conflict wins.
    if (
        _get(journey, "human_handoff_required")
        or _get(journey, "status") in {"JOURNEY_REVIEW", "TURN_HUMAN_REVIEW"}
    ):
        status, decision = STATUS_REVIEW, DECISION_REVIEW
        human = True
        rationale = "Upstream admission state requires human review before any action could be considered."

    elif _get(journey, "status") in {"JOURNEY_CLARIFICATION", "JOURNEY_UNKNOWN"}:
        if _get(journey, "status") == "JOURNEY_CLARIFICATION":
            status, decision = STATUS_CLARIFICATION, DECISION_CLARIFY
        else:
            status, decision = STATUS_UNKNOWN, DECISION_OBTAIN_STATE
        questions = list(_get(journey, "clarification_questions", []) or [])
        if not questions:
            questions = ["Please confirm the verified lead and admission journey state before proceeding."]
        rationale = "Clarification or verified state is required before an admission action boundary can be prepared."

    elif proposed == ACTION_NONE:
        status, decision = STATUS_BLOCKED, DECISION_BLOCK
        rationale = "The current CRM stage does not establish an application, payment, or enrollment action."

    else:
        if not lead_id:
            missing.append("verified lead_id")
        if not course_ids:
            missing.append("verified course_id")
        if auth != AUTH_GRANTED:
            missing.append("explicit granted authorization")
        if proposed == ACTION_PAYMENT and commercial_plan is None:
            missing.append("verified commercial/payment details")

        if missing:
            if auth in {AUTH_DENIED, AUTH_REVOKED, AUTH_EXPIRED}:
                status, decision = STATUS_BLOCKED, DECISION_BLOCK
                rationale = f"Execution is blocked because authorization is {auth.lower()}."
            elif not lead_id or not course_ids:
                status, decision = STATUS_UNKNOWN, DECISION_OBTAIN_STATE
                rationale = "Required verified lead/course state is missing."
            else:
                status, decision = STATUS_CLARIFICATION, DECISION_CLARIFY
                questions = ["Please provide/confirm the missing verified admission details before proceeding."]
                rationale = "The proposed action is identifiable, but required verification or authorization is incomplete."
        else:
            status, decision = STATUS_READY, DECISION_PREPARE
            rationale = "Required verified state and explicit authorization are present; prepare only for a separate executor."

    # Critical boundary: this layer never authorizes actual execution.
    return AdmissionActionReadinessResult(
        plan=AdmissionActionReadiness(
            status=status,
            decision=decision,
            proposed_action=proposed,
            lead_id=lead_id,
            course_ids=course_ids,
            crm_stage=stage,
            authorization_state=auth,
            rationale=rationale,
            evidence=evidence,
            missing_requirements=missing,
            clarification_questions=questions,
            human_handoff_required=human,
            execution_authorized=False,
            application_occurred=False,
            payment_occurred=False,
            enrollment_occurred=False,
            crm_write_allowed=False,
            message_send_allowed=False,
            external_action_allowed=False,
            prohibited_claims=_claims(),
            provenance=list(dict.fromkeys(provenance)),
            errors=errors,
        )
    )

def run_admission_action_readiness(*args, **kwargs):
    return build_admission_action_readiness(*args, **kwargs)

def validate_admission_action_readiness(result):
    errors = []
    p = result.plan
    valid_status = {
        STATUS_READY, STATUS_CLARIFICATION, STATUS_REVIEW,
        STATUS_BLOCKED, STATUS_UNKNOWN
    }
    valid_decision = {
        DECISION_PREPARE, DECISION_CLARIFY, DECISION_REVIEW,
        DECISION_BLOCK, DECISION_OBTAIN_STATE, DECISION_NONE
    }

    if p.status not in valid_status:
        errors.append("Invalid action-readiness status.")
    if p.decision not in valid_decision:
        errors.append("Invalid action-readiness decision.")
    if p.execution_authorized is not False:
        errors.append("Actual execution authorization must remain False.")
    if p.application_occurred or p.payment_occurred or p.enrollment_occurred:
        errors.append("Occurrence claims must remain False.")
    if p.crm_write_allowed is not False:
        errors.append("CRM writes must remain disabled.")
    if p.message_send_allowed is not False:
        errors.append("Message sending must remain disabled.")
    if p.external_action_allowed is not False:
        errors.append("External actions must remain disabled.")
    if p.status == STATUS_REVIEW and not p.human_handoff_required:
        errors.append("Review requires human handoff.")
    if p.status == STATUS_READY and p.decision != DECISION_PREPARE:
        errors.append("Ready status requires prepare decision.")
    if (
        p.authorization_state in {AUTH_DENIED, AUTH_REVOKED, AUTH_EXPIRED}
        and p.decision == DECISION_PREPARE
    ):
        errors.append("Negative authorization cannot produce a prepare decision.")

    for e in p.evidence:
        if not e.verified:
            errors.append("Unverified evidence cannot be treated as verified.")

    for k in (
        "execution_enabled", "messaging_enabled",
        "external_actions_enabled", "crm_writes_enabled"
    ):
        if result.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def admission_action_readiness_to_dict(result):
    p = result.plan
    return {
        "plan": {
            "status": p.status,
            "decision": p.decision,
            "proposed_action": p.proposed_action,
            "lead_id": p.lead_id,
            "course_ids": list(p.course_ids),
            "crm_stage": p.crm_stage,
            "authorization_state": p.authorization_state,
            "rationale": p.rationale,
            "evidence": [
                {
                    "field": e.field,
                    "value": deepcopy(e.value),
                    "source": e.source,
                    "verified": e.verified,
                    "required": e.required,
                    "note": e.note,
                }
                for e in p.evidence
            ],
            "missing_requirements": list(p.missing_requirements),
            "clarification_questions": list(p.clarification_questions),
            "human_handoff_required": p.human_handoff_required,
            "execution_authorized": p.execution_authorized,
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

def validate_serialized_action_readiness(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("plan"), dict):
        return ["Serialized result must contain plan."]
    p = data["plan"]
    for k in ("status", "decision", "proposed_action", "authorization_state"):
        if k not in p:
            errors.append(f"Missing serialized field: {k}")
    if p.get("execution_authorized") is not False:
        errors.append("Serialized execution_authorized must be False.")
    if p.get("crm_write_allowed") is not False:
        errors.append("Serialized crm_write_allowed must be False.")
    if p.get("message_send_allowed") is not False:
        errors.append("Serialized message_send_allowed must be False.")
    if p.get("external_action_allowed") is not False:
        errors.append("Serialized external_action_allowed must be False.")
    return errors
