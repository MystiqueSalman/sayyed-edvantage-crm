
"""
Sayyed EdVantage AI Agent — AI Core 24
Admission Action Handoff & Execution Boundary Contract

This read-only layer converts verified Core-23 admission action readiness
into a controlled handoff package for a FUTURE executor. It does not execute,
send, write CRM, or claim completion.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

HANDOFF_APPLICATION = "APPLICATION"
HANDOFF_PAYMENT = "PAYMENT"
HANDOFF_ENROLLMENT = "ENROLLMENT"
HANDOFF_NONE = "NONE"

STATUS_HANDOFF_READY = "HANDOFF_READY"
STATUS_HANDOFF_CLARIFICATION = "HANDOFF_CLARIFICATION"
STATUS_HANDOFF_REVIEW = "HANDOFF_REVIEW"
STATUS_HANDOFF_BLOCKED = "HANDOFF_BLOCKED"
STATUS_HANDOFF_UNKNOWN = "HANDOFF_UNKNOWN"

MODE_PREPARE = "PREPARE_HANDOFF"
MODE_CLARIFY = "CLARIFY_BEFORE_HANDOFF"
MODE_REVIEW = "HUMAN_REVIEW_BEFORE_HANDOFF"
MODE_BLOCK = "BLOCK_HANDOFF"
MODE_OBTAIN_STATE = "OBTAIN_VERIFIED_STATE"
MODE_NONE = "NO_HANDOFF"

@dataclass
class HandoffField:
    field: str
    value: Any
    source: str
    verified: bool = True
    required: bool = False

@dataclass
class AdmissionActionHandoff:
    status: str
    mode: str
    action: str
    lead_id: Optional[str]
    course_ids: List[str]
    crm_stage: Optional[str]
    authorization_state: str
    readiness_status: str
    rationale: str
    fields: List[HandoffField] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    handoff_created: bool = False
    executor_invocation_allowed: bool = False
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
class AdmissionActionHandoffResult:
    handoff: AdmissionActionHandoff
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "executor_invocation_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _obj(value):
    if isinstance(value, dict) and "plan" in value:
        return value["plan"]
    return value

def _claims():
    return [
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not claim a handoff means the action was executed.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def _safe_status(readiness_status):
    s = str(readiness_status or "").upper()
    return s

def build_admission_action_handoff(readiness_result, *, response_turn=None, crm_snapshot=None):
    p = _obj(readiness_result)
    readiness_status = _safe_status(_get(p, "status"))
    action = _get(p, "proposed_action", HANDOFF_NONE)
    lead_id = _get(p, "lead_id")
    course_ids = list(_get(p, "course_ids", []) or [])
    stage = _get(p, "crm_stage")
    auth = str(_get(p, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()

    provenance = ["ACTION_READINESS"]
    if response_turn is not None:
        provenance.append("AGENT_TURN")
    if crm_snapshot is not None:
        provenance.append("CRM_READ")

    fields = []
    if lead_id:
        fields.append(HandoffField("lead_id", lead_id, "ACTION_READINESS", required=True))
    if course_ids:
        fields.append(HandoffField("course_ids", course_ids, "ACTION_READINESS", required=True))
    if stage:
        fields.append(HandoffField("crm_stage", stage, "ACTION_READINESS", required=True))
    fields.append(HandoffField("authorization_state", auth, "ACTION_READINESS", required=True))
    fields.append(HandoffField("action", action, "ACTION_READINESS", required=True))

    missing = list(_get(p, "missing_requirements", []) or [])
    errors = list(_get(p, "errors", []) or [])

    if readiness_status == "ACTION_READINESS_READY":
        status = STATUS_HANDOFF_READY
        mode = MODE_PREPARE
        rationale = "Verified action-readiness permits preparation of a handoff package for a separate future executor."
        created = True
    elif readiness_status == "ACTION_READINESS_REVIEW" or _get(p, "human_handoff_required"):
        status = STATUS_HANDOFF_REVIEW
        mode = MODE_REVIEW
        rationale = "Human review is required before a handoff package can be considered."
        created = False
    elif readiness_status == "ACTION_READINESS_CLARIFICATION":
        status = STATUS_HANDOFF_CLARIFICATION
        mode = MODE_CLARIFY
        rationale = "Action readiness is incomplete; clarification is required before handoff."
        created = False
    elif readiness_status == "ACTION_READINESS_BLOCKED":
        status = STATUS_HANDOFF_BLOCKED
        mode = MODE_BLOCK
        rationale = "The upstream action-readiness layer blocked the proposed action."
        created = False
    else:
        status = STATUS_HANDOFF_UNKNOWN
        mode = MODE_OBTAIN_STATE
        rationale = "Verified action-readiness state is unavailable or unknown."
        created = False

    # A handoff package is never equivalent to authorization or execution.
    if status == STATUS_HANDOFF_READY:
        if not lead_id:
            missing.append("verified lead_id")
        if not course_ids:
            missing.append("verified course_id")
        if auth != "GRANTED":
            missing.append("explicit granted authorization")
        if missing:
            status = STATUS_HANDOFF_CLARIFICATION
            mode = MODE_CLARIFY
            created = False
            rationale = "Required verified fields or authorization are missing from the handoff boundary."

    return AdmissionActionHandoffResult(
        handoff=AdmissionActionHandoff(
            status=status,
            mode=mode,
            action=action,
            lead_id=lead_id,
            course_ids=course_ids,
            crm_stage=stage,
            authorization_state=auth,
            readiness_status=readiness_status,
            rationale=rationale,
            fields=fields,
            missing_requirements=list(dict.fromkeys(missing)),
            human_handoff_required=(status == STATUS_HANDOFF_REVIEW),
            handoff_created=created,
            executor_invocation_allowed=False,
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

def run_admission_action_handoff(*args, **kwargs):
    return build_admission_action_handoff(*args, **kwargs)

def validate_admission_action_handoff(result):
    errors = []
    h = result.handoff
    valid_status = {
        STATUS_HANDOFF_READY, STATUS_HANDOFF_CLARIFICATION,
        STATUS_HANDOFF_REVIEW, STATUS_HANDOFF_BLOCKED, STATUS_HANDOFF_UNKNOWN
    }
    valid_modes = {
        MODE_PREPARE, MODE_CLARIFY, MODE_REVIEW, MODE_BLOCK,
        MODE_OBTAIN_STATE, MODE_NONE
    }
    if h.status not in valid_status:
        errors.append("Invalid handoff status.")
    if h.mode not in valid_modes:
        errors.append("Invalid handoff mode.")
    if h.status == STATUS_HANDOFF_READY and not h.handoff_created:
        errors.append("Ready handoff must be marked created.")
    if h.status != STATUS_HANDOFF_READY and h.handoff_created:
        errors.append("Non-ready handoff cannot be marked created.")
    if h.status == STATUS_HANDOFF_REVIEW and not h.human_handoff_required:
        errors.append("Review requires human handoff.")
    if h.executor_invocation_allowed is not False:
        errors.append("Executor invocation must remain disabled.")
    if h.execution_authorized is not False:
        errors.append("Execution authorization must remain false.")
    if h.application_occurred or h.payment_occurred or h.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if h.crm_write_allowed or h.message_send_allowed or h.external_action_allowed:
        errors.append("Action side effects must remain disabled.")
    for f in h.fields:
        if not f.verified:
            errors.append("Unverified handoff field cannot be marked verified.")
    required = {"lead_id", "course_ids", "authorization_state", "action"}
    present = {f.field for f in h.fields}
    if h.status == STATUS_HANDOFF_READY and not required.issubset(present):
        errors.append("Ready handoff is missing required fields.")
    if h.status == STATUS_HANDOFF_READY and h.authorization_state != "GRANTED":
        errors.append("Ready handoff requires granted authorization.")
    for key in (
        "execution_enabled", "messaging_enabled", "external_actions_enabled",
        "crm_writes_enabled", "executor_invocation_enabled"
    ):
        if result.safety.get(key) is not False:
            errors.append(f"{key} must remain False.")
    if result.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if result.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def admission_action_handoff_to_dict(result):
    h = result.handoff
    return {
        "handoff": {
            "status": h.status,
            "mode": h.mode,
            "action": h.action,
            "lead_id": h.lead_id,
            "course_ids": list(h.course_ids),
            "crm_stage": h.crm_stage,
            "authorization_state": h.authorization_state,
            "readiness_status": h.readiness_status,
            "rationale": h.rationale,
            "fields": [
                {"field": f.field, "value": deepcopy(f.value), "source": f.source,
                 "verified": f.verified, "required": f.required}
                for f in h.fields
            ],
            "missing_requirements": list(h.missing_requirements),
            "human_handoff_required": h.human_handoff_required,
            "handoff_created": h.handoff_created,
            "executor_invocation_allowed": h.executor_invocation_allowed,
            "execution_authorized": h.execution_authorized,
            "application_occurred": h.application_occurred,
            "payment_occurred": h.payment_occurred,
            "enrollment_occurred": h.enrollment_occurred,
            "crm_write_allowed": h.crm_write_allowed,
            "message_send_allowed": h.message_send_allowed,
            "external_action_allowed": h.external_action_allowed,
            "prohibited_claims": list(h.prohibited_claims),
            "provenance": list(h.provenance),
            "errors": list(h.errors),
        },
        "safety": dict(result.safety),
    }

def validate_serialized_admission_action_handoff(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("handoff"), dict):
        return ["Serialized result must contain handoff."]
    h = data["handoff"]
    for k in ("status", "mode", "action", "authorization_state", "readiness_status"):
        if k not in h:
            errors.append(f"Missing serialized field: {k}")
    for k in ("handoff_created", "executor_invocation_allowed", "execution_authorized",
              "crm_write_allowed", "message_send_allowed", "external_action_allowed"):
        if k not in h:
            errors.append(f"Missing serialized safety boundary field: {k}")
    if h.get("executor_invocation_allowed") is not False:
        errors.append("Serialized executor invocation must be False.")
    if h.get("execution_authorized") is not False:
        errors.append("Serialized execution authorization must be False.")
    return errors
