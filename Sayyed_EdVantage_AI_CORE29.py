
"""
Sayyed EdVantage AI Agent — AI Core 29
Admission Evidence Package → Orchestration Handoff Contract

Converts the verified Core-28 evidence package into a compact downstream
orchestration contract. It is a boundary adapter only: no execution,
executor invocation, CRM writes, messaging, or external actions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

ORCH_READY = "ORCHESTRATION_HANDOFF_READY"
ORCH_CLARIFICATION = "ORCHESTRATION_HANDOFF_CLARIFICATION"
ORCH_REVIEW = "ORCHESTRATION_HANDOFF_REVIEW"
ORCH_BLOCKED = "ORCHESTRATION_HANDOFF_BLOCKED"
ORCH_UNKNOWN = "ORCHESTRATION_HANDOFF_UNKNOWN"

DECISION_READY = "READY_FOR_ORCHESTRATION"
DECISION_CLARIFY = "CLARIFY_BEFORE_ORCHESTRATION"
DECISION_REVIEW = "HUMAN_REVIEW_BEFORE_ORCHESTRATION"
DECISION_BLOCK = "BLOCK_ORCHESTRATION"
DECISION_OBTAIN = "OBTAIN_VERIFIED_EVIDENCE"

@dataclass
class OrchestrationEvidence:
    sequence: int
    checkpoint: str
    source: str
    passed: bool
    usable: bool
    detail: str = ""

@dataclass
class AdmissionOrchestrationHandoff:
    status: str
    decision: str
    action: Optional[str]
    lead_id: Optional[str]
    course_ids: List[str]
    package_status: str
    package_accepted: bool
    authorization_state: str
    evidence_count: int
    usable_evidence_count: int
    rationale: str
    evidence: List[OrchestrationEvidence] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    orchestration_handoff_created: bool = False
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
class OrchestrationRuntimeResult:
    handoff: AdmissionOrchestrationHandoff
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
    if isinstance(value, dict) and "package" in value:
        return value["package"]
    return value

def _claims():
    return [
        "An orchestration handoff does not mean an admission action was executed.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def build_orchestration_handoff(package_result, *, audit_result=None,
                                final_boundary_result=None,
                                integrity_result=None):
    p = _obj(package_result)
    package_status = str(_get(p, "status", "") or "").upper()
    action = _get(p, "action")
    lead_id = _get(p, "lead_id")
    courses = list(_get(p, "course_ids", []) or [])
    auth = str(_get(p, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()
    accepted = package_status == "EVIDENCE_PACKAGE_ACCEPTED"
    package_complete = bool(_get(p, "audit_complete", False))
    final_verified = bool(_get(p, "final_boundary_verified", False))
    failed = list(_get(p, "failed_checks", []) or [])
    conflicts = list(_get(p, "conflicts", []) or [])
    missing = list(_get(p, "missing_requirements", []) or [])
    errors = list(_get(p, "errors", []) or [])

    evidence = []
    for idx, e in enumerate(_get(p, "evidence", []) or [], 1):
        evidence.append(OrchestrationEvidence(
            sequence=int(_get(e, "sequence", idx)),
            checkpoint=_get(e, "checkpoint", "unknown"),
            source=_get(e, "source", "EVIDENCE_PACKAGE"),
            passed=bool(_get(e, "passed", False)),
            usable=bool(_get(e, "usable", False)),
            detail=_get(e, "detail", ""),
        ))
    evidence.sort(key=lambda x: x.sequence)

    if audit_result is not None:
        a = _obj(audit_result)
        if str(_get(a, "status", "")).upper() != "AUDIT_ACCEPTED":
            conflicts.append("audit source is not accepted")
        if lead_id is not None and _get(a, "lead_id") is not None and lead_id != _get(a, "lead_id"):
            conflicts.append("lead_id differs from audit")
        ac = list(_get(a, "course_ids", []) or [])
        if ac and ac != courses:
            conflicts.append("course_ids differ from audit")

    if final_boundary_result is not None:
        f = _obj(final_boundary_result)
        if str(_get(f, "status", "")).upper() != "FINAL_HANDOFF_ACCEPTED":
            conflicts.append("final boundary source is not accepted")

    if integrity_result is not None:
        i = _obj(integrity_result)
        if str(_get(i, "status", "")).upper() != "HANDOFF_INTEGRITY_PASS":
            conflicts.append("integrity source is not passing")

    conflicts = list(dict.fromkeys(conflicts))
    failed = list(dict.fromkeys(failed))

    if conflicts:
        status, decision = ORCH_REVIEW, DECISION_REVIEW
        rationale = "Material upstream conflicts require human review before orchestration."
        created, human = False, True
    elif not package_status:
        status, decision = ORCH_UNKNOWN, DECISION_OBTAIN
        rationale = "Evidence-package state is unavailable."
        created, human = False, False
    elif package_status == "EVIDENCE_PACKAGE_REVIEW":
        status, decision = ORCH_REVIEW, DECISION_REVIEW
        rationale = "The evidence package requires human review."
        created, human = False, True
    elif package_status == "EVIDENCE_PACKAGE_BLOCKED":
        status, decision = ORCH_BLOCKED, DECISION_BLOCK
        rationale = "The evidence package is blocked."
        created, human = False, False
    elif package_status == "EVIDENCE_PACKAGE_CLARIFICATION":
        status, decision = ORCH_CLARIFICATION, DECISION_CLARIFY
        rationale = "The evidence package requires clarification."
        created, human = False, False
    elif package_status == "EVIDENCE_PACKAGE_UNKNOWN":
        status, decision = ORCH_UNKNOWN, DECISION_OBTAIN
        rationale = "Verified evidence state is unknown."
        created, human = False, False
    elif not accepted or not package_complete or not final_verified or auth != "GRANTED":
        status, decision = ORCH_CLARIFICATION, DECISION_CLARIFY
        rationale = "The evidence package is not sufficiently verified for orchestration."
        created, human = False, False
    elif failed:
        status, decision = ORCH_REVIEW, DECISION_REVIEW
        rationale = "Failed evidence checkpoints prevent safe orchestration."
        created, human = False, True
    elif not lead_id or not courses:
        status, decision = ORCH_CLARIFICATION, DECISION_CLARIFY
        rationale = "Verified lead and course identity are required."
        created, human = False, False
    else:
        status, decision = ORCH_READY, DECISION_READY
        rationale = "The evidence package is verified and can be passed to a separate orchestration layer."
        created, human = True, False

    provenance = ["EVIDENCE_PACKAGE"]
    if audit_result is not None:
        provenance.append("AUDIT")
    if final_boundary_result is not None:
        provenance.append("FINAL_BOUNDARY")
    if integrity_result is not None:
        provenance.append("HANDOFF_INTEGRITY")

    return OrchestrationRuntimeResult(
        handoff=AdmissionOrchestrationHandoff(
            status=status,
            decision=decision,
            action=action,
            lead_id=lead_id,
            course_ids=courses,
            package_status=package_status,
            package_accepted=accepted,
            authorization_state=auth,
            evidence_count=len(evidence),
            usable_evidence_count=sum(1 for e in evidence if e.usable),
            rationale=rationale,
            evidence=evidence,
            failed_checks=failed,
            conflicts=conflicts,
            missing_requirements=missing,
            human_handoff_required=human,
            orchestration_handoff_created=created,
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

def run_orchestration_handoff(*args, **kwargs):
    return build_orchestration_handoff(*args, **kwargs)

def validate_orchestration_handoff(runtime):
    errors = []
    h = runtime.handoff
    valid_status = {ORCH_READY, ORCH_CLARIFICATION, ORCH_REVIEW, ORCH_BLOCKED, ORCH_UNKNOWN}
    valid_decision = {DECISION_READY, DECISION_CLARIFY, DECISION_REVIEW, DECISION_BLOCK, DECISION_OBTAIN}
    if h.status not in valid_status:
        errors.append("Invalid orchestration status.")
    if h.decision not in valid_decision:
        errors.append("Invalid orchestration decision.")
    if h.evidence_count != len(h.evidence):
        errors.append("Evidence count mismatch.")
    if h.usable_evidence_count != sum(1 for e in h.evidence if e.usable):
        errors.append("Usable evidence count mismatch.")
    if h.status == ORCH_READY:
        if not h.orchestration_handoff_created:
            errors.append("Ready orchestration handoff must be created.")
        if not h.package_accepted or not h.authorization_state == "GRANTED":
            errors.append("Ready orchestration handoff requires accepted package and granted authorization.")
        if h.conflicts or h.failed_checks:
            errors.append("Ready orchestration handoff cannot contain conflicts or failed checks.")
        if not h.lead_id or not h.course_ids:
            errors.append("Ready orchestration handoff requires lead and course identity.")
    if h.status == ORCH_REVIEW and not h.human_handoff_required:
        errors.append("Review requires human handoff.")
    if h.status != ORCH_READY and h.orchestration_handoff_created:
        errors.append("Only ready orchestration handoff may be created.")
    if h.executor_invocation_allowed or h.execution_authorized:
        errors.append("Execution must remain disabled.")
    if h.application_occurred or h.payment_occurred or h.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if h.crm_write_allowed or h.message_send_allowed or h.external_action_allowed:
        errors.append("Side effects must remain disabled.")
    for e in h.evidence:
        if e.sequence < 1 or not e.checkpoint or not e.source:
            errors.append("Invalid evidence item.")
    for k in ("execution_enabled", "messaging_enabled", "external_actions_enabled",
              "crm_writes_enabled", "executor_invocation_enabled"):
        if runtime.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if runtime.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def orchestration_handoff_to_dict(runtime):
    h = runtime.handoff
    return {
        "handoff": {
            "status": h.status,
            "decision": h.decision,
            "action": h.action,
            "lead_id": h.lead_id,
            "course_ids": list(h.course_ids),
            "package_status": h.package_status,
            "package_accepted": h.package_accepted,
            "authorization_state": h.authorization_state,
            "evidence_count": h.evidence_count,
            "usable_evidence_count": h.usable_evidence_count,
            "rationale": h.rationale,
            "evidence": [
                {"sequence": e.sequence, "checkpoint": e.checkpoint, "source": e.source,
                 "passed": e.passed, "usable": e.usable, "detail": e.detail}
                for e in h.evidence
            ],
            "failed_checks": list(h.failed_checks),
            "conflicts": list(h.conflicts),
            "missing_requirements": list(h.missing_requirements),
            "human_handoff_required": h.human_handoff_required,
            "orchestration_handoff_created": h.orchestration_handoff_created,
            "executor_invocation_allowed": h.executor_invocation_allowed,
            "execution_authorized": h.execution_authorized,
            "application_occurred": h.application_occurred,
            "payment_occurred": h.payment_occurred,
            "enrollment_occurred": h.enrollment_occurred,
            "crm_write_allowed": h.crm_write_allowed,
            "message_send_allowed": h.message_send_allowed,
            "external_action_allowed": h.external_action_allowed,
            "provenance": list(h.provenance),
            "prohibited_claims": list(h.prohibited_claims),
            "errors": list(h.errors),
        },
        "safety": dict(runtime.safety),
    }

def validate_serialized_orchestration_handoff(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("handoff"), dict):
        return ["Serialized result must contain handoff."]
    h = data["handoff"]
    for k in ("status", "decision", "action", "authorization_state",
              "evidence_count", "usable_evidence_count", "evidence"):
        if k not in h:
            errors.append(f"Missing serialized field: {k}")
    for k in ("executor_invocation_allowed", "execution_authorized",
              "crm_write_allowed", "message_send_allowed", "external_action_allowed"):
        if h.get(k) is not False:
            errors.append(f"Serialized {k} must be False.")
    return errors
