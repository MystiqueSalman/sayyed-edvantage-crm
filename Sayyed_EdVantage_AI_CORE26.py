
"""
Sayyed EdVantage AI Agent — AI Core 26
Admission Action Boundary Finalization Contract

Consumes Core-25 handoff-integrity output and produces a final, explicit
boundary state for a future executor. This is the last read-only gate in this
mini-chain: it may finalize a handoff as ACCEPTED, CLARIFICATION, REVIEW,
BLOCKED, or UNKNOWN, but it never executes the action.

No CRM writes, no message sends, no external actions, no executor invocation,
and no claims that application/payment/enrollment occurred.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

FINAL_ACCEPTED = "FINAL_HANDOFF_ACCEPTED"
FINAL_CLARIFICATION = "FINAL_HANDOFF_CLARIFICATION"
FINAL_REVIEW = "FINAL_HANDOFF_REVIEW"
FINAL_BLOCKED = "FINAL_HANDOFF_BLOCKED"
FINAL_UNKNOWN = "FINAL_HANDOFF_UNKNOWN"

DECISION_ACCEPT = "ACCEPT_FINAL_BOUNDARY"
DECISION_CLARIFY = "CLARIFY_FINAL_BOUNDARY"
DECISION_REVIEW = "HUMAN_REVIEW_FINAL_BOUNDARY"
DECISION_BLOCK = "BLOCK_FINAL_BOUNDARY"
DECISION_OBTAIN = "OBTAIN_VERIFIED_STATE"

@dataclass
class FinalizationCheck:
    name: str
    passed: bool
    source: str
    detail: str = ""

@dataclass
class FinalizedAdmissionBoundary:
    status: str
    decision: str
    action: str
    lead_id: Optional[str]
    course_ids: List[str]
    authorization_state: str
    integrity_status: str
    integrity_verified: bool
    final_boundary_verified: bool
    rationale: str
    checks: List[FinalizationCheck] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
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
    provenance: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class FinalizationRuntimeResult:
    boundary: FinalizedAdmissionBoundary
    safety: Dict[str, bool] = field(default_factory=lambda: {
        "execution_enabled": False,
        "messaging_enabled": False,
        "external_actions_enabled": False,
        "crm_writes_enabled": False,
        "executor_invocation_enabled": False,
        "no_invention": True,
        "fail_closed": True,
    })

def _get(obj,key,default=None):
    if isinstance(obj,dict): return obj.get(key,default)
    return getattr(obj,key,default)

def _obj(value):
    if isinstance(value,dict) and "result" in value: return value["result"]
    return value

def _check(checks,name,passed,source,detail=""):
    checks.append(FinalizationCheck(name,bool(passed),source,detail))

def _claims():
    return [
        "Final boundary acceptance does not mean the action was executed.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def build_final_admission_boundary(integrity_result, *, handoff_result=None,
                                   readiness_result=None, crm_snapshot=None,
                                   authorization=None):
    i=_obj(integrity_result)
    status=str(_get(i,"status","") or "").upper()
    decision_source=_get(i,"decision")
    action=_get(i,"action")
    lead_id=_get(i,"lead_id")
    course_ids=list(_get(i,"course_ids",[]) or [])
    auth=str(_get(i,"authorization_state","UNKNOWN") or "UNKNOWN").upper()
    integrity_verified=bool(_get(i,"integrity_verified",False))
    handoff_created=bool(_get(i,"handoff_created",False))
    checks=[]
    missing=list(_get(i,"missing_requirements",[]) or [])
    conflicts=list(_get(i,"conflicts",[]) or [])
    errors=list(_get(i,"errors",[]) or [])

    _check(checks,"integrity_status_present",bool(status),"HANDOFF_INTEGRITY")
    _check(checks,"integrity_verified",integrity_verified,"HANDOFF_INTEGRITY")
    _check(checks,"handoff_created",handoff_created,"HANDOFF_INTEGRITY")
    _check(checks,"lead_present",bool(lead_id),"HANDOFF_INTEGRITY")
    _check(checks,"course_present",bool(course_ids),"HANDOFF_INTEGRITY")
    _check(checks,"authorization_granted",auth=="GRANTED","HANDOFF_INTEGRITY")

    if handoff_result is not None:
        h=_obj(handoff_result)
        h_status=str(_get(h,"status","") or "").upper()
        _check(checks,"handoff_status_match",h_status=="HANDOFF_READY","HANDOFF")
        _check(checks,"handoff_lead_match",lead_id==_get(h,"lead_id"),"HANDOFF")
        _check(checks,"handoff_course_match",course_ids==list(_get(h,"course_ids",[]) or []),"HANDOFF")
        _check(checks,"handoff_auth_match",auth==str(_get(h,"authorization_state","UNKNOWN") or "UNKNOWN").upper(),"HANDOFF")
        if h_status!="HANDOFF_READY": conflicts.append("handoff is not HANDOFF_READY")
        if lead_id!=_get(h,"lead_id"): conflicts.append("lead_id differs from handoff")
        if course_ids!=list(_get(h,"course_ids",[]) or []): conflicts.append("course_ids differ from handoff")

    if readiness_result is not None:
        r=_obj(readiness_result)
        _check(checks,"readiness_status_ready",str(_get(r,"status","")).upper()=="ACTION_READINESS_READY","ACTION_READINESS")
        _check(checks,"readiness_lead_match",lead_id==_get(r,"lead_id"),"ACTION_READINESS")
        _check(checks,"readiness_course_match",course_ids==list(_get(r,"course_ids",[]) or []),"ACTION_READINESS")
        if lead_id!=_get(r,"lead_id"): conflicts.append("lead_id differs from readiness")
        if course_ids!=list(_get(r,"course_ids",[]) or []): conflicts.append("course_ids differ from readiness")

    if crm_snapshot is not None:
        c=_obj(crm_snapshot) or {}
        _check(checks,"crm_lead_match",lead_id==_get(c,"lead_id"),"CRM_READ")
        cc=_get(c,"course_id")
        _check(checks,"crm_course_match",(not cc) or course_ids==[cc],"CRM_READ")
        if lead_id!=_get(c,"lead_id"): conflicts.append("lead_id differs from CRM")
        if cc and course_ids!=[cc]: conflicts.append("course differs from CRM")

    if authorization is not None:
        a=_obj(authorization)
        a_auth=str(_get(a,"authorization_state",_get(a,"status","UNKNOWN")) or "UNKNOWN").upper()
        _check(checks,"authorization_source_match",auth==a_auth,"AUTHORIZATION")
        if auth!=a_auth: conflicts.append("authorization differs from authorization source")

    all_checks=all(c.passed for c in checks)
    if conflicts:
        final_status,decision=FINAL_REVIEW,DECISION_REVIEW
        rationale="Material conflicts remain at finalization; human review is required."
        verified=False; created=False; human=True
    elif not status:
        final_status,decision=FINAL_UNKNOWN,DECISION_OBTAIN
        rationale="Final integrity state is unavailable."
        verified=False; created=False; human=False
    elif status=="HANDOFF_INTEGRITY_REVIEW":
        final_status,decision=FINAL_REVIEW,DECISION_REVIEW
        rationale="The integrity layer requires human review."
        verified=False; created=False; human=True
    elif status=="HANDOFF_INTEGRITY_BLOCKED":
        final_status,decision=FINAL_BLOCKED,DECISION_BLOCK
        rationale="The integrity layer blocked the handoff."
        verified=False; created=False; human=False
    elif status in {"HANDOFF_INTEGRITY_CLARIFICATION","HANDOFF_INTEGRITY_UNKNOWN"}:
        final_status=(FINAL_CLARIFICATION if status.endswith("CLARIFICATION") else FINAL_UNKNOWN)
        decision=(DECISION_CLARIFY if status.endswith("CLARIFICATION") else DECISION_OBTAIN)
        rationale="Verified information is insufficient for final boundary acceptance."
        verified=False; created=False; human=False
    elif not all_checks:
        final_status,decision=FINAL_REVIEW,DECISION_REVIEW
        rationale="One or more finalization checks failed."
        verified=False; created=False; human=True
    elif auth!="GRANTED":
        final_status,decision=FINAL_BLOCKED,DECISION_BLOCK
        rationale="Finalization cannot grant or substitute for explicit authorization."
        verified=False; created=False; human=False
    else:
        final_status,decision=FINAL_ACCEPTED,DECISION_ACCEPT
        rationale="The admission handoff is fully verified for a separate future executor boundary."
        verified=True; created=True; human=False

    provenance=["HANDOFF_INTEGRITY"]
    if handoff_result is not None: provenance.append("HANDOFF")
    if readiness_result is not None: provenance.append("ACTION_READINESS")
    if crm_snapshot is not None: provenance.append("CRM_READ")
    if authorization is not None: provenance.append("AUTHORIZATION")

    return FinalizationRuntimeResult(
        boundary=FinalizedAdmissionBoundary(
            status=final_status,decision=decision,action=action,lead_id=lead_id,
            course_ids=course_ids,authorization_state=auth,
            integrity_status=status,integrity_verified=integrity_verified,
            final_boundary_verified=verified,rationale=rationale,checks=checks,
            missing_requirements=list(dict.fromkeys(missing)),
            conflicts=list(dict.fromkeys(conflicts)),
            human_handoff_required=human,handoff_created=created,
            executor_invocation_allowed=False,execution_authorized=False,
            application_occurred=False,payment_occurred=False,
            enrollment_occurred=False,crm_write_allowed=False,
            message_send_allowed=False,external_action_allowed=False,
            provenance=list(dict.fromkeys(provenance)),prohibited_claims=_claims(),
            errors=errors
        )
    )

def run_final_admission_boundary(*args,**kwargs):
    return build_final_admission_boundary(*args,**kwargs)

def validate_final_admission_boundary(runtime):
    errors=[]
    b=runtime.boundary
    if b.status not in {FINAL_ACCEPTED,FINAL_CLARIFICATION,FINAL_REVIEW,FINAL_BLOCKED,FINAL_UNKNOWN}:
        errors.append("Invalid final status.")
    if b.decision not in {DECISION_ACCEPT,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN}:
        errors.append("Invalid final decision.")
    if b.status==FINAL_ACCEPTED:
        if not b.final_boundary_verified or not b.handoff_created:
            errors.append("Accepted final boundary must be verified and created.")
        if b.authorization_state!="GRANTED":
            errors.append("Accepted final boundary requires granted authorization.")
        if b.conflicts:
            errors.append("Accepted final boundary cannot contain conflicts.")
    if b.status==FINAL_REVIEW and not b.human_handoff_required:
        errors.append("Review requires human handoff.")
    if b.status!=FINAL_ACCEPTED and b.handoff_created:
        errors.append("Only accepted final boundary may retain created state.")
    if b.executor_invocation_allowed or b.execution_authorized:
        errors.append("Executor invocation and execution must remain disabled.")
    if b.application_occurred or b.payment_occurred or b.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if b.crm_write_allowed or b.message_send_allowed or b.external_action_allowed:
        errors.append("Side effects must remain disabled.")
    for c in b.checks:
        if not c.name or not c.source: errors.append("Checks require name and source.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled",
              "crm_writes_enabled","executor_invocation_enabled"):
        if runtime.safety.get(k) is not False: errors.append(f"{k} must remain False.")
    if runtime.safety.get("no_invention") is not True: errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True: errors.append("fail_closed must remain True.")
    return errors

def final_admission_boundary_to_dict(runtime):
    b=runtime.boundary
    return {"boundary":{
        "status":b.status,"decision":b.decision,"action":b.action,
        "lead_id":b.lead_id,"course_ids":list(b.course_ids),
        "authorization_state":b.authorization_state,"integrity_status":b.integrity_status,
        "integrity_verified":b.integrity_verified,"final_boundary_verified":b.final_boundary_verified,
        "rationale":b.rationale,
        "checks":[{"name":c.name,"passed":c.passed,"source":c.source,"detail":c.detail} for c in b.checks],
        "missing_requirements":list(b.missing_requirements),"conflicts":list(b.conflicts),
        "human_handoff_required":b.human_handoff_required,"handoff_created":b.handoff_created,
        "executor_invocation_allowed":b.executor_invocation_allowed,
        "execution_authorized":b.execution_authorized,"application_occurred":b.application_occurred,
        "payment_occurred":b.payment_occurred,"enrollment_occurred":b.enrollment_occurred,
        "crm_write_allowed":b.crm_write_allowed,"message_send_allowed":b.message_send_allowed,
        "external_action_allowed":b.external_action_allowed,"provenance":list(b.provenance),
        "prohibited_claims":list(b.prohibited_claims),"errors":list(b.errors)
    },"safety":dict(runtime.safety)}

def validate_serialized_final_admission_boundary(data):
    errors=[]
    if not isinstance(data,dict) or not isinstance(data.get("boundary"),dict):
        return ["Serialized result must contain boundary."]
    b=data["boundary"]
    for k in ("status","decision","action","authorization_state","integrity_status",
              "integrity_verified","final_boundary_verified","checks"):
        if k not in b: errors.append(f"Missing serialized field: {k}")
    for k in ("executor_invocation_allowed","execution_authorized",
              "crm_write_allowed","message_send_allowed","external_action_allowed"):
        if b.get(k) is not False: errors.append(f"Serialized {k} must be False.")
    return errors
