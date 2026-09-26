
"""
Sayyed EdVantage AI Agent — AI Core 30
Admission Orchestration Handoff → Unified Agent Boundary Closure Contract

Final read-only closure layer for the current admission-action architecture.
It verifies that the Core-29 orchestration handoff can be safely exposed to a
future executor boundary without granting execution authority.

No execution, executor invocation, CRM writes, messaging, or external actions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

CLOSURE_READY = "AGENT_BOUNDARY_READY"
CLOSURE_CLARIFICATION = "AGENT_BOUNDARY_CLARIFICATION"
CLOSURE_REVIEW = "AGENT_BOUNDARY_REVIEW"
CLOSURE_BLOCKED = "AGENT_BOUNDARY_BLOCKED"
CLOSURE_UNKNOWN = "AGENT_BOUNDARY_UNKNOWN"

DECISION_EXPOSE = "EXPOSE_VERIFIED_HANDOFF"
DECISION_CLARIFY = "CLARIFY_BEFORE_BOUNDARY"
DECISION_REVIEW = "HUMAN_REVIEW_BEFORE_BOUNDARY"
DECISION_BLOCK = "BLOCK_BOUNDARY"
DECISION_OBTAIN = "OBTAIN_VERIFIED_STATE"

@dataclass
class ClosureCheckpoint:
    sequence: int
    checkpoint: str
    source: str
    passed: bool
    usable: bool
    detail: str = ""

@dataclass
class UnifiedAgentBoundary:
    status: str
    decision: str
    action: Optional[str]
    lead_id: Optional[str]
    course_ids: List[str]
    orchestration_status: str
    orchestration_handoff_created: bool
    authorization_state: str
    evidence_count: int
    usable_evidence_count: int
    rationale: str
    checkpoints: List[ClosureCheckpoint] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    boundary_ready: bool = False
    future_executor_input_ready: bool = False

    # Explicitly NOT execution authority.
    execution_authorized: bool = False
    executor_invocation_allowed: bool = False
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False

    application_occurred: bool = False
    payment_occurred: bool = False
    enrollment_occurred: bool = False

    provenance: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class UnifiedBoundaryRuntime:
    boundary: UnifiedAgentBoundary
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

def _unwrap(obj):
    if isinstance(obj, dict):
        for key in ("handoff", "boundary", "runtime"):
            if key in obj and isinstance(obj[key], (dict, object)):
                return obj[key]
    return obj

def _claims():
    return [
        "Boundary readiness is not execution authorization.",
        "A future executor must perform its own authorization and execution checks.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This closure layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def build_unified_agent_boundary(orchestration_result, *,
                                 evidence_package_result=None,
                                 audit_result=None,
                                 final_boundary_result=None):
    o = _unwrap(orchestration_result)
    orch_status = str(_get(o, "status", "") or "").upper()
    action = _get(o, "action")
    lead_id = _get(o, "lead_id")
    courses = list(_get(o, "course_ids", []) or [])
    auth = str(_get(o, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()
    created = bool(_get(o, "orchestration_handoff_created", False))
    evidence_count = int(_get(o, "evidence_count", 0) or 0)
    usable_count = int(_get(o, "usable_evidence_count", 0) or 0)
    failed = list(_get(o, "failed_checks", []) or [])
    conflicts = list(_get(o, "conflicts", []) or [])
    missing = list(_get(o, "missing_requirements", []) or [])
    errors = list(_get(o, "errors", []) or [])
    checkpoints = []

    for idx, e in enumerate(_get(o, "evidence", []) or [], 1):
        checkpoints.append(ClosureCheckpoint(
            sequence=int(_get(e, "sequence", idx)),
            checkpoint=_get(e, "checkpoint", "unknown"),
            source=_get(e, "source", "ORCHESTRATION"),
            passed=bool(_get(e, "passed", False)),
            usable=bool(_get(e, "usable", False)),
            detail=_get(e, "detail", ""),
        ))
    checkpoints.sort(key=lambda x: x.sequence)

    # Cross-layer identity and status verification.
    if evidence_package_result is not None:
        p = _unwrap(evidence_package_result)
        if str(_get(p, "status", "")).upper() != "EVIDENCE_PACKAGE_ACCEPTED":
            conflicts.append("evidence package is not accepted")
        pl = _get(p, "lead_id")
        pc = list(_get(p, "course_ids", []) or [])
        pa = str(_get(p, "authorization_state", "UNKNOWN") or "UNKNOWN").upper()
        if lead_id is not None and pl is not None and lead_id != pl:
            conflicts.append("lead_id differs from evidence package")
        if pc and pc != courses:
            conflicts.append("course_ids differ from evidence package")
        if pa != "UNKNOWN" and pa != auth:
            conflicts.append("authorization differs from evidence package")

    if audit_result is not None:
        a = _unwrap(audit_result)
        if str(_get(a, "status", "")).upper() != "AUDIT_ACCEPTED":
            conflicts.append("audit is not accepted")

    if final_boundary_result is not None:
        f = _unwrap(final_boundary_result)
        if str(_get(f, "status", "")).upper() != "FINAL_HANDOFF_ACCEPTED":
            conflicts.append("final boundary is not accepted")

    conflicts = list(dict.fromkeys(conflicts))
    failed = list(dict.fromkeys(failed))

    if conflicts:
        status, decision, rationale = CLOSURE_REVIEW, DECISION_REVIEW, \
            "Material cross-layer conflict requires human review before boundary exposure."
        ready, future, human = False, False, True
    elif not orch_status:
        status, decision, rationale = CLOSURE_UNKNOWN, DECISION_OBTAIN, \
            "Orchestration state is unavailable."
        ready, future, human = False, False, False
    elif orch_status == "ORCHESTRATION_HANDOFF_REVIEW":
        status, decision, rationale = CLOSURE_REVIEW, DECISION_REVIEW, \
            "The orchestration handoff requires human review."
        ready, future, human = False, False, True
    elif orch_status == "ORCHESTRATION_HANDOFF_BLOCKED":
        status, decision, rationale = CLOSURE_BLOCKED, DECISION_BLOCK, \
            "The orchestration handoff is blocked."
        ready, future, human = False, False, False
    elif orch_status == "ORCHESTRATION_HANDOFF_CLARIFICATION":
        status, decision, rationale = CLOSURE_CLARIFICATION, DECISION_CLARIFY, \
            "The orchestration handoff requires clarification."
        ready, future, human = False, False, False
    elif orch_status == "ORCHESTRATION_HANDOFF_UNKNOWN":
        status, decision, rationale = CLOSURE_UNKNOWN, DECISION_OBTAIN, \
            "Verified orchestration state is unknown."
        ready, future, human = False, False, False
    elif failed:
        status, decision, rationale = CLOSURE_REVIEW, DECISION_REVIEW, \
            "Failed upstream checks prevent safe boundary exposure."
        ready, future, human = False, False, True
    elif not created or auth != "GRANTED" or not lead_id or not courses:
        status, decision, rationale = CLOSURE_CLARIFICATION, DECISION_CLARIFY, \
            "Verified orchestration handoff, authorization, lead, and course identity are required."
        ready, future, human = False, False, False
    elif evidence_count <= 0 or usable_count <= 0:
        status, decision, rationale = CLOSURE_CLARIFICATION, DECISION_CLARIFY, \
            "Attributable usable evidence is required before boundary exposure."
        ready, future, human = False, False, False
    else:
        status, decision, rationale = CLOSURE_READY, DECISION_EXPOSE, \
            "The verified orchestration handoff is ready to be passed to a future executor boundary; execution remains disabled."
        ready, future, human = True, True, False

    provenance = ["ORCHESTRATION_HANDOFF"]
    if evidence_package_result is not None:
        provenance.append("EVIDENCE_PACKAGE")
    if audit_result is not None:
        provenance.append("AUDIT")
    if final_boundary_result is not None:
        provenance.append("FINAL_BOUNDARY")

    b = UnifiedAgentBoundary(
        status=status, decision=decision, action=action, lead_id=lead_id,
        course_ids=courses, orchestration_status=orch_status,
        orchestration_handoff_created=created, authorization_state=auth,
        evidence_count=evidence_count, usable_evidence_count=usable_count,
        rationale=rationale, checkpoints=checkpoints,
        failed_checks=failed, conflicts=conflicts,
        missing_requirements=missing, human_handoff_required=human,
        boundary_ready=ready, future_executor_input_ready=future,
        execution_authorized=False, executor_invocation_allowed=False,
        execution_enabled=False, messaging_enabled=False,
        external_actions_enabled=False, crm_writes_enabled=False,
        application_occurred=False, payment_occurred=False,
        enrollment_occurred=False,
        provenance=list(dict.fromkeys(provenance)),
        prohibited_claims=_claims(), errors=errors
    )
    return UnifiedBoundaryRuntime(boundary=b)

def run_unified_agent_boundary(*args, **kwargs):
    return build_unified_agent_boundary(*args, **kwargs)

def validate_unified_agent_boundary(runtime):
    errors=[]
    b=runtime.boundary
    valid_status={CLOSURE_READY,CLOSURE_CLARIFICATION,CLOSURE_REVIEW,CLOSURE_BLOCKED,CLOSURE_UNKNOWN}
    valid_dec={DECISION_EXPOSE,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN}
    if b.status not in valid_status: errors.append("Invalid closure status.")
    if b.decision not in valid_dec: errors.append("Invalid closure decision.")
    if b.evidence_count != len(b.checkpoints): errors.append("Evidence count mismatch.")
    if b.usable_evidence_count != sum(1 for x in b.checkpoints if x.usable):
        errors.append("Usable evidence count mismatch.")
    if b.status==CLOSURE_READY:
        if not b.boundary_ready or not b.future_executor_input_ready:
            errors.append("Ready boundary must be marked ready.")
        if not b.orchestration_handoff_created or b.authorization_state!="GRANTED":
            errors.append("Ready boundary requires created handoff and granted authorization.")
        if not b.lead_id or not b.course_ids:
            errors.append("Ready boundary requires lead and course identity.")
        if b.conflicts or b.failed_checks:
            errors.append("Ready boundary cannot contain conflicts or failed checks.")
        if b.evidence_count<=0 or b.usable_evidence_count<=0:
            errors.append("Ready boundary requires usable evidence.")
    if b.status==CLOSURE_REVIEW and not b.human_handoff_required:
        errors.append("Review requires human handoff.")
    if b.status!=CLOSURE_READY and (b.boundary_ready or b.future_executor_input_ready):
        errors.append("Only ready boundary may expose readiness.")
    if b.execution_authorized or b.executor_invocation_allowed:
        errors.append("Execution authority must remain false.")
    if b.execution_enabled or b.messaging_enabled or b.external_actions_enabled or b.crm_writes_enabled:
        errors.append("Side effects must remain disabled.")
    if b.application_occurred or b.payment_occurred or b.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if not b.provenance: errors.append("Provenance is required.")
    for x in b.checkpoints:
        if x.sequence<1 or not x.checkpoint or not x.source:
            errors.append("Invalid checkpoint.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled",
              "crm_writes_enabled","executor_invocation_enabled"):
        if runtime.safety.get(k) is not False:
            errors.append(f"{k} must remain False.")
    if runtime.safety.get("no_invention") is not True:
        errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True:
        errors.append("fail_closed must remain True.")
    return errors

def unified_agent_boundary_to_dict(runtime):
    b=runtime.boundary
    return {"boundary":{
        "status":b.status,"decision":b.decision,"action":b.action,
        "lead_id":b.lead_id,"course_ids":list(b.course_ids),
        "orchestration_status":b.orchestration_status,
        "orchestration_handoff_created":b.orchestration_handoff_created,
        "authorization_state":b.authorization_state,
        "evidence_count":b.evidence_count,
        "usable_evidence_count":b.usable_evidence_count,
        "rationale":b.rationale,
        "checkpoints":[{"sequence":x.sequence,"checkpoint":x.checkpoint,
         "source":x.source,"passed":x.passed,"usable":x.usable,"detail":x.detail}
         for x in b.checkpoints],
        "failed_checks":list(b.failed_checks),"conflicts":list(b.conflicts),
        "missing_requirements":list(b.missing_requirements),
        "human_handoff_required":b.human_handoff_required,
        "boundary_ready":b.boundary_ready,
        "future_executor_input_ready":b.future_executor_input_ready,
        "execution_authorized":b.execution_authorized,
        "executor_invocation_allowed":b.executor_invocation_allowed,
        "execution_enabled":b.execution_enabled,
        "messaging_enabled":b.messaging_enabled,
        "external_actions_enabled":b.external_actions_enabled,
        "crm_writes_enabled":b.crm_writes_enabled,
        "application_occurred":b.application_occurred,
        "payment_occurred":b.payment_occurred,
        "enrollment_occurred":b.enrollment_occurred,
        "provenance":list(b.provenance),
        "prohibited_claims":list(b.prohibited_claims),
        "errors":list(b.errors)}, "safety":dict(runtime.safety)}

def validate_serialized_unified_agent_boundary(data):
    if not isinstance(data,dict) or not isinstance(data.get("boundary"),dict):
        return ["Serialized result must contain boundary."]
    b=data["boundary"]; errors=[]
    for k in ("status","decision","orchestration_status","authorization_state",
              "evidence_count","usable_evidence_count","checkpoints"):
        if k not in b: errors.append("Missing serialized field: "+k)
    for k in ("execution_authorized","executor_invocation_allowed",
              "execution_enabled","messaging_enabled","external_actions_enabled",
              "crm_writes_enabled"):
        if b.get(k) is not False: errors.append("Serialized "+k+" must be False.")
    return errors
