
import os,sys,copy
sys.path.insert(0,os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE28 import *

def check(n,c):
    if not c: raise AssertionError(n)
    print("PASS:",n)

for n in [PACKAGE_ACCEPTED,PACKAGE_CLARIFICATION,PACKAGE_REVIEW,PACKAGE_BLOCKED,PACKAGE_UNKNOWN,
          PACKAGE_ACCEPT,PACKAGE_CLARIFY,PACKAGE_REVIEW_DECISION,PACKAGE_BLOCK,PACKAGE_OBTAIN]:
    check("constant "+n,bool(n))
check("evidence dataclass",isinstance(EvidenceItem(1,"x",True,"T"),EvidenceItem))

final={"status":"AUDIT_ACCEPTED","decision":"AUDIT_ACCEPT_FINAL_BOUNDARY",
 "action":"APPLICATION","lead_id":"SE-00001","course_ids":["SE-DS-001"],
 "authorization_state":"GRANTED","audit_complete":True,"final_boundary_verified":True,
 "conflicts":[],"missing_requirements":[],"failed_checks":[],
 "entries":[
  {"sequence":1,"checkpoint":"lead","passed":True,"source":"FINAL_BOUNDARY"},
  {"sequence":2,"checkpoint":"course","passed":True,"source":"CRM_READ"},
  {"sequence":3,"checkpoint":"auth","passed":True,"source":"AUTHORIZATION"}]}
boundary={"status":"FINAL_HANDOFF_ACCEPTED","lead_id":"SE-00001","course_ids":["SE-DS-001"]}
integrity={"status":"HANDOFF_INTEGRITY_PASS"}
handoff={"status":"HANDOFF_READY"}

r=build_admission_evidence_package(final,final_boundary_result=boundary,
 integrity_result=integrity,handoff_result=handoff)
p=r.package
check("accepted",p.status==PACKAGE_ACCEPTED)
check("accept decision",p.decision==PACKAGE_ACCEPT)
check("action",p.action=="APPLICATION")
check("lead",p.lead_id=="SE-00001")
check("course",p.course_ids==["SE-DS-001"])
check("auth",p.authorization_state=="GRANTED")
check("complete",p.audit_complete)
check("verified",p.final_boundary_verified)
check("evidence count",p.evidence_count==3)
check("usable count",p.usable_evidence_count==3)
check("evidence order",[e.sequence for e in p.evidence]==[1,2,3])
check("no conflicts",p.conflicts==[])
check("no failed",p.failed_checks==[])
check("executor false",not p.executor_invocation_allowed)
check("execution false",not p.execution_authorized)
check("application false",not p.application_occurred)
check("payment false",not p.payment_occurred)
check("enrollment false",not p.enrollment_occurred)
check("CRM false",not p.crm_write_allowed)
check("message false",not p.message_send_allowed)
check("external false",not p.external_action_allowed)
check("validation clean",validate_admission_evidence_package(r)==[])

# Conflict precedence.
x=dict(final); x["course_ids"]=["SE-PY-001"]
rr=build_admission_evidence_package(x,final_boundary_result=boundary)
check("boundary conflict review",rr.package.status==PACKAGE_REVIEW)
check("conflict recorded",len(rr.package.conflicts)>0)
check("review required",rr.package.human_handoff_required)

x=dict(final); x["lead_id"]="SE-00002"
rr=build_admission_evidence_package(x,final_boundary_result=boundary)
check("lead conflict review",rr.package.status==PACKAGE_REVIEW)

# Upstream states.
for st,exp,dec in [
 ("AUDIT_REVIEW",PACKAGE_REVIEW,PACKAGE_REVIEW_DECISION),
 ("AUDIT_BLOCKED",PACKAGE_BLOCKED,PACKAGE_BLOCK),
 ("AUDIT_CLARIFICATION",PACKAGE_CLARIFICATION,PACKAGE_CLARIFY),
 ("AUDIT_UNKNOWN",PACKAGE_UNKNOWN,PACKAGE_OBTAIN)
]:
    x=dict(final); x["status"]=st; x["audit_complete"]=False; x["final_boundary_verified"]=False
    rr=build_admission_evidence_package(x)
    check("upstream "+st,rr.package.status==exp)
    check("decision "+st,rr.package.decision==dec)

# Failed audit checks must not be accepted.
x=dict(final); x["failed_checks"]=["bad_checkpoint"]
rr=build_admission_evidence_package(x)
check("failed checks not accepted",rr.package.status!=PACKAGE_ACCEPTED)
check("failed check retained","bad_checkpoint" in rr.package.failed_checks)

# Missing identity.
for fld,val in [("lead_id",None),("course_ids",[])]:
    x=dict(final); x[fld]=val
    rr=build_admission_evidence_package(x)
    check("missing "+fld+" not accepted",rr.package.status!=PACKAGE_ACCEPTED)

# Negative auth.
for auth in ["DENIED","REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    x=dict(final); x["authorization_state"]=auth
    rr=build_admission_evidence_package(x)
    check("auth "+auth+" not accepted",rr.package.status!=PACKAGE_ACCEPTED)
    check("auth "+auth+" execution false",not rr.package.execution_authorized)

# Evidence usability and counts.
x=dict(final); x["entries"]=[
 {"sequence":1,"checkpoint":"good","passed":True,"source":"T"},
 {"sequence":2,"checkpoint":"bad","passed":False,"source":"T"}]
x["failed_checks"]=["bad"]
rr=build_admission_evidence_package(x)
check("usable evidence count",rr.package.usable_evidence_count==1)
check("total evidence count",rr.package.evidence_count==2)

# Provenance.
check("audit provenance","AUDIT" in p.provenance)
check("boundary provenance","FINAL_BOUNDARY" in p.provenance)
check("integrity provenance","HANDOFF_INTEGRITY" in p.provenance)
check("handoff provenance","HANDOFF" in p.provenance)

# Defensive copy.
src=dict(final); src["course_ids"]=["SE-DS-001"]
rr=build_admission_evidence_package(src)
src["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.package.course_ids==["SE-DS-001"])

# Serialization.
d=admission_evidence_package_to_dict(r)
check("serialized package",isinstance(d["package"],dict))
check("serialized evidence",isinstance(d["package"]["evidence"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized validation",validate_serialized_admission_evidence_package(d)==[])

# Validator catches unsafe mutations.
for fld in ["executor_invocation_allowed","execution_authorized",
            "application_occurred","crm_write_allowed","message_send_allowed",
            "external_action_allowed"]:
    bad=copy.deepcopy(r); setattr(bad.package,fld,True)
    check("validator catches "+fld,len(validate_admission_evidence_package(bad))>0)

bad=copy.deepcopy(r); bad.package.conflicts=["x"]
check("validator catches accepted conflict",len(validate_admission_evidence_package(bad))>0)
bad=copy.deepcopy(r); bad.package.audit_complete=False
check("validator catches accepted incomplete",len(validate_admission_evidence_package(bad))>0)
bad=copy.deepcopy(r); bad.package.evidence_count=99
check("validator catches count mismatch",len(validate_admission_evidence_package(bad))>0)

rr=run_admission_evidence_package(final,final_boundary_result=boundary,
 integrity_result=integrity,handoff_result=handoff)
check("run wrapper",rr.package.status==PACKAGE_ACCEPTED)

print("\nAI CORE 28 TEST RESULT: ALL PASSED")
