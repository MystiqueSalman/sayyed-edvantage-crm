
import os, sys, copy
sys.path.insert(0, os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE25 import *

def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print("PASS:", name)

for n in [INTEGRITY_PASS,INTEGRITY_CLARIFICATION,INTEGRITY_REVIEW,
          INTEGRITY_BLOCKED,INTEGRITY_UNKNOWN,
          DECISION_ACCEPT_HANDOFF,DECISION_CLARIFY,DECISION_HUMAN_REVIEW,
          DECISION_BLOCK,DECISION_OBTAIN_STATE]:
    check("constant "+n, bool(n))
check("integrity check dataclass", isinstance(IntegrityCheck("x",True,"T"), IntegrityCheck))

ready = {
 "status":"HANDOFF_READY","mode":"PREPARE_HANDOFF","action":"APPLICATION",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],"crm_stage":"Application",
 "authorization_state":"GRANTED","readiness_status":"ACTION_READINESS_READY",
 "handoff_created":True,"missing_requirements":[],"human_handoff_required":False
}
readiness = {
 "status":"ACTION_READINESS_READY","proposed_action":"APPLICATION",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],
 "authorization_state":"GRANTED"
}
crm = {"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Application"}
auth = {"authorization_state":"GRANTED"}

r = build_handoff_integrity(ready, readiness_result=readiness,
                             crm_snapshot=crm, authorization=auth)
x = r.result
check("passing status",x.status==INTEGRITY_PASS)
check("accept decision",x.decision==DECISION_ACCEPT_HANDOFF)
check("action preserved",x.action=="APPLICATION")
check("lead preserved",x.lead_id=="SE-00001")
check("course preserved",x.course_ids==["SE-DS-001"])
check("auth preserved",x.authorization_state=="GRANTED")
check("handoff retained",x.handoff_created)
check("integrity verified",x.integrity_verified)
check("no conflicts",x.conflicts==[])
check("no missing",x.missing_requirements==[])
check("executor disabled",not x.executor_invocation_allowed)
check("execution false",not x.execution_authorized)
check("application false",not x.application_occurred)
check("payment false",not x.payment_occurred)
check("enrollment false",not x.enrollment_occurred)
check("CRM false",not x.crm_write_allowed)
check("message false",not x.message_send_allowed)
check("external false",not x.external_action_allowed)
check("validation clean",validate_handoff_integrity(r)==[])

check("readiness provenance","ACTION_READINESS" in x.provenance)
check("CRM provenance","CRM_READ" in x.provenance)
check("auth provenance","AUTHORIZATION" in x.provenance)

# Conflicts must become human review.
bad = dict(readiness); bad["course_ids"]=["SE-PY-001"]
rr = build_handoff_integrity(ready, readiness_result=bad, crm_snapshot=crm, authorization=auth)
check("course conflict review",rr.result.status==INTEGRITY_REVIEW)
check("course conflict recorded",any("course_ids" in c for c in rr.result.conflicts))
check("review handoff",rr.result.human_handoff_required)
check("review decision",rr.result.decision==DECISION_HUMAN_REVIEW)

bad = dict(readiness); bad["lead_id"]="SE-99999"
rr = build_handoff_integrity(ready, readiness_result=bad)
check("lead conflict review",rr.result.status==INTEGRITY_REVIEW)
check("lead conflict recorded",len(rr.result.conflicts)>0)

badcrm = dict(crm); badcrm["lead_id"]="SE-00002"
rr = build_handoff_integrity(ready, readiness_result=readiness, crm_snapshot=badcrm)
check("CRM conflict review",rr.result.status==INTEGRITY_REVIEW)
check("CRM conflict recorded",len(rr.result.conflicts)>0)

badauth = {"authorization_state":"REVOKED"}
rr = build_handoff_integrity(ready, readiness_result=readiness, authorization=badauth)
check("auth conflict review",rr.result.status==INTEGRITY_REVIEW)
check("auth conflict recorded",any("authorization" in c for c in rr.result.conflicts))

