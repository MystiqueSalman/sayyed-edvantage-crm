
import os, sys, copy
sys.path.insert(0, os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE24 import *

def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print("PASS:", name)

# Constants/API
for n in [HANDOFF_APPLICATION,HANDOFF_PAYMENT,HANDOFF_ENROLLMENT,HANDOFF_NONE,
          STATUS_HANDOFF_READY,STATUS_HANDOFF_CLARIFICATION,STATUS_HANDOFF_REVIEW,
          STATUS_HANDOFF_BLOCKED,STATUS_HANDOFF_UNKNOWN,
          MODE_PREPARE,MODE_CLARIFY,MODE_REVIEW,MODE_BLOCK,MODE_OBTAIN_STATE]:
    check("constant "+n, bool(n))
check("handoff field dataclass", isinstance(HandoffField("x",1,"T"), HandoffField))

ready={
 "status":"ACTION_READINESS_READY","proposed_action":"APPLICATION",
 "lead_id":"SE-00001","course_ids":["SE-DS-001"],"crm_stage":"Application",
 "authorization_state":"GRANTED","missing_requirements":[],"human_handoff_required":False
}
r=build_admission_action_handoff(ready)
h=r.handoff
check("ready status",h.status==STATUS_HANDOFF_READY)
check("prepare mode",h.mode==MODE_PREPARE)
check("application action",h.action==HANDOFF_APPLICATION)
check("lead preserved",h.lead_id=="SE-00001")
check("course preserved",h.course_ids==["SE-DS-001"])
check("auth preserved",h.authorization_state=="GRANTED")
check("readiness preserved",h.readiness_status=="ACTION_READINESS_READY")
check("handoff created",h.handoff_created)
check("executor disabled",not h.executor_invocation_allowed)
check("execution false",not h.execution_authorized)
check("application false",not h.application_occurred)
check("payment false",not h.payment_occurred)
check("enrollment false",not h.enrollment_occurred)
check("CRM false",not h.crm_write_allowed)
check("message false",not h.message_send_allowed)
check("external false",not h.external_action_allowed)
check("validation clean",validate_admission_action_handoff(r)==[])

for st, expected_status, expected_mode in [
 ("ACTION_READINESS_CLARIFICATION",STATUS_HANDOFF_CLARIFICATION,MODE_CLARIFY),
 ("ACTION_READINESS_REVIEW",STATUS_HANDOFF_REVIEW,MODE_REVIEW),
 ("ACTION_READINESS_BLOCKED",STATUS_HANDOFF_BLOCKED,MODE_BLOCK),
 ("ACTION_READINESS_UNKNOWN",STATUS_HANDOFF_UNKNOWN,MODE_OBTAIN_STATE),
]:
    x=dict(ready); x["status"]=st; x["human_handoff_required"]=(st=="ACTION_READINESS_REVIEW")
    rr=build_admission_action_handoff(x)
    check("maps "+st,rr.handoff.status==expected_status)
    check("mode "+st,rr.handoff.mode==expected_mode)
    check("not created "+st,not rr.handoff.handoff_created)

x=dict(ready); x["authorization_state"]="DENIED"
rr=build_admission_action_handoff(x)
check("denied auth cannot create",not rr.handoff.handoff_created)
check("denied auth clarification",rr.handoff.status==STATUS_HANDOFF_CLARIFICATION)
check("denied auth missing requirement","explicit granted authorization" in rr.handoff.missing_requirements)

for auth in ["REVOKED","EXPIRED","UNKNOWN","REQUESTED"]:
    x=dict(ready); x["authorization_state"]=auth
    rr=build_admission_action_handoff(x)
    check("incomplete auth blocks creation "+auth,not rr.handoff.handoff_created)
    check("incomplete auth safe "+auth,not rr.handoff.executor_invocation_allowed)

x=dict(ready); x.pop("lead_id")
rr=build_admission_action_handoff(x)
check("missing lead clarification",rr.handoff.status==STATUS_HANDOFF_CLARIFICATION)
check("missing lead listed","verified lead_id" in rr.handoff.missing_requirements)

x=dict(ready); x["course_ids"]=[]
rr=build_admission_action_handoff(x)
check("missing course clarification",rr.handoff.status==STATUS_HANDOFF_CLARIFICATION)
check("missing course listed","verified course_id" in rr.handoff.missing_requirements)

x=dict(ready); x["human_handoff_required"]=True; x["status"]="ACTION_READINESS_REVIEW"
rr=build_admission_action_handoff(x)
check("review handoff required",rr.handoff.human_handoff_required)
check("review mode",rr.handoff.mode==MODE_REVIEW)

rr=build_admission_action_handoff(ready,response_turn={"status":"TURN_READY"},crm_snapshot={"lead_id":"SE-00001"})
check("agent provenance","AGENT_TURN" in rr.handoff.provenance)
check("CRM provenance","CRM_READ" in rr.handoff.provenance)
check("readiness provenance","ACTION_READINESS" in rr.handoff.provenance)

original=copy.deepcopy(ready)
rr=build_admission_action_handoff(original)
original["lead_id"]="CHANGED"; original["course_ids"].append("SE-PY-001")
check("defensive lead copy",rr.handoff.lead_id=="SE-00001")
check("defensive course copy",rr.handoff.course_ids==["SE-DS-001"])

check("fields present",len(rr.handoff.fields)>=5)
check("field verification",all(f.verified for f in rr.handoff.fields))
check("required action field",any(f.field=="action" and f.required for f in rr.handoff.fields))
check("required auth field",any(f.field=="authorization_state" and f.required for f in rr.handoff.fields))

d=admission_action_handoff_to_dict(rr)
check("serialized handoff",isinstance(d["handoff"],dict))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized status",d["handoff"]["status"]==rr.handoff.status)
check("serialized executor false",d["handoff"]["executor_invocation_allowed"] is False)
check("serialized execution false",d["handoff"]["execution_authorized"] is False)
check("serialized validation",validate_serialized_admission_action_handoff(d)==[])

bad=copy.deepcopy(rr); bad.handoff.executor_invocation_allowed=True
check("validator catches executor",len(validate_admission_action_handoff(bad))>0)
bad=copy.deepcopy(rr); bad.handoff.execution_authorized=True
check("validator catches execution",len(validate_admission_action_handoff(bad))>0)
bad=copy.deepcopy(rr); bad.handoff.handoff_created=False
check("validator catches ready not created",len(validate_admission_action_handoff(bad))>0)

bad=copy.deepcopy(rr); bad.handoff.application_occurred=True
check("validator catches occurrence",len(validate_admission_action_handoff(bad))>0)
bad=copy.deepcopy(rr); bad.handoff.crm_write_allowed=True
check("validator catches CRM write",len(validate_admission_action_handoff(bad))>0)
bad=copy.deepcopy(rr); bad.handoff.message_send_allowed=True
check("validator catches message send",len(validate_admission_action_handoff(bad))>0)
bad=copy.deepcopy(rr); bad.handoff.external_action_allowed=True
check("validator catches external",len(validate_admission_action_handoff(bad))>0)

rr2=run_admission_action_handoff(ready)
check("run wrapper",rr2.handoff.status==STATUS_HANDOFF_READY)

print("\nAI CORE 24 TEST RESULT: ALL PASSED")
