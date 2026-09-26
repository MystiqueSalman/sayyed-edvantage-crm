
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy
import json, os

STATUS_READY="CONTEXT_DECISION_READY"
STATUS_CLARIFY="CONTEXT_DECISION_CLARIFICATION"
STATUS_REVIEW="CONTEXT_DECISION_REVIEW"
STATUS_UNKNOWN="CONTEXT_DECISION_UNKNOWN"
MODE_RESPOND="RESPOND"
MODE_CLARIFY="CLARIFY"
MODE_HUMAN_REVIEW="HUMAN_REVIEW"
MODE_OBTAIN_STATE="OBTAIN_STATE"
VALID_COURSES={"SE-DS-001","SE-DA-001","SE-AIGEN-001","SE-PY-001","SE-LINUX-001","SE-DEVOPS-001","SE-EHC-001"}

@dataclass
class ConversationState:
    session_id:str
    lead_id:Optional[str]=None
    user_messages:List[str]=field(default_factory=list)
    response_history:List[str]=field(default_factory=list)
    active_course_ids:List[str]=field(default_factory=list)
    active_intent:Optional[str]=None

@dataclass
class DecisionPipelineResult:
    status:str
    mode:str
    session_id:str
    lead_id:Optional[str]
    course_ids:List[str]
    intent:str
    response_text:str
    context_reused:bool
    crm_verified:bool
    evidence:List[Dict[str,Any]]=field(default_factory=list)
    provenance:List[str]=field(default_factory=list)
    errors:List[str]=field(default_factory=list)
    human_handoff_required:bool=False
    execution_enabled:bool=False
    messaging_enabled:bool=False
    external_actions_enabled:bool=False
    crm_writes_enabled:bool=False
    executor_invocation_enabled:bool=False
    execution_authorized:bool=False