# Negative authorization without a conflicting source blocks.
for a in ["DENIED","REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    h = dict(ready); h["authorization_state"]=a
    rr = build_handoff_integrity(h)
    check("negative auth "+a+" not accepted",rr.result.status!=INTEGRITY_PASS)
    check("negative auth "+a+" no execution",not rr.result.execution_authorized)

# Upstream states.
for st, expected, decision in [
 ("HANDOFF_REVIEW",INTEGRITY_REVIEW,DECISION_HUMAN_REVIEW),
 ("HANDOFF_BLOCKED",INTEGRITY_BLOCKED,DECISION_BLOCK),
 ("HANDOFF_CLARIFICATION",INTEGRITY_CLARIFICATION,DECISION_CLARIFY),
 ("HANDOFF_UNKNOWN",INTEGRITY_UNKNOWN,DECISION_OBTAIN_STATE),
]:
    h=dict(ready); h["status"]=st; h["handoff_created"]=False
    rr=build_handoff_integrity(h)
    check("upstream "+st,rr.result.status==expected)
    check("upstream decision "+st,rr.result.decision==decision)
    check("upstream not created "+st,not rr.result.handoff_created)

# Missing core fields.
for field in ["lead_id","course_ids","action"]:
    h=dict(ready)
    if field=="lead_id": h[field]=None
    if field=="course_ids": h[field]=[]
    if field=="action": h[field]="NONE"
    rr=build_handoff_integrity(h)
    check("missing/invalid "+field+" not pass",rr.result.status!=INTEGRITY_PASS)

# Created=false cannot pass.
h=dict(ready); h["handoff_created"]=False
rr=build_handoff_integrity(h)
check("not-created handoff not pass",rr.result.status!=INTEGRITY_PASS)
check("not-created clarification",rr.result.decision==DECISION_CLARIFY)

# Missing CRM stage is recorded when CRM is supplied.
badcrm=dict(crm); badcrm.pop("stage")
rr=build_handoff_integrity(ready, readiness_result=readiness, crm_snapshot=badcrm, authorization=auth)
check("missing CRM stage recorded","verified CRM stage" in rr.result.missing_requirements)
check("missing CRM stage not pass",rr.result.status!=INTEGRITY_PASS)

# Defensive copy.
src=dict(ready); src["course_ids"]=["SE-DS-001"]
rr=build_handoff_integrity(src)
src["course_ids"].append("SE-PY-001")
check("defensive course copy",rr.result.course_ids==["SE-DS-001"])

# Serialization.
d=handoff_integrity_to_dict(r)
check("serialized result",isinstance(d["result"],dict))
check("serialized checks",isinstance(d["result"]["checks"],list))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized status",d["result"]["status"]==INTEGRITY_PASS)
check("serialized executor false",d["result"]["executor_invocation_allowed"] is False)
check("serialized validation",validate_serialized_handoff_integrity(d)==[])

# Validator catches unsafe mutation.
bad=copy.deepcopy(r); bad.result.executor_invocation_allowed=True
check("validator catches executor",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.execution_authorized=True
check("validator catches execution",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.application_occurred=True
check("validator catches occurrence",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.crm_write_allowed=True
check("validator catches CRM",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.message_send_allowed=True
check("validator catches message",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.external_action_allowed=True
check("validator catches external",len(validate_handoff_integrity(bad))>0)

# Validator catches invalid pass state.
bad=copy.deepcopy(r); bad.result.authorization_state="DENIED"
check("validator catches pass negative auth",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.handoff_created=False
check("validator catches pass not-created",len(validate_handoff_integrity(bad))>0)
bad=copy.deepcopy(r); bad.result.integrity_verified=False
check("validator catches pass not-verified",len(validate_handoff_integrity(bad))>0)

# Wrapper.
rr=run_handoff_integrity(ready, readiness_result=readiness,
                         crm_snapshot=crm, authorization=auth)
check("run wrapper",rr.result.status==INTEGRITY_PASS)

print("\nAI CORE 25 TEST RESULT: ALL PASSED")
