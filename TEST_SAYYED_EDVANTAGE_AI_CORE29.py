
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE29 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

for n in [ORCH_READY,ORCH_CLARIFICATION,ORCH_REVIEW,ORCH_BLOCKED,ORCH_UNKNOWN,
          DECISION_READY,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN]:
    check("constant "+n,bool(n))

package={"status":"EVIDENCE_PACKAGE_ACCEPTED","action":"APPLICATION",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],"authorization_state":"GRANTED",
 "audit_complete":True,"final_boundary_verified":True,"failed_checks":[],
 "conflicts":[],"missing_requirements":[],
 "evidence":[
  {"sequence":1,"checkpoint":"lead","passed":True,"usable":True,"source":"AUDIT"},
  {"sequence":2,"checkpoint":"course","passed":True,"usable":True,"source":"CRM_READ"}]}
audit={"status":"AUDIT_ACCEPTED","lead_id":"SE-00001","course_ids":["SE-DS-001"]}
boundary={"status":"FINAL_HANDOFF_ACCEPTED","lead_id":"SE-00001","course_ids":["SE-DS-001"]}
integrity={"status":"HANDOFF_INTEGRITY_PASS"}

r=build_orchestration_handoff(package,audit_result=audit,
 final_boundary_result=boundary,integrity_result=integrity)
h=r.handoff
check("ready",h.status==ORCH_READY)
check("decision",h.decision==DECISION_READY)
check("action",h.action=="APPLICATION")
check("lead",h.lead_id=="SE-00001")
check("course",h.course_ids==["SE-DS-001"])
check("package accepted",h.package_accepted)
check("auth",h.authorization_state=="GRANTED")
check("created",h.orchestration_handoff_created)
check("evidence count",h.evidence_count==2)
check("usable count",h.usable_evidence_count==2)
check("no conflicts",h.conflicts==[])
check("no failed",h.failed_checks==[])
check("executor false",not h.executor_invocation_allowed)
check("execution false",not h.execution_authorized)
check("application false",not h.application_occurred)
check("payment false",not h.payment_occurred)
check("enrollment false",not h.enrollment_occurred)
check("CRM false",not h.crm_write_allowed)
check("message false",not h.message_send_allowed)
check("external false",not h.external_action_allowed)
check("validation clean",validate_orchestration_handoff(r)==[])

# Source conflicts.
x=dict(audit); x["lead_id"]="SE-00002"
rr=build_orchestration_handoff(package,audit_result=x)
check("audit conflict review",rr.handoff.status==ORCH_REVIEW)
check("audit conflict recorded",len(rr.handoff.conflicts)>0)

x=dict(boundary); x["status"]="FINAL_HANDOFF_REVIEW"
rr=build_orchestration_handoff(package,final_boundary_result=x)
check("boundary conflict review",rr.handoff.status==ORCH_REVIEW)

x=dict(integrity); x["status"]="HANDOFF_INTEGRITY_REVIEW"
rr=build_orchestration_handoff(package,integrity_result=x)
check("integrity conflict review",rr.handoff.status==ORCH_REVIEW)

# Upstream package states.
for st,exp,dec in [
 ("EVIDENCE_PACKAGE_REVIEW",ORCH_REVIEW,DECISION_REVIEW),
 ("EVIDENCE_PACKAGE_BLOCKED",ORCH_BLOCKED,DECISION_BLOCK),
 ("EVIDENCE_PACKAGE_CLARIFICATION",ORCH_CLARIFICATION,DECISION_CLARIFY),
 ("EVIDENCE_PACKAGE_UNKNOWN",ORCH_UNKNOWN,DECISION_OBTAIN),
]:
    x=dict(package); x["status"]=st; x["audit_complete"]=False; x["final_boundary_verified"]=False
    rr=build_orchestration_handoff(x)
    check("upstream "+st,rr.handoff.status==exp)
    check("decision "+st,rr.handoff.decision==dec)
    check("not created "+st,not rr.handoff.orchestration_handoff_created)

# Failed checks.
x=dict(package); x["failed_checks"]=["bad"]
rr=build_orchestration_handoff(x)
check("failed checks review",rr.handoff.status==ORCH_REVIEW)
check("failed retained","bad" in rr.handoff.failed_checks)

# Missing identity.
for fld,val in [("lead_id",None),("course_ids",[])]:
    x=dict(package); x[fld]=val
    rr=build_orchestration_handoff(x)
    check("missing "+fld+" not ready",rr.handoff.status!=ORCH_READY)

# Negative auth.
for a in ["DENIED","REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    x=dict(package); x["authorization_state"]=a
    rr=build_orchestration_handoff(x)
    check("auth "+a+" not ready",rr.handoff.status!=ORCH_READY)
    check("auth "+a+" execution false",not rr.handoff.execution_authorized)

# Evidence sorting / usability.
x=dict(package); x["evidence"]=[
 {"sequence":2,"checkpoint":"bad","passed":False,"usable":False,"source":"T"},
 {"sequence":1,"checkpoint":"good","passed":True,"usable":True,"source":"T"}]
rr=build_orchestration_handoff(x)
check("evidence sorted",[e.sequence for e in rr.handoff.evidence]==[1,2])
check("usable count one",rr.handoff.usable_evidence_count==1)

# Provenance.
check("package provenance","EVIDENCE_PACKAGE" in h.provenance)
check("audit provenance","AUDIT" in h.provenance)
check("boundary provenance","FINAL_BOUNDARY" in h.provenance)
check("integrity provenance","HANDOFF_INTEGRITY" in h.provenance)

# Defensive copy.
src=dict(package); src["course_ids"]=["SE-DS-001"]
rr=build_orchestration_handoff(src)
src["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.handoff.course_ids==["SE-DS-001"])

# Serialization.
d=orchestration_handoff_to_dict(r)
check("serialized handoff",isinstance(d["handoff"],dict))
check("serialized evidence",isinstance(d["handoff"]["evidence"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized validation",validate_serialized_orchestration_handoff(d)==[])

# Validator catches unsafe mutations.
for fld in ["executor_invocation_allowed","execution_authorized",
            "application_occurred","crm_write_allowed","message_send_allowed",
            "external_action_allowed"]:
    bad=copy.deepcopy(r); setattr(bad.handoff,fld,True)
    check("validator catches "+fld,len(validate_orchestration_handoff(bad))>0)

bad=copy.deepcopy(r); bad.handoff.conflicts=["x"]
check("validator catches conflict",len(validate_orchestration_handoff(bad))>0)
bad=copy.deepcopy(r); bad.handoff.evidence_count=99
check("validator catches evidence count",len(validate_orchestration_handoff(bad))>0)
bad=copy.deepcopy(r); bad.handoff.orchestration_handoff_created=False
check("validator catches ready not created",len(validate_orchestration_handoff(bad))>0)

rr=run_orchestration_handoff(package,audit_result=audit,
 final_boundary_result=boundary,integrity_result=integrity)
check("run wrapper",rr.handoff.status==ORCH_READY)

print("\nAI CORE 29 TEST RESULT: ALL PASSED")
