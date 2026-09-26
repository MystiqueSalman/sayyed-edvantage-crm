
import os, sys, copy
sys.path.insert(0, os.path.dirname(__file__))
from Sayyed_EdVantage_AI_CORE23 import *

def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print("PASS:", name)

# API/constants
for n in [ACTION_APPLICATION,ACTION_PAYMENT,ACTION_ENROLLMENT,ACTION_NONE,
          STATUS_READY,STATUS_CLARIFICATION,STATUS_REVIEW,STATUS_BLOCKED,STATUS_UNKNOWN,
          DECISION_PREPARE,DECISION_CLARIFY,DECISION_REVIEW,DECISION_BLOCK,DECISION_OBTAIN_STATE]:
    check("constant "+n, bool(n))
check("dataclass evidence", isinstance(ActionReadinessEvidence("x",1,"TEST"), ActionReadinessEvidence))
check("dataclass result", isinstance(AdmissionActionReadinessResult(AdmissionActionReadiness(
    STATUS_UNKNOWN,DECISION_OBTAIN_STATE,ACTION_NONE,None,[],None,AUTH_UNKNOWN,"x"
)), AdmissionActionReadinessResult))

base_crm={"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Application","region":"India"}
base_journey={"status":"JOURNEY_APPLICATION","lead_id":"SE-00001","course_ids":["SE-DS-001"],
              "crm_stage":"Application","human_handoff_required":False,"clarification_questions":[]}

r=build_admission_action_readiness(base_journey,base_crm,{"authorization_state":"GRANTED"}, {"status":"COMMERCIAL_READY"})
p=r.plan
check("application action detected",p.proposed_action==ACTION_APPLICATION)
check("ready with all required state",p.status==STATUS_READY)
check("prepare decision",p.decision==DECISION_PREPARE)
check("lead preserved",p.lead_id=="SE-00001")
check("course preserved",p.course_ids==["SE-DS-001"])
check("auth granted recognized",p.authorization_state==AUTH_GRANTED)
check("no missing requirements",p.missing_requirements==[])
check("no handoff",not p.human_handoff_required)
check("execution false",not p.execution_authorized)
check("application occurrence false",not p.application_occurred)
check("payment occurrence false",not p.payment_occurred)
check("enrollment occurrence false",not p.enrollment_occurred)
check("CRM writes false",not p.crm_write_allowed)
check("messaging false",not p.message_send_allowed)
check("external actions false",not p.external_action_allowed)
check("safety execution false",r.safety["execution_enabled"] is False)
check("safety messaging false",r.safety["messaging_enabled"] is False)
check("safety external false",r.safety["external_actions_enabled"] is False)
check("safety CRM false",r.safety["crm_writes_enabled"] is False)
check("no invention",r.safety["no_invention"] is True)
check("fail closed",r.safety["fail_closed"] is True)
check("validation clean",validate_admission_action_readiness(r)==[])

r2=build_admission_action_readiness(base_journey,base_crm,None,{"status":"COMMERCIAL_READY"})
check("missing auth not ready",r2.plan.status==STATUS_CLARIFICATION)
check("missing auth listed","explicit granted authorization" in r2.plan.missing_requirements)
check("clarification decision",r2.plan.decision==DECISION_CLARIFY)

for a in [AUTH_DENIED,AUTH_REVOKED,AUTH_EXPIRED]:
    rr=build_admission_action_readiness(base_journey,base_crm,{"authorization_state":a},{"status":"COMMERCIAL_READY"})
    check("negative auth blocked "+a,rr.plan.status==STATUS_BLOCKED)
    check("negative auth decision "+a,rr.plan.decision==DECISION_BLOCK)
    check("negative auth no prepare "+a,rr.plan.decision!=DECISION_PREPARE)

for a in [AUTH_UNKNOWN,AUTH_REQUESTED]:
    rr=build_admission_action_readiness(base_journey,base_crm,{"authorization_state":a},{"status":"COMMERCIAL_READY"})
    check("incomplete auth clarification "+a,rr.plan.status==STATUS_CLARIFICATION)
    check("incomplete auth safe "+a,not rr.plan.execution_authorized)

crm=dict(base_crm); crm.pop("lead_id")
jour=dict(base_journey); jour.pop("lead_id")
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("missing lead obtains state",rr.plan.status==STATUS_UNKNOWN)
check("missing lead named","verified lead_id" in rr.plan.missing_requirements)

crm=dict(base_crm); crm.pop("course_id")
jour=dict(base_journey); jour["course_ids"]=[]
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("missing course obtains state",rr.plan.status==STATUS_UNKNOWN)
check("missing course named","verified course_id" in rr.plan.missing_requirements)

