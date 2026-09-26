
"""
Sayyed EdVantage AI Agent — AI Core 27
Admission Action Audit & Traceability Contract

Consumes the finalized admission boundary and creates a deterministic,
read-only audit record showing why the boundary was accepted, clarified,
reviewed, blocked, or left unknown.

No execution, executor invocation, CRM writes, messaging, or external actions.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

AUDIT_ACCEPTED="AUDIT_ACCEPTED"
AUDIT_CLARIFICATION="AUDIT_CLARIFICATION"
AUDIT_REVIEW="AUDIT_REVIEW"
AUDIT_BLOCKED="AUDIT_BLOCKED"
AUDIT_UNKNOWN="AUDIT_UNKNOWN"

DECISION_AUDIT_ACCEPT="AUDIT_ACCEPT_FINAL_BOUNDARY"
DECISION_AUDIT_CLARIFY="AUDIT_CLARIFY_FINAL_BOUNDARY"
DECISION_AUDIT_REVIEW="AUDIT_HUMAN_REVIEW"
DECISION_AUDIT_BLOCK="AUDIT_BLOCK"
DECISION_AUDIT_OBTAIN="AUDIT_OBTAIN_STATE"

@dataclass
class AuditEntry:
    sequence: int
    checkpoint: str
    status: str
    passed: bool
    source: str
    detail: str=""

@dataclass
class AdmissionActionAudit:
    status:str
    decision:str
    action:Optional[str]
    lead_id:Optional[str]
    course_ids:List[str]
    final_boundary_status:str
    final_boundary_verified:bool
    authorization_state:str
    audit_complete:bool
    rationale:str
    entries:List[AuditEntry]=field(default_factory=list)
    failed_checks:List[str]=field(default_factory=list)
    conflicts:List[str]=field(default_factory=list)
    missing_requirements:List[str]=field(default_factory=list)
    human_handoff_required:bool=False
    executor_invocation_allowed:bool=False
    execution_authorized:bool=False
    application_occurred:bool=False
    payment_occurred:bool=False
    enrollment_occurred:bool=False
    crm_write_allowed:bool=False
    message_send_allowed:bool=False
    external_action_allowed:bool=False
    provenance:List[str]=field(default_factory=list)
    prohibited_claims:List[str]=field(default_factory=list)
    errors:List[str]=field(default_factory=list)

@dataclass
class AdmissionActionAuditRuntime:
    audit:AdmissionActionAudit
    safety:Dict[str,bool]=field(default_factory=lambda:{
        "execution_enabled":False,
        "messaging_enabled":False,
        "external_actions_enabled":False,
        "crm_writes_enabled":False,
        "executor_invocation_enabled":False,
        "no_invention":True,
        "fail_closed":True,
    })

def _get(o,k,d=None):
    if isinstance(o,dict): return o.get(k,d)
    return getattr(o,k,d)

def _obj(v):
    if isinstance(v,dict) and "boundary" in v: return v["boundary"]
    return v

def _entry(entries,seq,checkpoint,status,passed,source,detail=""):
    entries.append(AuditEntry(seq,checkpoint,status,bool(passed),source,detail))

def _claims():
    return [
        "An audit record does not mean the admission action was executed.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This audit layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def build_admission_action_audit(final_boundary_result, *, integrity_result=None,
                                 handoff_result=None, readiness_result=None,
                                 crm_snapshot=None, authorization=None):
    b=_obj(final_boundary_result)
    final_status=str(_get(b,"status","") or "").upper()
    action=_get(b,"action")
    lead_id=_get(b,"lead_id")
    courses=list(_get(b,"course_ids",[]) or [])
    auth=str(_get(b,"authorization_state","UNKNOWN") or "UNKNOWN").upper()
    final_verified=bool(_get(b,"final_boundary_verified",False))
    entries=[]; seq=1
    failed=[]; conflicts=list(_get(b,"conflicts",[]) or [])
    missing=list(_get(b,"missing_requirements",[]) or [])
    errors=list(_get(b,"errors",[]) or [])

    _entry(entries,seq,"final_status_present",final_status, bool(final_status),"FINAL_BOUNDARY"); seq+=1
    _entry(entries,seq,"final_boundary_verified",final_status,final_verified,"FINAL_BOUNDARY"); seq+=1
    _entry(entries,seq,"handoff_created",final_status,bool(_get(b,"handoff_created",False)),"FINAL_BOUNDARY"); seq+=1
    _entry(entries,seq,"lead_present",final_status,bool(lead_id),"FINAL_BOUNDARY"); seq+=1
    _entry(entries,seq,"course_present",final_status,bool(courses),"FINAL_BOUNDARY"); seq+=1
    _entry(entries,seq,"authorization_granted",final_status,auth=="GRANTED","FINAL_BOUNDARY"); seq+=1

    for c in _get(b,"checks",[]) or []:
        name=_get(c,"name","unknown")
        passed=bool(_get(c,"passed",False))
        source=_get(c,"source","FINAL_BOUNDARY")
        detail=_get(c,"detail","")
        _entry(entries,seq,name,final_status,passed,source,detail); seq+=1
        if not passed: failed.append(name)

    if integrity_result is not None:
        i=_obj(integrity_result)
        _entry(entries,seq,"integrity_status_match",
                final_status,bool(_get(i,"status")),"HANDOFF_INTEGRITY"); seq+=1
        if str(_get(i,"status","")).upper()!="HANDOFF_INTEGRITY_PASS":
            conflicts.append("integrity source is not passing")

    if handoff_result is not None:
        h=_obj(handoff_result)
        ok=str(_get(h,"status","")).upper()=="HANDOFF_READY"
        _entry(entries,seq,"handoff_ready",final_status,ok,"HANDOFF"); seq+=1
        if not ok: conflicts.append("handoff source is not ready")

    if readiness_result is not None:
        r=_obj(readiness_result)
        ok=str(_get(r,"status","")).upper()=="ACTION_READINESS_READY"
        _entry(entries,seq,"action_readiness_ready",final_status,ok,"ACTION_READINESS"); seq+=1
        if not ok: conflicts.append("action-readiness source is not ready")
        r_lead=_get(r,"lead_id")
        r_courses=list(_get(r,"course_ids",[]) or [])
        r_auth=_get(r,"authorization_state",None)
        if r_lead is not None and r_lead != lead_id:
            conflicts.append("lead_id differs from action-readiness source")
        if r_courses and r_courses != courses:
            conflicts.append("course_ids differ from action-readiness source")
        if r_auth is not None and str(r_auth).upper() != auth:
            conflicts.append("authorization differs from action-readiness source")

    if crm_snapshot is not None:
        c=_obj(crm_snapshot) or {}
        ok=lead_id==_get(c,"lead_id")
        _entry(entries,seq,"crm_lead_match",final_status,ok,"CRM_READ"); seq+=1
        if not ok: conflicts.append("lead_id differs from CRM")
        cc=_get(c,"course_id")
        ok=(not cc) or courses==[cc]
        _entry(entries,seq,"crm_course_match",final_status,ok,"CRM_READ"); seq+=1
        if not ok: conflicts.append("course differs from CRM")

    if authorization is not None:
        a=_obj(authorization)
        aa=str(_get(a,"authorization_state",_get(a,"status","UNKNOWN")) or "UNKNOWN").upper()
        ok=auth==aa
        _entry(entries,seq,"authorization_source_match",final_status,ok,"AUTHORIZATION"); seq+=1
        if not ok: conflicts.append("authorization differs from authorization source")

    for e in entries:
        if not e.passed:
            failed.append(e.checkpoint)
    failed=list(dict.fromkeys(failed))
    conflicts=list(dict.fromkeys(conflicts))
    all_checks=all(c.passed for c in entries)
    if conflicts:
        status,decision=AUDIT_REVIEW,DECISION_AUDIT_REVIEW
        rationale="Audit trace detected material state conflicts; human review is required."
        complete=False; human=True
    elif not final_status:
        status,decision=AUDIT_UNKNOWN,DECISION_AUDIT_OBTAIN
        rationale="Final boundary state is unavailable."
        complete=False; human=False
    elif final_status=="FINAL_HANDOFF_ACCEPTED" and final_verified and auth=="GRANTED" and not failed:
        status,decision=AUDIT_ACCEPTED,DECISION_AUDIT_ACCEPT
        rationale="Audit trail is complete and supports the final verified boundary."
        complete=True; human=False
    elif final_status=="FINAL_HANDOFF_REVIEW":
        status,decision=AUDIT_REVIEW,DECISION_AUDIT_REVIEW
        rationale="Final boundary requires human review."
        complete=False; human=True
    elif final_status=="FINAL_HANDOFF_BLOCKED":
        status,decision=AUDIT_BLOCKED,DECISION_AUDIT_BLOCK
        rationale="Final boundary is blocked."
        complete=False; human=False
    elif final_status=="FINAL_HANDOFF_CLARIFICATION":
        status,decision=AUDIT_CLARIFICATION,DECISION_AUDIT_CLARIFY
        rationale="Final boundary requires clarification."
        complete=False; human=False
    elif final_status=="FINAL_HANDOFF_UNKNOWN":
        status,decision=AUDIT_UNKNOWN,DECISION_AUDIT_OBTAIN
        rationale="Final boundary state is unknown and verified state must be obtained."
        complete=False; human=False
    elif not all_checks or failed:
        status,decision=AUDIT_REVIEW,DECISION_AUDIT_REVIEW
        rationale="One or more audit checkpoints failed."
        complete=False; human=True
    else:
        status,decision=AUDIT_UNKNOWN,DECISION_AUDIT_OBTAIN
        rationale="Final boundary cannot be safely audited as accepted."
        complete=False; human=False

    prov=["FINAL_BOUNDARY"]
    if integrity_result is not None: prov.append("HANDOFF_INTEGRITY")
    if handoff_result is not None: prov.append("HANDOFF")
    if readiness_result is not None: prov.append("ACTION_READINESS")
    if crm_snapshot is not None: prov.append("CRM_READ")
    if authorization is not None: prov.append("AUTHORIZATION")

    return AdmissionActionAuditRuntime(
        audit=AdmissionActionAudit(
            status=status,decision=decision,action=action,lead_id=lead_id,
            course_ids=courses,final_boundary_status=final_status,
            final_boundary_verified=final_verified,authorization_state=auth,
            audit_complete=complete,rationale=rationale,entries=entries,
            failed_checks=failed,conflicts=conflicts,
            missing_requirements=missing,human_handoff_required=human,
            executor_invocation_allowed=False,execution_authorized=False,
            application_occurred=False,payment_occurred=False,
            enrollment_occurred=False,crm_write_allowed=False,
            message_send_allowed=False,external_action_allowed=False,
            provenance=list(dict.fromkeys(prov)),prohibited_claims=_claims(),
            errors=errors
        )
    )

def run_admission_action_audit(*args,**kwargs):
    return build_admission_action_audit(*args,**kwargs)

def validate_admission_action_audit(runtime):
    errors=[]; a=runtime.audit
    if a.status not in {AUDIT_ACCEPTED,AUDIT_CLARIFICATION,AUDIT_REVIEW,AUDIT_BLOCKED,AUDIT_UNKNOWN}:
        errors.append("Invalid audit status.")
    if a.decision not in {DECISION_AUDIT_ACCEPT,DECISION_AUDIT_CLARIFY,DECISION_AUDIT_REVIEW,DECISION_AUDIT_BLOCK,DECISION_AUDIT_OBTAIN}:
        errors.append("Invalid audit decision.")
    if a.status==AUDIT_ACCEPTED:
        if not a.audit_complete or not a.final_boundary_verified: errors.append("Accepted audit must be complete and verified.")
        if a.conflicts or a.failed_checks: errors.append("Accepted audit cannot contain conflicts or failed checks.")
        if a.authorization_state!="GRANTED": errors.append("Accepted audit requires granted authorization.")
    if a.status==AUDIT_REVIEW and not a.human_handoff_required: errors.append("Review requires human handoff.")
    if a.executor_invocation_allowed or a.execution_authorized: errors.append("Execution boundary must remain disabled.")
    if a.application_occurred or a.payment_occurred or a.enrollment_occurred: errors.append("Occurrence claims must remain false.")
    if a.crm_write_allowed or a.message_send_allowed or a.external_action_allowed: errors.append("Side effects must remain disabled.")
    if not a.entries: errors.append("Audit must contain trace entries.")
    for e in a.entries:
        if e.sequence<1 or not e.checkpoint or not e.source: errors.append("Invalid audit entry.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled","executor_invocation_enabled"):
        if runtime.safety.get(k) is not False: errors.append(f"{k} must remain False.")
    if runtime.safety.get("no_invention") is not True: errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True: errors.append("fail_closed must remain True.")
    return errors

def admission_action_audit_to_dict(runtime):
    a=runtime.audit
    return {"audit":{
        "status":a.status,"decision":a.decision,"action":a.action,"lead_id":a.lead_id,
        "course_ids":list(a.course_ids),"final_boundary_status":a.final_boundary_status,
        "final_boundary_verified":a.final_boundary_verified,
        "authorization_state":a.authorization_state,"audit_complete":a.audit_complete,
        "rationale":a.rationale,
        "entries":[{"sequence":e.sequence,"checkpoint":e.checkpoint,"status":e.status,
                    "passed":e.passed,"source":e.source,"detail":e.detail} for e in a.entries],
        "failed_checks":list(a.failed_checks),"conflicts":list(a.conflicts),
        "missing_requirements":list(a.missing_requirements),
        "human_handoff_required":a.human_handoff_required,
        "executor_invocation_allowed":a.executor_invocation_allowed,
        "execution_authorized":a.execution_authorized,
        "application_occurred":a.application_occurred,
        "payment_occurred":a.payment_occurred,
        "enrollment_occurred":a.enrollment_occurred,
        "crm_write_allowed":a.crm_write_allowed,
        "message_send_allowed":a.message_send_allowed,
        "external_action_allowed":a.external_action_allowed,
        "provenance":list(a.provenance),"prohibited_claims":list(a.prohibited_claims),
        "errors":list(a.errors)
    },"safety":dict(runtime.safety)}

def validate_serialized_admission_action_audit(data):
    errors=[]
    if not isinstance(data,dict) or not isinstance(data.get("audit"),dict):
        return ["Serialized result must contain audit."]
    a=data["audit"]
    for k in ("status","decision","action","authorization_state","audit_complete","entries"):
        if k not in a: errors.append(f"Missing serialized field: {k}")
    for k in ("executor_invocation_allowed","execution_authorized","crm_write_allowed",
              "message_send_allowed","external_action_allowed"):
        if a.get(k) is not False: errors.append(f"Serialized {k} must be False.")
    return errors
