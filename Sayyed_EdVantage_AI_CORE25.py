
"""
Sayyed EdVantage AI Agent — AI Core 25
Admission Action Handoff Integrity & Verification Contract

Purpose:
Validate that a Core-24 admission action handoff is internally consistent,
complete, attributable, and safe before any future executor boundary.

This layer is READ-ONLY. It does not execute actions, invoke executors,
send messages, write CRM, or claim application/payment/enrollment completion.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

INTEGRITY_PASS = "HANDOFF_INTEGRITY_PASS"
INTEGRITY_CLARIFICATION = "HANDOFF_INTEGRITY_CLARIFICATION"
INTEGRITY_REVIEW = "HANDOFF_INTEGRITY_REVIEW"
INTEGRITY_BLOCKED = "HANDOFF_INTEGRITY_BLOCKED"
INTEGRITY_UNKNOWN = "HANDOFF_INTEGRITY_UNKNOWN"

DECISION_ACCEPT_HANDOFF = "ACCEPT_HANDOFF_BOUNDARY"
DECISION_CLARIFY = "CLARIFY_HANDOFF"
DECISION_HUMAN_REVIEW = "HUMAN_REVIEW_HANDOFF"
DECISION_BLOCK = "BLOCK_HANDOFF"
DECISION_OBTAIN_STATE = "OBTAIN_VERIFIED_HANDOFF_STATE"

@dataclass
class IntegrityCheck:
    name: str
    passed: bool
    source: str
    detail: str = ""

@dataclass
class HandoffIntegrityResult:
    status: str
    decision: str
    action: str
    lead_id: Optional[str]
    course_ids: List[str]
    authorization_state: str
    handoff_created: bool
    integrity_verified: bool
    rationale: str
    checks: List[IntegrityCheck] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    executor_invocation_allowed: bool = False
    execution_authorized: bool = False
    application_occurred: bool = False
    payment_occurred: bool = False
    enrollment_occurred: bool = False
    crm_write_allowed: bool = False
    message_send_allowed: bool = False
    external_action_allowed: bool = False
    provenance: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class HandoffIntegrityRuntimeResult:
    result: HandoffIntegrityResult
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
    if isinstance(value, dict) and "handoff" in value:
        return value["handoff"]
    return value

def _claims():
    return [
        "Integrity verification does not mean the admission action was executed.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def _check(checks, name, passed, source, detail=""):
    checks.append(IntegrityCheck(name, bool(passed), source, detail))

def build_handoff_integrity(handoff_result, *, readiness_result=None, crm_snapshot=None, authorization=None):
    h = _obj(handoff_result)
    checks = []
    missing = list(_get(h, "missing_requirements", []) or [])
    conflicts = []
    errors = list(_get(h, "errors", []) or [])

    action = _get(h, "action")
    lead_id = _get(h, "lead_id")
    course_ids = list(_get(h, "course_ids", []) or [])
    auth = str(_get(h, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()
    status = str(_get(h, "status", "") or "").upper()
    created = bool(_get(h, "handoff_created", False))

    _check(checks, "status_present", bool(status), "HANDOFF")
    _check(checks, "action_present", bool(action) and action != "NONE", "HANDOFF")
    _check(checks, "lead_present", bool(lead_id), "HANDOFF")
    _check(checks, "course_present", bool(course_ids), "HANDOFF")
    _check(checks, "authorization_present", bool(auth), "HANDOFF")

    if readiness_result is not None:
        r = _obj(readiness_result)
        r_lead = _get(r, "lead_id")
        r_courses = list(_get(r, "course_ids", []) or [])
        r_action = _get(r, "proposed_action")
        r_auth = str(_get(r, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()
        _check(checks, "readiness_lead_match", lead_id == r_lead, "ACTION_READINESS")
        _check(checks, "readiness_course_match", course_ids == r_courses, "ACTION_READINESS")
        _check(checks, "readiness_action_match", action == r_action, "ACTION_READINESS")
        _check(checks, "readiness_auth_match", auth == r_auth, "ACTION_READINESS")
        if lead_id != r_lead:
            conflicts.append("lead_id differs from action-readiness state")
        if course_ids != r_courses:
            conflicts.append("course_ids differ from action-readiness state")
        if action != r_action:
            conflicts.append("action differs from action-readiness state")
        if auth != r_auth:
            conflicts.append("authorization differs from action-readiness state")

    if crm_snapshot is not None:
        c = _obj(crm_snapshot) or {}
        c_lead = _get(c, "lead_id")
        c_course = _get(c, "course_id")
        c_stage = _get(c, "stage")
        _check(checks, "crm_lead_match", lead_id == c_lead, "CRM_READ")
        _check(checks, "crm_course_match", (not c_course) or (course_ids == [c_course]), "CRM_READ")
        if lead_id != c_lead:
            conflicts.append("lead_id differs from CRM")
        if c_course and course_ids != [c_course]:
            conflicts.append("course differs from CRM")
        if not c_stage:
            missing.append("verified CRM stage")

    if authorization is not None:
        a = _obj(authorization)
        a_state = str(_get(a, "authorization_state", _get(a, "status", "UNKNOWN")) or "UNKNOWN").upper()
        _check(checks, "authorization_source_match", auth == a_state, "AUTHORIZATION")
        if auth != a_state:
            conflicts.append("authorization differs from authorization source")

    # A handoff can only be accepted if the originating handoff says it is ready,
    # created, and explicitly authorized. Integrity verification never grants authority.
    upstream_ready = status == "HANDOFF_READY"
    core_checks_pass = all(c.passed for c in checks)
    auth_ok = auth == "GRANTED"

    if conflicts:
        final_status = INTEGRITY_REVIEW
        decision = DECISION_HUMAN_REVIEW
        rationale = "Material state conflicts were detected; human review is required."
        verified = False; created_out = False; human = True
    elif not status:
        final_status = INTEGRITY_UNKNOWN
        decision = DECISION_OBTAIN_STATE
        rationale = "Handoff state is unavailable."
        verified = False; created_out = False; human = False
    elif status == "HANDOFF_REVIEW":
        final_status = INTEGRITY_REVIEW
        decision = DECISION_HUMAN_REVIEW
        rationale = "The upstream handoff is already in human-review state."
        verified = False; created_out = False; human = True
    elif status == "HANDOFF_BLOCKED":
        final_status = INTEGRITY_BLOCKED
        decision = DECISION_BLOCK
        rationale = "The upstream handoff is blocked."
        verified = False; created_out = False; human = False
    elif status == "HANDOFF_UNKNOWN":
        final_status = INTEGRITY_UNKNOWN
        decision = DECISION_OBTAIN_STATE
        rationale = "The upstream handoff state is unknown; verified state must be obtained."
        verified = False; created_out = False; human = False
    elif status == "HANDOFF_CLARIFICATION":
        final_status = INTEGRITY_CLARIFICATION
        decision = DECISION_CLARIFY
        rationale = "The upstream handoff requires clarification."
        verified = False; created_out = False; human = False
    elif status == "HANDOFF_READY":
        if not core_checks_pass:
            final_status = INTEGRITY_REVIEW
            decision = DECISION_HUMAN_REVIEW
            rationale = "One or more integrity checks failed."
            human = True
        elif not auth_ok:
            final_status = INTEGRITY_BLOCKED
            decision = DECISION_BLOCK
            rationale = "Granted authorization is required; integrity verification cannot grant it."
            human = False
        elif missing:
            final_status = INTEGRITY_CLARIFICATION
            decision = DECISION_CLARIFY
            rationale = "Required verified handoff information is missing."
            human = False
        elif not created:
            final_status = INTEGRITY_CLARIFICATION
            decision = DECISION_CLARIFY
            rationale = "A ready handoff must be explicitly marked as created by the upstream boundary."
            human = False
        else:
            final_status = INTEGRITY_PASS
            decision = DECISION_ACCEPT_HANDOFF
            rationale = "The handoff is internally consistent and may be passed as a verified boundary package to a separate future executor."
            human = False
        verified = final_status == INTEGRITY_PASS
        created_out = verified
    else:
        final_status = INTEGRITY_UNKNOWN
        decision = DECISION_OBTAIN_STATE
        rationale = "The handoff state is unavailable or unsupported."
        verified = False; created_out = False; human = False

    provenance = ["HANDOFF"]
    if readiness_result is not None: provenance.append("ACTION_READINESS")
    if crm_snapshot is not None: provenance.append("CRM_READ")
    if authorization is not None: provenance.append("AUTHORIZATION")

    return HandoffIntegrityRuntimeResult(
        result=HandoffIntegrityResult(
            status=final_status,
            decision=decision,
            action=action,
            lead_id=lead_id,
            course_ids=course_ids,
            authorization_state=auth,
            handoff_created=created_out,
            integrity_verified=verified,
            rationale=rationale,
            checks=checks,
            missing_requirements=list(dict.fromkeys(missing)),
            conflicts=list(dict.fromkeys(conflicts)),
            human_handoff_required=human,
            executor_invocation_allowed=False,
            execution_authorized=False,
            application_occurred=False,
            payment_occurred=False,
            enrollment_occurred=False,
            crm_write_allowed=False,
            message_send_allowed=False,
            external_action_allowed=False,
            provenance=list(dict.fromkeys(provenance)),
            prohibited_claims=_claims(),
            errors=errors,
        )
    )

def run_handoff_integrity(*args, **kwargs):
    return build_handoff_integrity(*args, **kwargs)

def validate_handoff_integrity(runtime):
    errors = []
    r = runtime.result
    valid_status = {
        INTEGRITY_PASS, INTEGRITY_CLARIFICATION, INTEGRITY_REVIEW,
        INTEGRITY_BLOCKED, INTEGRITY_UNKNOWN
    }
    valid_decisions = {
        DECISION_ACCEPT_HANDOFF, DECISION_CLARIFY, DECISION_HUMAN_REVIEW,
        DECISION_BLOCK, DECISION_OBTAIN_STATE
    }
    if r.status not in valid_status:
        errors.append("Invalid integrity status.")
    if r.decision not in valid_decisions:
        errors.append("Invalid integrity decision.")
    if r.status == INTEGRITY_PASS:
        if not r.integrity_verified or not r.handoff_created:
            errors.append("Pass requires verified created handoff.")
        if r.decision != DECISION_ACCEPT_HANDOFF:
            errors.append("Pass requires accept-handoff decision.")
        if r.authorization_state != "GRANTED":
            errors.append("Pass requires granted authorization.")
    if r.status == INTEGRITY_REVIEW and not r.human_handoff_required:
        errors.append("Review requires human handoff.")
    if r.status != INTEGRITY_PASS and r.handoff_created:
        errors.append("Only a passing integrity result may retain created state.")
    if r.executor_invocation_allowed or r.execution_authorized:
        errors.append("Executor and execution must remain disabled.")
    if r.application_occurred or r.payment_occurred or r.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if r.crm_write_allowed or r.message_send_allowed or r.external_action_allowed:
        errors.append("Side effects must remain disabled.")
    for c in r.checks:
        if not c.name or not c.source:
            errors.append("Integrity checks require name and source.")
    for key in (
        "execution_enabled","messaging_enabled","external_actions_enabled",
        "crm_writes_enabled","executor_invocation_enabled"
    ):
        if runtime.safety.get(key) is not False:
            errors.append(f"{key} must remain False.")
    if runtime.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def handoff_integrity_to_dict(runtime):
    r = runtime.result
    return {
        "result": {
            "status": r.status,
            "decision": r.decision,
            "action": r.action,
            "lead_id": r.lead_id,
            "course_ids": list(r.course_ids),
            "authorization_state": r.authorization_state,
            "handoff_created": r.handoff_created,
            "integrity_verified": r.integrity_verified,
            "rationale": r.rationale,
            "checks": [
                {"name": c.name, "passed": c.passed, "source": c.source, "detail": c.detail}
                for c in r.checks
            ],
            "missing_requirements": list(r.missing_requirements),
            "conflicts": list(r.conflicts),
            "human_handoff_required": r.human_handoff_required,
            "executor_invocation_allowed": r.executor_invocation_allowed,
            "execution_authorized": r.execution_authorized,
            "application_occurred": r.application_occurred,
            "payment_occurred": r.payment_occurred,
            "enrollment_occurred": r.enrollment_occurred,
            "crm_write_allowed": r.crm_write_allowed,
            "message_send_allowed": r.message_send_allowed,
            "external_action_allowed": r.external_action_allowed,
            "provenance": list(r.provenance),
            "prohibited_claims": list(r.prohibited_claims),
            "errors": list(r.errors),
        },
        "safety": dict(runtime.safety),
    }

def validate_serialized_handoff_integrity(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
        return ["Serialized result must contain result."]
    r = data["result"]
    for k in ("status","decision","action","authorization_state",
              "handoff_created","integrity_verified","checks"):
        if k not in r:
            errors.append(f"Missing serialized field: {k}")
    if r.get("executor_invocation_allowed") is not False:
        errors.append("Serialized executor invocation must be False.")
    if r.get("execution_authorized") is not False:
        errors.append("Serialized execution authorization must be False.")
    return errors
