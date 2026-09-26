
"""
Sayyed EdVantage AI Agent — Phase 4 / Integration 03
Response Orchestration Integration Contract.

Connects conversation/CRM decision state to a single grounded response
orchestration result. This is still a preparation layer only:
no sending, CRM writes, external actions, executor invocation, or execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy

STATUS_READY="RESPONSE_ORCHESTRATION_READY"
STATUS_CLARIFY="RESPONSE_ORCHESTRATION_CLARIFICATION"
STATUS_REVIEW="RESPONSE_ORCHESTRATION_REVIEW"
STATUS_BLOCKED="RESPONSE_ORCHESTRATION_BLOCKED"
STATUS_UNKNOWN="RESPONSE_ORCHESTRATION_UNKNOWN"

MODE_RESPOND="RESPOND"
MODE_CLARIFY="CLARIFY"
MODE_HUMAN_REVIEW="HUMAN_REVIEW"
MODE_OBTAIN_STATE="OBTAIN_STATE"
MODE_NO_RESPONSE="NO_RESPONSE"

@dataclass
class ResponseOrchestration:
    status:str
    mode:str
    session_id:Optional[str]
    lead_id:Optional[str]
    course_ids:List[str]
    intent:str
    response_text:str
    response_allowed:bool
    evidence:List[Dict[str,Any]]=field(default_factory=list)
    provenance:List[str]=field(default_factory=list)
    prohibited_claims:List[str]=field(default_factory=list)
    conflicts:List[str]=field(default_factory=list)
    errors:List[str]=field(default_factory=list)
    human_handoff_required:bool=False
    execution_enabled:bool=False
    messaging_enabled:bool=False
    external_actions_enabled:bool=False
    crm_writes_enabled:bool=False
    executor_invocation_enabled:bool=False
    execution_authorized:bool=False

def _claims():
    return [
        "Do not invent missing course, commercial, certification, career, or enrollment information.",
        "Do not promise admission, employment, placement, salary, or income outcomes.",
        "Do not claim application, payment, or enrollment occurred unless independently verified.",
        "Response preparation does not authorize message sending or external actions.",
    ]

def _get(x,k,d=None):
    return x.get(k,d) if isinstance(x,dict) else getattr(x,k,d)

def build_response_orchestration(decision_result, *, integrated_result=None, crm_snapshot=None):
    d=decision_result
    status=str(_get(d,"status","") or "").upper()
    mode=str(_get(d,"mode","") or "").upper()
    session_id=_get(d,"session_id")
    lead_id=_get(d,"lead_id")
    courses=list(_get(d,"course_ids",[]) or [])
    intent=_get(d,"intent","unknown")
    text=_get(d,"response_text","") or ""
    errors=list(_get(d,"errors",[]) or [])
    conflicts=[]
    prov=list(_get(d,"provenance",[]) or [])
    evidence=deepcopy(_get(d,"evidence",[]) or [])
    human=False
    allowed=False

    if integrated_result is not None:
        ir=integrated_result
        if str(_get(ir,"status","")).upper() in {"INTEGRATED_RUNTIME_REVIEW","INTEGRATED_RUNTIME_BLOCKED"}:
            conflicts.append("integrated runtime requires review or is blocked")
        if lead_id is not None and _get(ir,"lead_id") is not None and lead_id != _get(ir,"lead_id"):
            conflicts.append("lead_id differs from integrated runtime")
        ic=list(_get(ir,"course_ids",[]) or [])
        if ic and courses and ic!=courses:
            conflicts.append("course_ids differ from integrated runtime")
        if "INTEGRATED_RUNTIME" not in prov:
            prov.append("INTEGRATED_RUNTIME")

    if crm_snapshot is not None:
        cl=_get(crm_snapshot,"lead_id")
        cc=list(_get(crm_snapshot,"course_ids",[]) or [])
        if lead_id is not None and cl is not None and lead_id!=cl:
            conflicts.append("lead_id differs from CRM snapshot")
        if cc and courses and cc!=courses:
            conflicts.append("course_ids differ from CRM snapshot")
        if "CRM_READ" not in prov:
            prov.append("CRM_READ")

    conflicts=list(dict.fromkeys(conflicts))

    if conflicts:
        out_status,out_mode=STATUS_REVIEW,MODE_HUMAN_REVIEW
        rationale="Material response-state conflict requires human review."
        human=True; allowed=False
    elif status in {"CONTEXT_DECISION_REVIEW","RESPONSE_CONTEXT_REVIEW"} or mode==MODE_HUMAN_REVIEW:
        out_status,out_mode=STATUS_REVIEW,MODE_HUMAN_REVIEW
        rationale="The current state requires human review before response preparation."
        human=True; allowed=False
    elif status in {"CONTEXT_DECISION_CLARIFICATION","RESPONSE_CONTEXT_CLARIFICATION"} or mode==MODE_CLARIFY:
        out_status,out_mode=STATUS_CLARIFY,MODE_CLARIFY
        rationale="The current state requires clarification before a grounded response."
        human=False; allowed=False
    elif status in {"CONTEXT_DECISION_UNKNOWN","RESPONSE_CONTEXT_UNKNOWN"} or mode==MODE_OBTAIN_STATE:
        out_status,out_mode=STATUS_UNKNOWN,MODE_OBTAIN_STATE
        rationale="Verified state is unavailable; obtain verified state before responding."
        human=False; allowed=False
    elif status=="CONTEXT_DECISION_READY" and mode==MODE_RESPOND:
        out_status,out_mode=STATUS_READY,MODE_RESPOND
        rationale="The response can be prepared from the current grounded state."
        human=False; allowed=True
    else:
        out_status,out_mode=STATUS_BLOCKED,MODE_NO_RESPONSE
        rationale="The upstream response state is not recognized as safe for response preparation."
        human=False; allowed=False

    return ResponseOrchestration(
        status=out_status,mode=out_mode,session_id=session_id,lead_id=lead_id,
        course_ids=courses,intent=intent,response_text=text if allowed else "",
        response_allowed=allowed,evidence=evidence,provenance=list(dict.fromkeys(prov)),
        prohibited_claims=_claims(),conflicts=conflicts,errors=errors,
        human_handoff_required=human,execution_enabled=False,messaging_enabled=False,
        external_actions_enabled=False,crm_writes_enabled=False,
        executor_invocation_enabled=False,execution_authorized=False)

def run_response_orchestration(*args,**kwargs):
    return build_response_orchestration(*args,**kwargs)

def validate_response_orchestration(r):
    e=[]
    if r.status not in {STATUS_READY,STATUS_CLARIFY,STATUS_REVIEW,STATUS_BLOCKED,STATUS_UNKNOWN}: e.append("invalid status")
    if r.mode not in {MODE_RESPOND,MODE_CLARIFY,MODE_HUMAN_REVIEW,MODE_OBTAIN_STATE,MODE_NO_RESPONSE}: e.append("invalid mode")
    if r.response_allowed != (r.status==STATUS_READY and r.mode==MODE_RESPOND): e.append("response flag mismatch")
    if r.human_handoff_required != (r.mode==MODE_HUMAN_REVIEW): e.append("handoff mismatch")
    if r.status==STATUS_READY and not r.response_text: e.append("ready response missing text")
    if r.status!=STATUS_READY and r.response_text: e.append("non-ready response must be empty")
    if r.status==STATUS_REVIEW and not r.human_handoff_required: e.append("review needs handoff")
    if r.status==STATUS_READY and r.conflicts: e.append("ready cannot contain conflicts")
    if any([r.execution_enabled,r.messaging_enabled,r.external_actions_enabled,
            r.crm_writes_enabled,r.executor_invocation_enabled,r.execution_authorized]):
        e.append("unsafe capability enabled")
    if not r.provenance: e.append("missing provenance")
    return e

def response_orchestration_to_dict(r):
    return {"response":{
        "status":r.status,"mode":r.mode,"session_id":r.session_id,"lead_id":r.lead_id,
        "course_ids":list(r.course_ids),"intent":r.intent,"response_text":r.response_text,
        "response_allowed":r.response_allowed,"evidence":deepcopy(r.evidence),
        "provenance":list(r.provenance),"prohibited_claims":list(r.prohibited_claims),
        "conflicts":list(r.conflicts),"errors":list(r.errors),
        "human_handoff_required":r.human_handoff_required,
        "execution_enabled":r.execution_enabled,"messaging_enabled":r.messaging_enabled,
        "external_actions_enabled":r.external_actions_enabled,"crm_writes_enabled":r.crm_writes_enabled,
        "executor_invocation_enabled":r.executor_invocation_enabled,
        "execution_authorized":r.execution_authorized}}

def validate_serialized_response_orchestration(d):
    if not isinstance(d,dict) or not isinstance(d.get("response"),dict): return ["Missing response envelope."]
    r=d["response"]; e=[]
    for k in ("status","mode","response_allowed","response_text","course_ids","provenance"): 
        if k not in r: e.append("Missing field: "+k)
    for k in ("execution_enabled","messaging_enabled","external_actions_enabled","crm_writes_enabled","executor_invocation_enabled","execution_authorized"):
        if r.get(k) is not False: e.append(k+" must be False.")
    return e
