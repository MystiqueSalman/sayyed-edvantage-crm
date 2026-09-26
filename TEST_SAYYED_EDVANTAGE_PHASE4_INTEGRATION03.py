
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_PHASE4_INTEGRATION03 import *
def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

decision={"status":"CONTEXT_DECISION_READY","mode":"RESPOND","session_id":"S1",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],"intent":"commercial",
 "response_text":"The verified Indian base fee for Data Science is ₹50,000.",
 "provenance":["CRM_READ","DECISION_PIPELINE","MASTER_KB"],
 "evidence":[{"course_ids":["SE-DS-001"],"intent":"commercial"}]}
integrated={"status":"INTEGRATED_RUNTIME_READY","lead_id":"SE-00001","course_ids":["SE-DS-001"]}
crm={"lead_id":"SE-00001","course_ids":["SE-DS-001"]}

r=build_response_orchestration(decision,integrated_result=integrated,crm_snapshot=crm)
check("ready",r.status==STATUS_READY)
check("respond mode",r.mode==MODE_RESPOND)
check("response allowed",r.response_allowed)
check("text preserved","₹50,000" in r.response_text)
check("session",r.session_id=="S1")
check("lead",r.lead_id=="SE-00001")
check("course",r.course_ids==["SE-DS-001"])
check("intent",r.intent=="commercial")
check("evidence",len(r.evidence)==1)
check("validation",validate_response_orchestration(r)==[])

for obj,label in [
 ({"status":"INTEGRATED_RUNTIME_REVIEW","lead_id":"SE-00001","course_ids":["SE-DS-001"]},"integrated review"),
 ({"status":"INTEGRATED_RUNTIME_BLOCKED","lead_id":"SE-00001","course_ids":["SE-DS-001"]},"integrated blocked")]:
    rr=build_response_orchestration(decision,integrated_result=obj)
    check(label+" review",rr.status==STATUS_REVIEW)

for st,mode,exp in [
 ("CONTEXT_DECISION_CLARIFICATION","CLARIFY",STATUS_CLARIFY),
 ("CONTEXT_DECISION_REVIEW","HUMAN_REVIEW",STATUS_REVIEW),
 ("CONTEXT_DECISION_UNKNOWN","OBTAIN_STATE",STATUS_UNKNOWN)]:
    d=dict(decision); d["status"]=st; d["mode"]=mode
    rr=build_response_orchestration(d)
    check("upstream "+st,rr.status==exp)
    check("no response "+st,rr.response_text=="")
    check("not allowed "+st,not rr.response_allowed)

# identity conflicts
x=dict(integrated); x["lead_id"]="SE-00002"
rr=build_response_orchestration(decision,integrated_result=x)
check("lead conflict",rr.status==STATUS_REVIEW); check("conflict recorded",bool(rr.conflicts))
x=dict(integrated); x["course_ids"]=["SE-PY-001"]
rr=build_response_orchestration(decision,integrated_result=x)
check("course conflict",rr.status==STATUS_REVIEW)

x=dict(crm); x["lead_id"]="SE-00002"
rr=build_response_orchestration(decision,crm_snapshot=x)
check("CRM lead conflict",rr.status==STATUS_REVIEW)

# Unknown upstream falls closed.
rr=build_response_orchestration({"status":"SOMETHING_ELSE","mode":"RESPOND","session_id":"X",
 "lead_id":None,"course_ids":[],"intent":"unknown","response_text":"unsafe",
 "provenance":["X"]})
check("unknown upstream blocked",rr.status==STATUS_BLOCKED)
check("unknown upstream no response",rr.response_text=="")
check("unknown upstream not allowed",not rr.response_allowed)

# Human handoff.
d=dict(decision); d["mode"]="HUMAN_REVIEW"
rr=build_response_orchestration(d)
check("human mode review",rr.status==STATUS_REVIEW)
check("human flag",rr.human_handoff_required)

# Provenance integration.
check("integrated provenance","INTEGRATED_RUNTIME" in r.provenance)
check("CRM provenance","CRM_READ" in r.provenance)

# Defensive evidence copy.
src=dict(decision); src["evidence"]=[{"a":1}]
rr=build_response_orchestration(src)
src["evidence"][0]["a"]=9
check("evidence defensive copy",rr.evidence[0]["a"]==1)

# serialization
d=response_orchestration_to_dict(r)
check("serialized",isinstance(d["response"],dict))
check("serialized validation",validate_serialized_response_orchestration(d)==[])

# safety mutation validation
for fld in ["execution_enabled","messaging_enabled","external_actions_enabled",
            "crm_writes_enabled","executor_invocation_enabled","execution_authorized"]:
    bad=copy.deepcopy(r); setattr(bad,fld,True)
    check("validator catches "+fld,bool(validate_response_orchestration(bad)))

bad=copy.deepcopy(r); bad.response_allowed=False
check("validator catches response flag",bool(validate_response_orchestration(bad)))
bad=copy.deepcopy(r); bad.response_text=""
check("validator catches missing text",bool(validate_response_orchestration(bad)))
bad=copy.deepcopy(r); bad.provenance=[]
check("validator catches provenance",bool(validate_response_orchestration(bad)))

rr=run_response_orchestration(decision,integrated_result=integrated,crm_snapshot=crm)
check("wrapper",rr.status==STATUS_READY)

print("\nPHASE 4 INTEGRATION 03 TEST RESULT: ALL PASSED")
