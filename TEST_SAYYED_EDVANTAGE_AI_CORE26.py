
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE26 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

for n in [FINAL_ACCEPTED,FINAL_CLARIFICATION,FINAL_REVIEW,FINAL_BLOCKED,FINAL_UNKNOWN,
          DECISION_ACCEPT,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN]:
    check("constant "+n,bool(n))
check("check dataclass",isinstance(FinalizationCheck("x",True,"T"),FinalizationCheck))

integrity={"status":"HANDOFF_INTEGRITY_PASS","decision":"ACCEPT_HANDOFF_BOUNDARY",
 "action":"APPLICATION","lead_id":"SE-00001","course_ids":["SE-DS-001"],
 "authorization_state":"GRANTED","integrity_verified":True,"handoff_created":True,
 "conflicts":[],"missing_requirements":[]}
handoff={"status":"HANDOFF_READY","action":"APPLICATION","lead_id":"SE-00001",
 "course_ids":["SE-DS-001"],"authorization_state":"GRANTED","handoff_created":True}
readiness={"status":"ACTION_READINESS_READY","lead_id":"SE-00001",
 "course_ids":["SE-DS-001"],"authorization_state":"GRANTED"}
crm={"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Application"}
auth={"authorization_state":"GRANTED"}

r=build_final_admission_boundary(integrity,handoff_result=handoff,
 readiness_result=readiness,crm_snapshot=crm,authorization=auth)
b=r.boundary
check("accepted status",b.status==FINAL_ACCEPTED)
check("accept decision",b.decision==DECISION_ACCEPT)
check("action preserved",b.action=="APPLICATION")
check("lead preserved",b.lead_id=="SE-00001")
check("course preserved",b.course_ids==["SE-DS-001"])
check("auth preserved",b.authorization_state=="GRANTED")
check("integrity verified",b.integrity_verified)
check("final verified",b.final_boundary_verified)
check("handoff created",b.handoff_created)
check("no conflicts",b.conflicts==[])
check("no missing",b.missing_requirements==[])
check("executor false",not b.executor_invocation_allowed)
check("execution false",not b.execution_authorized)
check("application false",not b.application_occurred)
check("payment false",not b.payment_occurred)
check("enrollment false",not b.enrollment_occurred)
check("CRM false",not b.crm_write_allowed)
check("message false",not b.message_send_allowed)
check("external false",not b.external_action_allowed)
check("validation clean",validate_final_admission_boundary(r)==[])

check("handoff provenance","HANDOFF" in b.provenance)
check("readiness provenance","ACTION_READINESS" in b.provenance)
check("CRM provenance","CRM_READ" in b.provenance)
check("auth provenance","AUTHORIZATION" in b.provenance)

# Material conflicts -> review.
x=dict(readiness); x["course_ids"]=["SE-PY-001"]
rr=build_final_admission_boundary(integrity,readiness_result=x)
check("course conflict review",rr.boundary.status==FINAL_REVIEW)
check("course conflict recorded",len(rr.boundary.conflicts)>0)
check("review required",rr.boundary.human_handoff_required)
check("review decision",rr.boundary.decision==DECISION_REVIEW)

x=dict(integrity); x["lead_id"]="SE-99999"
rr=build_final_admission_boundary(x,handoff_result=handoff)
check("handoff lead conflict review",rr.boundary.status==FINAL_REVIEW)

# Upstream integrity states.
for st,exp,dec in [
 ("HANDOFF_INTEGRITY_REVIEW",FINAL_REVIEW,DECISION_REVIEW),
 ("HANDOFF_INTEGRITY_BLOCKED",FINAL_BLOCKED,DECISION_BLOCK),
 ("HANDOFF_INTEGRITY_CLARIFICATION",FINAL_CLARIFICATION,DECISION_CLARIFY),
 ("HANDOFF_INTEGRITY_UNKNOWN",FINAL_UNKNOWN,DECISION_OBTAIN)
]:
    x=dict(integrity); x["status"]=st; x["handoff_created"]=False; x["integrity_verified"]=False
    rr=build_final_admission_boundary(x)
    check("upstream "+st,rr.boundary.status==exp)
    check("decision "+st,rr.boundary.decision==dec)
    check("not created "+st,not rr.boundary.handoff_created)

# Negative/unknown authorization cannot pass.
for a in ["DENIED","REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    x=dict(integrity); x["authorization_state"]=a
    rr=build_final_admission_boundary(x)
    check("auth "+a+" not accepted",rr.boundary.status!=FINAL_ACCEPTED)
    check("auth "+a+" execution false",not rr.boundary.execution_authorized)

# Missing core data.
for fld,val in [("lead_id",None),("course_ids",[])]:
    x=dict(integrity); x[fld]=val
    rr=build_final_admission_boundary(x)
    check("missing "+fld+" not accepted",rr.boundary.status!=FINAL_ACCEPTED)

# Handoff mismatch.
x=dict(handoff); x["lead_id"]="SE-00002"
rr=build_final_admission_boundary(integrity,handoff_result=x)
check("handoff mismatch review",rr.boundary.status==FINAL_REVIEW)
check("handoff mismatch recorded",len(rr.boundary.conflicts)>0)

# CRM mismatch.
x=dict(crm); x["course_id"]="SE-PY-001"
rr=build_final_admission_boundary(integrity,crm_snapshot=x)
check("CRM mismatch review",rr.boundary.status==FINAL_REVIEW)

# Authorization source mismatch.
rr=build_final_admission_boundary(integrity,authorization={"authorization_state":"REVOKED"})
check("auth source mismatch review",rr.boundary.status==FINAL_REVIEW)

# Accepted requires created + verified.
for fld,val in [("handoff_created",False),("integrity_verified",False)]:
    x=dict(integrity); x[fld]=val
    rr=build_final_admission_boundary(x)
    check("invalid accepted flag "+fld,rr.boundary.status!=FINAL_ACCEPTED)

# Defensive copy.
src=dict(integrity); src["course_ids"]=["SE-DS-001"]
rr=build_final_admission_boundary(src)
src["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.boundary.course_ids==["SE-DS-001"])

# Serialization.
d=final_admission_boundary_to_dict(r)
check("serialized boundary",isinstance(d["boundary"],dict))
check("serialized checks",isinstance(d["boundary"]["checks"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized accepted",d["boundary"]["status"]==FINAL_ACCEPTED)
check("serialized executor false",d["boundary"]["executor_invocation_allowed"] is False)
check("serialized validation",validate_serialized_final_admission_boundary(d)==[])

# Validator safety mutations.
for fld in ["executor_invocation_allowed","execution_authorized",
            "application_occurred","crm_write_allowed","message_send_allowed",
            "external_action_allowed"]:
    bad=copy.deepcopy(r); setattr(bad.boundary,fld,True)
    check("validator catches "+fld,len(validate_final_admission_boundary(bad))>0)

bad=copy.deepcopy(r); bad.boundary.authorization_state="DENIED"
check("validator catches negative auth",len(validate_final_admission_boundary(bad))>0)
bad=copy.deepcopy(r); bad.boundary.conflicts=["conflict"]
check("validator catches accepted conflict",len(validate_final_admission_boundary(bad))>0)

rr=run_final_admission_boundary(integrity,handoff_result=handoff,
 readiness_result=readiness,crm_snapshot=crm,authorization=auth)
check("run wrapper",rr.boundary.status==FINAL_ACCEPTED)

print("\nAI CORE 26 TEST RESULT: ALL PASSED")
