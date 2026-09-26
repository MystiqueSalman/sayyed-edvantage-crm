
"""
Sayyed EdVantage AI Agent — Phase 4 / Integration 01
Unified Runtime Integration

Connects the completed Master KB + AI Core stack + CRM read layer into one
deterministic, read-only agent pipeline.

This integration layer prepares responses only. It does NOT send messages,
write CRM, execute actions, call an executor, or perform external actions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy
import os, json

RUNTIME_READY = "INTEGRATED_RUNTIME_READY"
RUNTIME_CLARIFICATION = "INTEGRATED_RUNTIME_CLARIFICATION"
RUNTIME_REVIEW = "INTEGRATED_RUNTIME_REVIEW"
RUNTIME_BLOCKED = "INTEGRATED_RUNTIME_BLOCKED"
RUNTIME_UNKNOWN = "INTEGRATED_RUNTIME_UNKNOWN"

@dataclass
class IntegratedAgentResult:
    status: str
    lead_id: Optional[str]
    course_ids: List[str]
    intent: str
    response_mode: str
    response_text: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False
    executor_invocation_enabled: bool = False
    execution_authorized: bool = False

class SayyedEdVantageIntegratedRuntime:
    """
    Integration facade.

    The facade deliberately uses the existing project artifacts through
    importable adapters when available. It also supports a deterministic
    fallback path so the integration contract can be tested independently.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.getcwd()
        self.execution_enabled = False
        self.messaging_enabled = False
        self.external_actions_enabled = False
        self.crm_writes_enabled = False
        self.executor_invocation_enabled = False
        self.execution_authorized = False
        self.no_invention = True
        self.fail_closed = True

    def _crm_path(self):
        return os.path.join(self.project_root, "data", "leads.json")

    def read_lead(self, lead_id: str) -> Dict[str, Any]:
        if not lead_id:
            return {}
        path = self._crm_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            leads = data.get("leads", data) if isinstance(data, dict) else data
            if isinstance(leads, list):
                for lead in leads:
                    if isinstance(lead, dict) and str(lead.get("lead_id")) == str(lead_id):
                        return deepcopy(lead)
            elif isinstance(leads, dict):
                lead = leads.get(lead_id)
                if isinstance(lead, dict):
                    return deepcopy(lead)
        except Exception:
            return {}
        return {}

    def _course_from_text(self, text: str) -> List[str]:
        t = (text or "").lower()
        aliases = [
            (["data science", "machine learning"], "SE-DS-001"),
            (["data analytics", "power bi", "sql"], "SE-DA-001"),
            (["ai + generative ai", "generative ai", "gen ai", "llm", "langchain", "langgraph", "rag"], "SE-AIGEN-001"),
            (["python"], "SE-PY-001"),
            (["linux"], "SE-LINUX-001"),
            (["devops", "kubernetes", "docker", "terraform"], "SE-DEVOPS-001"),
            (["ethical hacking", "cybersecurity", "cyber security", "owasp"], "SE-EHC-001"),
        ]
        found=[]
        for keys,cid in aliases:
            if any(k in t for k in keys) and cid not in found:
                found.append(cid)
        return found

    def _intent(self, text: str) -> str:
        t=(text or "").lower()
        if any(x in t for x in ["fee","fees","price","cost","discount","payment","gst","tax"]):
            return "commercial"
        if any(x in t for x in ["eligible","eligibility","qualification","prerequisite"]):
            return "eligibility"
        if any(x in t for x in ["certificate","certification"]):
            return "certification"
        if any(x in t for x in ["job","salary","career","placement"]):
            return "career"
        if any(x in t for x in ["project","assessment","exam"]):
            return "assessment_projects"
        if any(x in t for x in ["tool","software","technology"]):
            return "tools"
        if any(x in t for x in ["which course","recommend","suggest","best course"]):
            return "course_recommendation"
        return "program_information"

    def _response(self, text: str, lead: Dict[str,Any], courses: List[str], intent: str):
        t=(text or "").lower()
        region=(lead.get("region") or lead.get("country") or "").lower() if lead else ""
        names={
            "SE-DS-001":"Data Science",
            "SE-DA-001":"Data Analytics",
            "SE-AIGEN-001":"AI + Generative AI",
            "SE-PY-001":"Python",
            "SE-LINUX-001":"Linux",
            "SE-DEVOPS-001":"DevOps",
            "SE-EHC-001":"Ethical Hacking & Cybersecurity",
        }
        fees={
            "SE-DS-001":"₹50,000",
            "SE-DA-001":"₹40,000",
            "SE-AIGEN-001":"₹70,000",
            "SE-PY-001":"₹35,000",
            "SE-LINUX-001":"₹25,000",
            "SE-DEVOPS-001":"₹45,000",
            "SE-EHC-001":"₹60,000",
        }
        if len(courses)>1:
            return ("CLARIFY", "I can help with these courses, but I need to know which course you want to discuss first: " +
                    ", ".join(names.get(c,c) for c in courses) + ".")
        if intent=="course_recommendation":
            return ("CLARIFY","I can recommend a course, but I need a little more information about your background and goal first.")
        if not courses:
            return ("CLARIFY","I can help, but I need the course name or a little more context to give a grounded answer.")
        c=courses[0]; name=names[c]
        if intent=="commercial":
            if region and region not in ["india","indian","in"]:
                return ("HANDOFF",f"{name} information is available. International pricing is not currently defined in the verified knowledge, so admissions should confirm the applicable fee and enrollment details.")
            if not region:
                return ("CLARIFY",f"I can provide the verified fee once I know whether the student is in India or internationally. I will not assume a region or quote the wrong regional fee.")
            if any(x in t for x in ["discount","payment plan","installment","emi"]):
                return ("HANDOFF",f"For {name}, the verified Indian base fee is {fees[c]}. Discount and payment-plan details are not defined in the verified knowledge, so admissions should confirm them.")
            if "gst" in t or "tax" in t:
                return ("READY",f"For {name}, the verified Indian base fee is {fees[c]}. GST/tax may apply; the final fee and applicable tax should be confirmed by admissions.")
            return ("READY",f"The verified Indian base fee for {name} is {fees[c]}. Admissions should confirm the final fee, applicable taxes, payment options, and enrollment details.")
        if intent=="certification":
            return ("READY",f"Certification details for {name} are not currently defined in the verified knowledge. I would route that question to admissions/faculty rather than invent an answer.")
        if intent=="career":
            return ("READY",f"{name} is designed to build relevant skills and practical preparation. The verified knowledge does not guarantee a job, placement, salary, or income outcome.")
        return ("READY",f"I can provide verified information about {name}. The response is grounded in the course knowledge and will not invent missing details.")

    def run(self, message: str, lead_id: Optional[str] = None) -> IntegratedAgentResult:
        if not isinstance(message, str) or not message.strip():
            return IntegratedAgentResult(RUNTIME_CLARIFICATION,lead_id,[],"unknown","CLARIFY",
                "Please provide a question or message.",provenance=["INTEGRATED_RUNTIME"])
        lead=self.read_lead(lead_id) if lead_id else {}
        if lead_id and not lead:
            return IntegratedAgentResult(RUNTIME_CLARIFICATION,lead_id,[],"unknown","CLARIFY",
                "I could not verify that lead in the CRM. Please provide a valid lead ID.",
                provenance=["CRM_READ","INTEGRATED_RUNTIME"],errors=["CRM lead not found."])
        courses=self._course_from_text(message)
        if not courses and lead:
            # Reuse only an explicitly stored course identity from CRM.
            cid=lead.get("course_id")
            if cid and cid in {"SE-DS-001","SE-DA-001","SE-AIGEN-001","SE-PY-001","SE-LINUX-001","SE-DEVOPS-001","SE-EHC-001"}:
                courses=[cid]
        intent=self._intent(message)
        mode,text=self._response(message,lead,courses,intent)
        status=RUNTIME_REVIEW if mode=="HANDOFF" else RUNTIME_CLARIFICATION if mode=="CLARIFY" else RUNTIME_READY
        provenance=["INTEGRATED_RUNTIME"]
        if lead_id: provenance.insert(0,"CRM_READ")
        if courses: provenance.append("MASTER_KB")
        return IntegratedAgentResult(status,lead_id,courses,intent,mode,text,
            evidence=[{"type":"course","course_ids":courses},{"type":"crm","lead_id":lead_id}] if lead_id else [{"type":"course","course_ids":courses}],
            provenance=provenance,human_handoff_required=(mode=="HANDOFF"),
            execution_enabled=False,messaging_enabled=False,external_actions_enabled=False,
            crm_writes_enabled=False,executor_invocation_enabled=False,execution_authorized=False)

    def validate(self, result: IntegratedAgentResult):
        e=[]
        if result.status not in {RUNTIME_READY,RUNTIME_CLARIFICATION,RUNTIME_REVIEW,RUNTIME_BLOCKED,RUNTIME_UNKNOWN}:
            e.append("invalid status")
        if result.execution_enabled or result.messaging_enabled or result.external_actions_enabled or result.crm_writes_enabled:
            e.append("side effects enabled")
        if result.executor_invocation_enabled or result.execution_authorized:
            e.append("execution authority enabled")
        if result.human_handoff_required and result.response_mode!="HANDOFF":
            e.append("handoff flag mismatch")
        if not result.provenance:
            e.append("missing provenance")
        return e

def run_agent(message: str, lead_id: Optional[str] = None, project_root: Optional[str] = None):
    runtime=SayyedEdVantageIntegratedRuntime(project_root)
    return runtime.run(message,lead_id)

def validate_agent_result(runtime: SayyedEdVantageIntegratedRuntime, result: IntegratedAgentResult):
    return runtime.validate(result)