class ConversationCRMDecisionPipeline:
    def __init__(self,project_root=None):
        self.project_root=project_root or os.getcwd()
        self.sessions={}
        self.execution_enabled=False; self.messaging_enabled=False
        self.external_actions_enabled=False; self.crm_writes_enabled=False
        self.executor_invocation_enabled=False; self.execution_authorized=False
        self.no_invention=True; self.fail_closed=True

    def _crm_path(self): return os.path.join(self.project_root,"data","leads.json")
    def _read_lead(self,lead_id):
        if not lead_id or not os.path.exists(self._crm_path()): return {}
        try:
            with open(self._crm_path(),encoding="utf-8") as f: data=json.load(f)
            leads=data.get("leads",data) if isinstance(data,dict) else data
            if isinstance(leads,list):
                for x in leads:
                    if isinstance(x,dict) and str(x.get("lead_id"))==str(lead_id): return deepcopy(x)
            elif isinstance(leads,dict) and isinstance(leads.get(lead_id),dict): return deepcopy(leads[lead_id])
        except Exception: return {}
        return {}

    def _detect_courses(self,text):
        t=text.lower()
        mapping=[
            (["data science","machine learning"],"SE-DS-001"),
            (["data analytics","power bi"],"SE-DA-001"),
            (["ai + generative ai","generative ai","gen ai","llm","langchain","langgraph","rag"],"SE-AIGEN-001"),
            (["python"],"SE-PY-001"),(["linux"],"SE-LINUX-001"),
            (["devops","docker","kubernetes","terraform"],"SE-DEVOPS-001"),
            (["ethical hacking","cybersecurity","cyber security","owasp"],"SE-EHC-001")]
        return list(dict.fromkeys(cid for keys,cid in mapping if any(k in t for k in keys)))

    def _intent(self,text):
        t=text.lower()
        if any(x in t for x in ["fee","fees","price","cost","discount","payment","gst","tax"]): return "commercial"
        if any(x in t for x in ["eligible","eligibility","qualification","prerequisite"]): return "eligibility"
        if any(x in t for x in ["certificate","certification"]): return "certification"
        if any(x in t for x in ["job","salary","placement","career"]): return "career"
        if any(x in t for x in ["which course","recommend","suggest","best course"]): return "course_recommendation"
        return "program_information"

    def _respond(self,text,courses,intent,lead):
        names={"SE-DS-001":"Data Science","SE-DA-001":"Data Analytics","SE-AIGEN-001":"AI + Generative AI","SE-PY-001":"Python","SE-LINUX-001":"Linux","SE-DEVOPS-001":"DevOps","SE-EHC-001":"Ethical Hacking & Cybersecurity"}
        fees={"SE-DS-001":"₹50,000","SE-DA-001":"₹40,000","SE-AIGEN-001":"₹70,000","SE-PY-001":"₹35,000","SE-LINUX-001":"₹25,000","SE-DEVOPS-001":"₹45,000","SE-EHC-001":"₹60,000"}
        if len(courses)>1: return MODE_CLARIFY,"Please tell me which course you want to discuss first: "+", ".join(names[x] for x in courses)+"."
        if not courses:
            if intent=="course_recommendation": return MODE_CLARIFY,"I need a little information about your background and goal before recommending a course."
            return MODE_CLARIFY,"Please specify the course or provide more context so I can give a grounded answer."
        c=courses[0]; name=names[c]; region=str((lead or {}).get("region") or "").lower()
        if intent=="commercial":
            if not region: return MODE_CLARIFY,"Before quoting a fee, I need to know whether the student is in India or international."
            if region not in {"india","indian","in"}: return MODE_HUMAN_REVIEW,f"{name} information is available, but international pricing is not defined in the verified knowledge. Admissions should confirm the applicable fee."
            if any(x in text.lower() for x in ["discount","installment","emi","payment plan"]): return MODE_HUMAN_REVIEW,f"The verified Indian base fee for {name} is {fees[c]}. Discount and payment-plan details are not defined, so admissions should confirm them."
            return MODE_RESPOND,f"The verified Indian base fee for {name} is {fees[c]}. Admissions should confirm the final fee, applicable taxes, payment options, and enrollment details."
        if intent=="career": return MODE_RESPOND,f"{name} builds relevant skills and practical preparation. The verified knowledge does not guarantee a job, placement, salary, or income outcome."
        if intent=="certification": return MODE_RESPOND,f"Certification details for {name} are not currently defined in the verified knowledge, so I will not invent them."
        return MODE_RESPOND,f"I can provide verified information about {name} based on the available course knowledge."

    def run_turn(self,session_id,message,lead_id=None):
        if not session_id: session_id="SESSION-DEFAULT"
        if not isinstance(message,str) or not message.strip():
            return DecisionPipelineResult(STATUS_CLARIFY,MODE_CLARIFY,session_id,lead_id,[],"unknown","Please provide a question or message.",False,False,provenance=["DECISION_PIPELINE"])
        state=self.sessions.setdefault(session_id,ConversationState(session_id))
        effective_lead_id=lead_id or state.lead_id
        lead=self._read_lead(effective_lead_id) if effective_lead_id else {}
        if lead_id:
            state.lead_id=lead_id
        if effective_lead_id and not lead:
            return DecisionPipelineResult(STATUS_CLARIFY,MODE_CLARIFY,session_id,effective_lead_id,[],"unknown","I could not verify that lead in the CRM. Please provide a valid lead ID.",False,False,errors=["CRM lead not found."],provenance=["CRM_READ","DECISION_PIPELINE"])
        explicit=self._detect_courses(message)
        context_reused=False
        courses=explicit
        if not courses and state.active_course_ids:
            courses=list(state.active_course_ids); context_reused=True
        if not courses and lead.get("course_id") in VALID_COURSES:
            courses=[lead["course_id"]]; context_reused=True
        intent=self._intent(message)
        # Generic follow-ups inherit the established intent, but a new
        # commercial/eligibility/career/etc. signal always overrides context.
        explicit_intent=intent!="program_information"
        if not explicit_intent:
            t=message.lower()
            if any(x in t for x in ["fee","fees","price","cost","discount","payment","gst","tax"]):
                intent="commercial"; explicit_intent=True
            elif any(x in t for x in ["eligible","eligibility","qualification","prerequisite"]):
                intent="eligibility"; explicit_intent=True
            elif any(x in t for x in ["certificate","certification"]):
                intent="certification"; explicit_intent=True
            elif any(x in t for x in ["job","salary","placement","career"]):
                intent="career"; explicit_intent=True
            elif state.active_intent:
                intent=state.active_intent
        mode,text=self._respond(message,courses,intent,lead)
        status={MODE_RESPOND:STATUS_READY,MODE_CLARIFY:STATUS_CLARIFY,MODE_HUMAN_REVIEW:STATUS_REVIEW}.get(mode,STATUS_UNKNOWN)
        if len(courses)==1: state.active_course_ids=list(courses)
        if explicit_intent or state.active_intent is None: state.active_intent=intent
        state.user_messages.append(message); state.response_history.append(text)
        prov=["DECISION_PIPELINE"]
        if effective_lead_id: prov.insert(0,"CRM_READ")
        if courses: prov.append("MASTER_KB")
        if context_reused: prov.append("CONVERSATION_CONTEXT")
        return DecisionPipelineResult(status,mode,session_id,effective_lead_id,list(courses),intent,text,context_reused,bool(lead),[{"course_ids":list(courses),"intent":intent}],list(dict.fromkeys(prov)),human_handoff_required=(mode==MODE_HUMAN_REVIEW))
    def validate(self,r):
        e=[]
        if r.status not in {STATUS_READY,STATUS_CLARIFY,STATUS_REVIEW,STATUS_UNKNOWN}: e.append("invalid status")
        if r.mode not in {MODE_RESPOND,MODE_CLARIFY,MODE_HUMAN_REVIEW,MODE_OBTAIN_STATE}: e.append("invalid mode")
        if r.human_handoff_required!=(r.mode==MODE_HUMAN_REVIEW): e.append("handoff mismatch")
        if any([r.execution_enabled,r.messaging_enabled,r.external_actions_enabled,r.crm_writes_enabled,r.executor_invocation_enabled,r.execution_authorized]): e.append("unsafe flag enabled")
        if not r.provenance: e.append("missing provenance")
        return e

def run_decision_pipeline(session_id,message,lead_id=None,project_root=None):
    return ConversationCRMDecisionPipeline(project_root).run_turn(session_id,message,lead_id)
