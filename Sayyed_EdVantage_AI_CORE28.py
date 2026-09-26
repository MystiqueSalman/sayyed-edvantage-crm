
"""
Sayyed EdVantage AI Agent — AI Core 28
Admission Action Audit Summary & Evidence Packaging Contract

Consumes Core-27 audit output and produces a compact, attributable evidence
package for downstream orchestration. This remains read-only and does not
execute, invoke an executor, send messages, write CRM, or claim completion.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

PACKAGE_ACCEPTED="EVIDENCE_PACKAGE_ACCEPTED"
PACKAGE_CLARIFICATION="EVIDENCE_PACKAGE_CLARIFICATION"
PACKAGE_REVIEW="EVIDENCE_PACKAGE_REVIEW"
PACKAGE_BLOCKED="EVIDENCE_PACKAGE_BLOCKED"
PACKAGE_UNKNOWN="EVIDENCE_PACKAGE_UNKNOWN"

PACKAGE_ACCEPT="ACCEPT_EVIDENCE_PACKAGE"
PACKAGE_CLARIFY="CLARIFY_EVIDENCE_PACKAGE"
PACKAGE_REVIEW_DECISION="HUMAN_REVIEW_EVIDENCE_PACKAGE"
PACKAGE_BLOCK="BLOCK_EVIDENCE_PACKAGE"
PACKAGE_OBTAIN="OBTAIN_EVIDENCE_STATE"

@dataclass
class EvidenceItem:
    sequence:int
    checkpoint:str
    passed:bool
    source:str
    detail:str=""
    usable:bool=True

@dataclass
class AdmissionEvidencePackage:
    status:str
    decision:str
    action:Optional[str]
    lead_id:Optional[str]
    course_ids:List[str]
    audit_status:str
    audit_complete:bool
    final_boundary_verified:bool
    authorization_state:str
    evidence_count:int
    usable_evidence_count:int
    rationale:str
    evidence:List[EvidenceItem]=field(default_factory=list)
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
class EvidencePackageRuntime:
    package:AdmissionEvidencePackage
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
    if isinstance(v,dict) and "audit" in v: return v["audit"]
    return v

def _claims():
    return [
        "An evidence package does not mean an admission action was executed.",
        "Do not claim an application was submitted unless independently verified.",
        "Do not claim payment was received unless independently verified.",
        "Do not claim enrollment occurred unless independently verified.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "This layer does not invoke an executor, send messages, write CRM, or perform external actions.",
    ]

def build_admission_evidence_package(audit_result, *, final_boundary_result=None,
                                     integrity_result=None, handoff_result=None):
    a=_obj(audit_result)
    status=str(_get(a,"status","") or "").upper()
    action=_get(a,"action")
    lead_id=_get(a,"lead_id")
    courses=list(_get(a,"course_ids",[]) or [])
    auth=str(_get(a,"authorization_state","UNKNOWN") or "UNKNOWN").upper()
    audit_complete=bool(_get(a,"audit_complete",False))
    final_verified=bool(_get(a,"final_boundary_verified",False))
    conflicts=list(_get(a,"conflicts",[]) or [])
    missing=list(_get(a,"missing_requirements",[]) or [])
    failed=list(_get(a,"failed_checks",[]) or [])
    errors=list(_get(a,"errors",[]) or [])

    raw=[]
    for idx,e in enumerate(_get(a,"entries",[]) or [],1):
        raw.append(EvidenceItem(
            sequence=int(_get(e,"sequence",idx)),
            checkpoint=_get(e,"checkpoint","unknown"),
            passed=bool(_get(e,"passed",False)),
            source=_get(e,"source","AUDIT"),
            detail=_get(e,"detail",""),
            usable=bool(_get(e,"passed",False))
        ))
    raw.sort(key=lambda x:x.sequence)
    usable=sum(1 for e in raw if e.usable)

    if final_boundary_result is not None:
        f=_obj(final_boundary_result)
        fs=str(_get(f,"status","")).upper()
        if fs!="FINAL_HANDOFF_ACCEPTED":
            conflicts.append("final boundary is not accepted")
        if lead_id is not None and _get(f,"lead_id") is not None and lead_id!=_get(f,"lead_id"):
            conflicts.append("lead_id differs from final boundary")
        fc=list(_get(f,"course_ids",[]) or [])
        if fc and fc!=courses: conflicts.append("course_ids differ from final boundary")

    if integrity_result is not None:
        i=_obj(integrity_result)
        if str(_get(i,"status","")).upper()!="HANDOFF_INTEGRITY_PASS":
            conflicts.append("integrity source is not passing")

    if handoff_result is not None:
        h=_obj(handoff_result)
        if str(_get(h,"status","")).upper()!="HANDOFF_READY":
            conflicts.append("handoff source is not ready")

    conflicts=list(dict.fromkeys(conflicts))
    failed=list(dict.fromkeys(failed))

    if conflicts:
        st,dec=PACKAGE_REVIEW,PACKAGE_REVIEW_DECISION
        rationale="Material evidence conflicts require human review."
        accepted=False; human=True
    elif not status:
        st,dec=PACKAGE_UNKNOWN,PACKAGE_OBTAIN
        rationale="Audit state is unavailable."
        accepted=False; human=False
    elif status=="AUDIT_ACCEPTED" and failed:
        st,dec=PACKAGE_REVIEW,PACKAGE_REVIEW_DECISION
        rationale="The audit contains failed checkpoints; human review is required."
        accepted=False; human=True
    elif status=="AUDIT_ACCEPTED" and (not lead_id or not courses):
        st,dec=PACKAGE_CLARIFICATION,PACKAGE_CLARIFY
        rationale="Verified lead and course identity are required before accepting the evidence package."
        accepted=False; human=False
    elif status=="AUDIT_ACCEPTED" and audit_complete and final_verified and auth=="GRANTED":
        st,dec=PACKAGE_ACCEPTED,PACKAGE_ACCEPT
        rationale="Evidence is complete, attributable, and usable for the verified admission boundary."
        accepted=True; human=False
        rationale="Evidence is complete, attributable, and usable for the verified admission boundary."
        accepted=True; human=False
    elif status=="AUDIT_REVIEW":
        st,dec=PACKAGE_REVIEW,PACKAGE_REVIEW_DECISION
        rationale="The audit requires human review."
        accepted=False; human=True
    elif status=="AUDIT_BLOCKED":
        st,dec=PACKAGE_BLOCKED,PACKAGE_BLOCK
        rationale="The audit is blocked."
        accepted=False; human=False
    elif status=="AUDIT_CLARIFICATION":
        st,dec=PACKAGE_CLARIFICATION,PACKAGE_CLARIFY
        rationale="The audit requires clarification."
        accepted=False; human=False
    else:
        st,dec=PACKAGE_UNKNOWN,PACKAGE_OBTAIN
        rationale="The evidence package cannot be safely accepted."
        accepted=False; human=False

    prov=["AUDIT"]
    if final_boundary_result is not None: prov.append("FINAL_BOUNDARY")
    if integrity_result is not None: prov.append("HANDOFF_INTEGRITY")
    if handoff_result is not None: prov.append("HANDOFF")

    return EvidencePackageRuntime(
        package=AdmissionEvidencePackage(
            status=st,decision=dec,action=action,lead_id=lead_id,course_ids=courses,
            audit_status=status,audit_complete=audit_complete,
            final_boundary_verified=final_verified,authorization_state=auth,
            evidence_count=len(raw),usable_evidence_count=usable,rationale=rationale,
            evidence=raw,failed_checks=failed,conflicts=conflicts,
            missing_requirements=missing,human_handoff_required=human,
            executor_invocation_allowed=False,execution_authorized=False,
            application_occurred=False,payment_occurred=False,
            enrollment_occurred=False,crm_write_allowed=False,
            message_send_allowed=False,external_action_allowed=False,
            provenance=prov,prohibited_claims=_claims(),errors=errors
        )
    )

def run_admission_evidence_package(*args,**kwargs):
    return build_admission_evidence_package(*args,**kwargs)

def validate_admission_evidence_package(runtime):
    errors=[]; p=runtime.package
    if p.status not in {PACKAGE_ACCEPTED,PACKAGE_CLARIFICATION,PACKAGE_REVIEW,PACKAGE_BLOCKED,PACKAGE_UNKNOWN}:
        errors.append("Invalid package status.")
    if p.decision not in {PACKAGE_ACCEPT,PACKAGE_CLARIFY,PACKAGE_REVIEW_DECISION,PACKAGE_BLOCK,PACKAGE_OBTAIN}:
        errors.append("Invalid package decision.")
    if p.evidence_count!=len(p.evidence):
        errors.append("Evidence count mismatch.")
    if p.usable_evidence_count!=sum(1 for e in p.evidence if e.usable):
        errors.append("Usable evidence count mismatch.")
    if p.status==PACKAGE_ACCEPTED:
        if not p.audit_complete or not p.final_boundary_verified:
            errors.append("Accepted package must be complete and verified.")
        if p.authorization_state!="GRANTED":
            errors.append("Accepted package requires granted authorization.")
        if p.conflicts or p.failed_checks:
            errors.append("Accepted package cannot contain conflicts or failed checks.")
    if p.status==PACKAGE_REVIEW and not p.human_handoff_required:
        errors.append("Review requires human handoff.")
    if p.status!=PACKAGE_ACCEPTED and p.audit_complete and p.final_boundary_verified and not p.conflicts and p.failed_checks==[] and p.authorization_state=="GRANTED":
        # Non-accepted states are allowed only when upstream audit status itself is non-accepted.
        if p.audit_status=="AUDIT_ACCEPTED":
            errors.append("Accepted upstream audit should not become a non-accepted package without conflict.")
    if p.executor_invocation_allowed or p.execution_authorized:
        errors.append("Execution must remain disabled.")
    if p.application_occurred or p.payment_occurred or p.enrollment_occurred:
        errors.append("Occurrence claims must remain false.")
    if p.crm_write_allowed or p.message_send_allowed or p.external_action_allowed:
        errors.append("Side effects must remain disabled.")
    for e in p.evidence:
        if e.sequence<1 or not e.checkpoint or not e.source:
            errors.append("Invalid evidence item.")
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled","executor_invocation_enabled"):
        if runtime.safety.get(k) is not False: errors.append(f"{k} must remain False.")
    if runtime.safety.get("no_invention") is not True: errors.append("no_invention must remain True.")
    if runtime.safety.get("fail_closed") is not True: errors.append("fail_closed must remain True.")
    return errors

def admission_evidence_package_to_dict(runtime):
    p=runtime.package
    return {"package":{
        "status":p.status,"decision":p.decision,"action":p.action,"lead_id":p.lead_id,
        "course_ids":list(p.course_ids),"audit_status":p.audit_status,
        "audit_complete":p.audit_complete,"final_boundary_verified":p.final_boundary_verified,
        "authorization_state":p.authorization_state,"evidence_count":p.evidence_count,
        "usable_evidence_count":p.usable_evidence_count,"rationale":p.rationale,
        "evidence":[{"sequence":e.sequence,"checkpoint":e.checkpoint,"passed":e.passed,
                    "source":e.source,"detail":e.detail,"usable":e.usable} for e in p.evidence],
        "failed_checks":list(p.failed_checks),"conflicts":list(p.conflicts),
        "missing_requirements":list(p.missing_requirements),
        "human_handoff_required":p.human_handoff_required,
        "executor_invocation_allowed":p.executor_invocation_allowed,
        "execution_authorized":p.execution_authorized,
        "application_occurred":p.application_occurred,"payment_occurred":p.payment_occurred,
        "enrollment_occurred":p.enrollment_occurred,"crm_write_allowed":p.crm_write_allowed,
        "message_send_allowed":p.message_send_allowed,"external_action_allowed":p.external_action_allowed,
        "provenance":list(p.provenance),"prohibited_claims":list(p.prohibited_claims),
        "errors":list(p.errors)
    },"safety":dict(runtime.safety)}

def validate_serialized_admission_evidence_package(data):
    errors=[]
    if not isinstance(data,dict) or not isinstance(data.get("package"),dict):
        return ["Serialized result must contain package."]
    p=data["package"]
    for k in ("status","decision","action","authorization_state","evidence_count",
              "usable_evidence_count","evidence"):
        if k not in p: errors.append(f"Missing serialized field: {k}")
    for k in ("executor_invocation_allowed","execution_authorized","crm_write_allowed",
              "message_send_allowed","external_action_allowed"):
        if p.get(k) is not False: errors.append(f"Serialized {k} must be False.")
    return errors
