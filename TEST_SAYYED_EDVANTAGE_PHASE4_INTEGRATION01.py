
import os,sys,tempfile,json,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_PHASE4_INTEGRATION01 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

root=tempfile.mkdtemp()
os.makedirs(os.path.join(root,"data"))
leads={"leads":[
 {"lead_id":"SE-00001","course_id":"SE-DS-001","region":"India","stage":"Interested"},
 {"lead_id":"SE-00002","course_id":"SE-PY-001","region":"India","stage":"New"}]}
with open(os.path.join(root,"data","leads.json"),"w",encoding="utf-8") as f: json.dump(leads,f)

rt=SayyedEdVantageIntegratedRuntime(root)
check("runtime safety execution off",not rt.execution_enabled)
check("runtime safety messaging off",not rt.messaging_enabled)
check("runtime safety external off",not rt.external_actions_enabled)
check("runtime safety CRM off",not rt.crm_writes_enabled)
check("runtime safety executor off",not rt.executor_invocation_enabled)
check("runtime no invention",rt.no_invention)
check("runtime fail closed",rt.fail_closed)

lead=rt.read_lead("SE-00001")
check("CRM read",lead["lead_id"]=="SE-00001")
lead["stage"]="Enrolled"
check("CRM defensive read",rt.read_lead("SE-00001")["stage"]=="Interested")
check("missing CRM safe",rt.read_lead("SE-99999")=={})

r=rt.run("What is the Data Science fee?", "SE-00001")
check("fee ready",r.status==RUNTIME_READY)
check("fee course",r.course_ids==["SE-DS-001"])
check("fee intent",r.intent=="commercial")
check("fee present","50,000" in r.response_text)
check("fee provenance","MASTER_KB" in r.provenance)

r=rt.run("Tell me about Python", "SE-00002")
check("CRM context course",r.course_ids==["SE-PY-001"])
check("program response",r.status==RUNTIME_READY)

r=rt.run("Which course is best for me?", "SE-00002")
check("recommendation clarification",r.status==RUNTIME_CLARIFICATION)
check("no silent course selection",r.course_ids==["SE-PY-001"])

r=rt.run("What are the Data Science fees and Python fees?")
check("multi-course clarification",r.status==RUNTIME_CLARIFICATION)
check("multi course preserved",set(r.course_ids)=={"SE-DS-001","SE-PY-001"})

r=rt.run("Will Data Science guarantee me a job?")
check("career safety",r.status==RUNTIME_READY)
check("no job guarantee","does not guarantee" in r.response_text)

r=rt.run("Is the Data Science certificate guaranteed?")
check("certification unknown safe",r.status==RUNTIME_READY)
check("certification not invented","not currently defined" in r.response_text)

r=rt.run("Give me the international Data Science fee")
# no lead: wording itself should not quote India
check("international no India fallback",r.status==RUNTIME_CLARIFICATION)
check("international safe", "International pricing" in r.response_text or "international" in r.response_text.lower())
check("international no India fee", "₹50,000" not in r.response_text)

r=rt.run("Can I get a discount on Data Science?", "SE-00001")
check("discount handoff",r.status==RUNTIME_REVIEW)
check("discount human handoff",r.human_handoff_required)

r=rt.run("", "SE-00001")
check("empty clarification",r.status==RUNTIME_CLARIFICATION)

r=rt.run("What is Linux?", "SE-99999")
check("invalid lead fail closed",r.status==RUNTIME_CLARIFICATION)
check("invalid lead error",bool(r.errors))

r=rt.run("Tell me about AI and Generative AI")
check("AI course detection",r.course_ids==["SE-AIGEN-001"])

r=rt.run("Tell me about DevOps")
check("DevOps detection",r.course_ids==["SE-DEVOPS-001"])

r=rt.run("Tell me about cybersecurity")
check("Cybersecurity detection",r.course_ids==["SE-EHC-001"])

r=rt.run("Tell me about Data Analytics")
check("Data Analytics detection",r.course_ids==["SE-DA-001"])

r=rt.run("Tell me about Linux")
check("Linux detection",r.course_ids==["SE-LINUX-001"])

r=rt.run("Tell me about Python")
check("Python detection",r.course_ids==["SE-PY-001"])

r=rt.run("Tell me about Data Science")
check("Data Science detection",r.course_ids==["SE-DS-001"])

check("result validation",rt.validate(r)==[])

# Validate catches unsafe mutation.
bad=copy.deepcopy(r); bad.execution_authorized=True
check("validator catches execution",bool(rt.validate(bad)))
bad=copy.deepcopy(r); bad.crm_writes_enabled=True
check("validator catches CRM write",bool(rt.validate(bad)))

# wrapper
r=run_agent("What is the Data Science fee?","SE-00001",root)
check("wrapper works",r.status==RUNTIME_READY)

print("\nPHASE 4 INTEGRATION 01 TEST RESULT: ALL PASSED")
