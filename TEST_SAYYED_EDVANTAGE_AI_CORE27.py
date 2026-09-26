
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE27 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

for n in [AUDIT_ACCEPTED,AUDIT_CLARIFICATION,AUDIT_REVIEW,AUDIT_BLOCKED,AUDIT_UNKNOWN,
          DECISION_AUDIT_ACCEPT,DECISION_AUDIT_CLARIFY,DECISION_AUDIT_REVIEW,
          DECISION_AUDIT_BLOCK,DECISION_AUDIT_OBTAIN]:
    check("constant "+n,bool(n))
check("entry dataclass",isinstance(AuditEntry(1,"x","S",True,"T"),AuditEntry))

final={"status":"FINAL_HANDOFF_ACCEPTED","decision":"ACCEPT_FINAL_BOUNDARY",
 "action":"APPLICATION","lead_id":"SE-00001","course_ids":["SE-DS-001"],
 "authorization_state":"GRANTED","final_boundary_verified":True,"handoff_created":True,
 "conflicts":[],"missing_requirements":[],"checks":[
   {"name":"core","passed":True,"source":"FINAL_BOUNDARY","detail":"ok"}
 ]}
integrity={"status":"HANDOFF_INTEGRITY_PASS","integrity_verified":True}
handoff={"status":"HANDOFF_READY","lead_id":"SE-00001","course_ids":["SE-DS-001"],
         "authorization_state":"GRANTED"}
readiness={"status":"ACTION_READINESS_READY","lead_id":"SE-00001",
           "course_ids":["SE-DS-001"]}
crm={"lead_id":"SE-00001","course_id":"SE-DS-001"}
auth={"authorization_state":"GRANTED"}

r=build_admission_action_audit(final,integrity_result=integrity,
 handoff_result=handoff,readiness_result=readiness,crm_snapshot=crm,authorization=auth)
a=r.audit
check("accepted audit",a.status==AUDIT_ACCEPTED)
check("accept decision",a.decision==DECISION_AUDIT_ACCEPT)
check("complete",a.audit_complete)
check("verified",a.final_boundary_verified)
check("lead",a.lead_id=="SE-00001")
check("course",a.course_ids==["SE-DS-001"])
check("auth",a.authorization_state=="GRANTED")
check("no failed checks",a.failed_checks==[])
check("no conflicts",a.conflicts==[])
check("entries",len(a.entries)>=10)
check("sequence starts one",a.entries[0].sequence==1)
check("provenance final","FINAL_BOUNDARY" in a.provenance)
check("provenance integrity","HANDOFF_INTEGRITY" in a.provenance)
check("provenance handoff","HANDOFF" in a.provenance)
check("provenance readiness","ACTION_READINESS" in a.provenance)
check("provenance CRM","CRM_READ" in a.provenance)
check("provenance auth","AUTHORIZATION" in a.provenance)
check("executor false",not a.executor_invocation_allowed)
check("execution false",not a.execution_authorized)
check("application false",not a.application_occurred)
check("payment false",not a.payment_occurred)
check("enrollment false",not a.enrollment_occurred)
check("CRM false",not a.crm_write_allowed)
check("message false",not a.message_send_allowed)
check("external false",not a.external_action_allowed)
check("validation clean",validate_admission_action_audit(r)==[])

# Conflicts.
x=dict(readiness); x["course_ids"]=["SE-PY-001"]
rr=build_admission_action_audit(final,readiness_result=x)
check("course source conflict review",rr.audit.status==AUDIT_REVIEW)
check("conflict recorded",len(rr.audit.conflicts)>0)
check("review required",rr.audit.human_handoff_required)

x=dict(crm); x["lead_id"]="SE-00002"
rr=build_admission_action_audit(final,crm_snapshot=x)
check("CRM conflict review",rr.audit.status==AUDIT_REVIEW)

rr=build_admission_action_audit(final,authorization={"authorization_state":"REVOKED"})
check("auth conflict review",rr.audit.status==AUDIT_REVIEW)

# Upstream final states.
for st,exp,dec in [
 ("FINAL_HANDOFF_REVIEW",AUDIT_REVIEW,DECISION_AUDIT_REVIEW),
 ("FINAL_HANDOFF_BLOCKED",AUDIT_BLOCKED,DECISION_AUDIT_BLOCK),
 ("FINAL_HANDOFF_CLARIFICATION",AUDIT_CLARIFICATION,DECISION_AUDIT_CLARIFY),
 ("FINAL_HANDOFF_UNKNOWN",AUDIT_UNKNOWN,DECISION_AUDIT_OBTAIN)
]:
    x=dict(final); x["status"]=st; x["final_boundary_verified"]=False; x["handoff_created"]=False
    rr=build_admission_action_audit(x)
    check("upstream "+st,rr.audit.status==exp)
    check("decision "+st,rr.audit.decision==dec)
    check("not complete "+st,not rr.audit.audit_complete)

# Missing/failed checks.
x=dict(final); x["lead_id"]=None
rr=build_admission_action_audit(x)
check("missing lead not accepted",rr.audit.status!=AUDIT_ACCEPTED)

x=dict(final); x["course_ids"]=[]
rr=build_admission_action_audit(x)
check("missing course not accepted",rr.audit.status!=AUDIT_ACCEPTED)

x=dict(final); x["checks"]=[{"name":"bad","passed":False,"source":"TEST"}]
rr=build_admission_action_audit(x)
check("failed check review",rr.audit.status==AUDIT_REVIEW)
check("failed check recorded","bad" in rr.audit.failed_checks)

# Defensive copy.
src=dict(final); src["course_ids"]=["SE-DS-001"]
rr=build_admission_action_audit(src)
src["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.audit.course_ids==["SE-DS-001"])

d=admission_action_audit_to_dict(r)
check("serialized audit",isinstance(d["audit"],dict))
check("serialized entries",isinstance(d["audit"]["entries"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized validation",validate_serialized_admission_action_audit(d)==[])

for fld in ["executor_invocation_allowed","execution_authorized",
            "application_occurred","crm_write_allowed","message_send_allowed",
            "external_action_allowed"]:
    bad=copy.deepcopy(r); setattr(bad.audit,fld,True)
    check("validator catches "+fld,len(validate_admission_action_audit(bad))>0)

bad=copy.deepcopy(r); bad.audit.conflicts=["x"]
check("validator catches accepted conflict",len(validate_admission_action_audit(bad))>0)
bad=copy.deepcopy(r); bad.audit.audit_complete=False
check("validator catches incomplete accepted",len(validate_admission_action_audit(bad))>0)

rr=run_admission_action_audit(final,integrity_result=integrity,
 handoff_result=handoff,readiness_result=readiness,crm_snapshot=crm,authorization=auth)
check("run wrapper",rr.audit.status==AUDIT_ACCEPTED)

print("\nAI CORE 27 TEST RESULT: ALL PASSED")