crm=dict(base_crm); crm["stage"]="Payment Pending"
jour=dict(base_journey); jour["status"]="JOURNEY_PAYMENT"; jour["crm_stage"]="Payment Pending"
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},None)
check("payment detected",rr.plan.proposed_action==ACTION_PAYMENT)
check("payment commercial verification required",rr.plan.status==STATUS_CLARIFICATION)
check("payment detail named","verified commercial/payment details" in rr.plan.missing_requirements)

rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("payment ready with commercial evidence",rr.plan.status==STATUS_READY)
check("payment prepare",rr.plan.decision==DECISION_PREPARE)

crm=dict(base_crm); crm["stage"]="Enrolled"
jour=dict(base_journey); jour["status"]="JOURNEY_ENROLLMENT"; jour["crm_stage"]="Enrolled"
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("enrollment detected",rr.plan.proposed_action==ACTION_ENROLLMENT)
check("enrollment ready",rr.plan.status==STATUS_READY)

crm=dict(base_crm); crm["stage"]="Interested"
jour=dict(base_journey); jour["status"]="JOURNEY_INTERESTED"; jour["crm_stage"]="Interested"
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("interested blocks action",rr.plan.status==STATUS_BLOCKED)
check("interested no action",rr.plan.decision==DECISION_BLOCK)
check("interested action none",rr.plan.proposed_action==ACTION_NONE)

jour=dict(base_journey); jour["status"]="JOURNEY_REVIEW"; jour["human_handoff_required"]=True
rr=build_admission_action_readiness(jour,base_crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("review wins",rr.plan.status==STATUS_REVIEW)
check("review decision",rr.plan.decision==DECISION_REVIEW)
check("review handoff",rr.plan.human_handoff_required)

jour=dict(base_journey); jour["status"]="JOURNEY_CLARIFICATION"; jour["clarification_questions"]=["Confirm course"]
rr=build_admission_action_readiness(jour,base_crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("journey clarification",rr.plan.status==STATUS_CLARIFICATION)
check("question preserved",rr.plan.clarification_questions==["Confirm course"])

jour=dict(base_journey); jour["status"]="JOURNEY_UNKNOWN"; jour["clarification_questions"]=[]
rr=build_admission_action_readiness(jour,base_crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("journey unknown",rr.plan.status==STATUS_UNKNOWN)
check("unknown asks state",rr.plan.decision==DECISION_OBTAIN_STATE)
check("unknown gets safe question",len(rr.plan.clarification_questions)==1)

crm={"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Application"}
jour={"status":"JOURNEY_APPLICATION","lead_id":"SE-00001","course_ids":["SE-DS-001"]}
rr=build_admission_action_readiness(jour,crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
crm["lead_id"]="MUTATED"; jour["course_ids"].append("SE-PY-001")
check("defensive lead copy",rr.plan.lead_id=="SE-00001")
check("defensive course copy",rr.plan.course_ids==["SE-DS-001"])

check("provenance journey","ADMISSION_JOURNEY" in rr.plan.provenance)
check("provenance CRM","CRM_READ" in rr.plan.provenance)
check("provenance auth","AUTHORIZATION" in rr.plan.provenance)
check("provenance commercial","COMMERCIAL_CONVERSATION" in rr.plan.provenance)

d=admission_action_readiness_to_dict(rr)
check("serialized plan",isinstance(d["plan"],dict))
check("serialized safety",isinstance(d["safety"],dict))
check("serialized status",d["plan"]["status"]==rr.plan.status)
check("serialized execution false",d["plan"]["execution_authorized"] is False)
check("serialized safe validation",validate_serialized_action_readiness(d)==[])

bad=copy.deepcopy(rr); bad.plan.execution_authorized=True
check("validator catches execution authorization",len(validate_admission_action_readiness(bad))>0)
bad=copy.deepcopy(rr); bad.plan.crm_write_allowed=True
check("validator catches CRM write",len(validate_admission_action_readiness(bad))>0)
bad=copy.deepcopy(rr); bad.plan.application_occurred=True
check("validator catches occurrence claim",len(validate_admission_action_readiness(bad))>0)

rr2=run_admission_action_readiness(base_journey,base_crm,{"authorization_state":"GRANTED"},{"status":"COMMERCIAL_READY"})
check("run wrapper",rr2.plan.status==STATUS_READY)

print("\nAI CORE 23 TEST RESULT: ALL PASSED")
