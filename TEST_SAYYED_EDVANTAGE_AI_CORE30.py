
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE30 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

for n in [CLOSURE_READY,CLOSURE_CLARIFICATION,CLOSURE_REVIEW,CLOSURE_BLOCKED,CLOSURE_UNKNOWN,
          DECISION_EXPOSE,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN]:
    check("constant "+n,bool(n))

orch={"status":"ORCHESTRATION_HANDOFF_READY","action":"APPLICATION",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],
 "authorization_state":"GRANTED","orchestration_handoff_created":True,
 "evidence_count":2,"usable_evidence_count":2,"failed_checks":[],"conflicts":[],
 "missing_requirements":[],"evidence":[
  {"sequence":1,"checkpoint":"lead","source":"AUDIT","passed":True,"usable":True},
  {"sequence":2,"checkpoint":"course","source":"CRM","passed":True,"usable":True}]}
pkg={"status":"EVIDENCE_PACKAGE_ACCEPTED","lead_id":"SE-00001",
     "course_ids":["SE-DS-001"],"authorization_state":"GRANTED"}
audit={"status":"AUDIT_ACCEPTED"}
boundary={"status":"FINAL_HANDOFF_ACCEPTED"}

r=build_unified_agent_boundary(orch,evidence_package_result=pkg,
                               audit_result=audit,final_boundary_result=boundary)
b=r.boundary
check("ready",b.status==CLOSURE_READY)
check("expose decision",b.decision==DECISION_EXPOSE)
check("action",b.action=="APPLICATION")
check("lead",b.lead_id=="SE-00001")
check("course",b.course_ids==["SE-DS-001"])
check("auth",b.authorization_state=="GRANTED")
check("handoff created",b.orchestration_handoff_created)
check("boundary ready",b.boundary_ready)
check("future executor input",b.future_executor_input_ready)
check("evidence count",b.evidence_count==2)
check("usable evidence",b.usable_evidence_count==2)
check("validation clean",validate_unified_agent_boundary(r)==[])

for fld,val,label in [
 ("lead_id","SE-00002","lead conflict"),
 ("course_ids",["SE-PY-001"],"course conflict"),
 ("authorization_state","DENIED","auth conflict")]:
    p=dict(pkg); p[fld]=val
    rr=build_unified_agent_boundary(orch,evidence_package_result=p)
    check(label+" review",rr.boundary.status==CLOSURE_REVIEW)

for st,exp,dec in [
 ("ORCHESTRATION_HANDOFF_REVIEW",CLOSURE_REVIEW,DECISION_REVIEW),
 ("ORCHESTRATION_HANDOFF_BLOCKED",CLOSURE_BLOCKED,DECISION_BLOCK),
 ("ORCHESTRATION_HANDOFF_CLARIFICATION",CLOSURE_CLARIFICATION,DECISION_CLARIFY),
 ("ORCHESTRATION_HANDOFF_UNKNOWN",CLOSURE_UNKNOWN,DECISION_OBTAIN)]:
    o=dict(orch); o["status"]=st; o["orchestration_handoff_created"]=False
    rr=build_unified_agent_boundary(o)
    check("upstream "+st,rr.boundary.status==exp)
    check("decision "+st,rr.boundary.decision==dec)
    check("not ready "+st,not rr.boundary.boundary_ready)

o=dict(orch); o["failed_checks"]=["checkpoint failure"]
rr=build_unified_agent_boundary(o)
check("failed checkpoint review",rr.boundary.status==CLOSURE_REVIEW)
check("failed retained","checkpoint failure" in rr.boundary.failed_checks)

for fld,val in [("lead_id",None),("course_ids",[])]:
    o=dict(orch); o[fld]=val
    rr=build_unified_agent_boundary(o)
    check("missing "+fld,rr.boundary.status!=CLOSURE_READY)

for a in ["DENIED","REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    o=dict(orch); o["authorization_state"]=a
    rr=build_unified_agent_boundary(o)
    check("negative auth "+a,rr.boundary.status!=CLOSURE_READY)
    check("negative auth execution "+a,not rr.boundary.execution_authorized)

o=dict(orch); o["evidence_count"]=0; o["usable_evidence_count"]=0; o["evidence"]=[]
rr=build_unified_agent_boundary(o)
check("no evidence clarification",rr.boundary.status==CLOSURE_CLARIFICATION)

# Provenance.
for src in ["ORCHESTRATION_HANDOFF","EVIDENCE_PACKAGE","AUDIT","FINAL_BOUNDARY"]:
    check("provenance "+src,src in b.provenance)

# Checkpoint sorting and usability.
o=dict(orch); o["evidence"]=[
 {"sequence":3,"checkpoint":"third","source":"T","passed":False,"usable":False},
 {"sequence":1,"checkpoint":"first","source":"T","passed":True,"usable":True},
 {"sequence":2,"checkpoint":"second","source":"T","passed":True,"usable":True}]
o["evidence_count"]=3; o["usable_evidence_count"]=2
rr=build_unified_agent_boundary(o)
check("checkpoint sorted",[x.sequence for x in rr.boundary.checkpoints]==[1,2,3])
check("checkpoint usable count",rr.boundary.usable_evidence_count==2)

# Defensive copies.
o2=dict(orch); o2["course_ids"]=["SE-DS-001"]
rr=build_unified_agent_boundary(o2)
o2["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.boundary.course_ids==["SE-DS-001"])

# Serialization.
d=unified_agent_boundary_to_dict(r)
check("serialized boundary",isinstance(d["boundary"],dict))
check("serialized checkpoints",isinstance(d["boundary"]["checkpoints"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized validation",validate_serialized_unified_agent_boundary(d)==[])

# Safety mutation tests.
for fld in ["execution_authorized","executor_invocation_allowed",
            "execution_enabled","messaging_enabled","external_actions_enabled",
            "crm_writes_enabled","application_occurred","payment_occurred",
            "enrollment_occurred"]:
    bad=copy.deepcopy(r); setattr(bad.boundary,fld,True)
    check("validator catches "+fld,len(validate_unified_agent_boundary(bad))>0)

bad=copy.deepcopy(r); bad.boundary.evidence_count=99
check("validator catches evidence count",len(validate_unified_agent_boundary(bad))>0)
bad=copy.deepcopy(r); bad.boundary.boundary_ready=False
check("validator catches ready flag",len(validate_unified_agent_boundary(bad))>0)
bad=copy.deepcopy(r); bad.boundary.provenance=[]
check("validator catches provenance",len(validate_unified_agent_boundary(bad))>0)

rr=run_unified_agent_boundary(orch,evidence_package_result=pkg,
                              audit_result=audit,final_boundary_result=boundary)
check("run wrapper",rr.boundary.status==CLOSURE_READY)

print("\nAI CORE 30 TEST RESULT: ALL PASSED")
