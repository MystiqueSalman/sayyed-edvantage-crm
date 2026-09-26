
from Sayyed_EdVantage_AI_CORE20 import *

passed = 0
total = 0
def check(name, condition):
    global passed, total
    total += 1
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        print(f"FAIL: {name}")

ctx = {
    "status":"RESPONSE_CONTEXT_READY","lead_id":"SE-00001",
    "course_ids":["SE-DS-001"],"intent":"commercial","lead_stage":"Counselling",
    "facts":[
        {"field":"lead_id","value":"SE-00001","source":"CRM_READ","usable":True},
        {"field":"region","value":"India","source":"CRM_READ","usable":True},
        {"field":"intent","value":"commercial","source":"CONVERSATION_CONTEXT","usable":True},
    ],
    "provenance":["CRM_READ","CONVERSATION_CONTEXT","STATE_SYNCHRONIZATION"]
}
decision = {"decision":{"decision":"DECISION_CONTINUE","response_allowed":True}}
r = build_grounded_response_plan(
    ctx, decision,
    course_answer={"status":"READY"},
    commercial_plan={"status":"COMMERCIAL_READY"}
)
p = r.plan
check("ready status", p.status == RESPONSE_READY)
check("grounded mode", p.mode == MODE_GROUNDED)
check("lead preserved", p.lead_id == "SE-00001")
check("course preserved", p.course_ids == ["SE-DS-001"])
check("intent preserved", p.intent == "commercial")
check("stage preserved", p.lead_stage == "Counselling")
check("evidence preserved", len(p.evidence) == 3)
check("CRM evidence source", any(e.source=="CRM_READ" for e in p.evidence))
check("conversation evidence source", any(e.source=="CONVERSATION_CONTEXT" for e in p.evidence))
check("auxiliary provenance course", "COURSE_ANSWER" in p.provenance)
check("auxiliary provenance commercial", "COMMERCIAL_PLAN" in p.provenance)
check("message sending disabled", p.message_send_allowed is False)
check("CRM writes disabled", p.crm_write_allowed is False)
check("career safety claim included", any("employment" in x.lower() for x in p.prohibited_claims))
check("commercial safety claim included", any("indian pricing" in x.lower() for x in p.prohibited_claims))

partial = build_grounded_response_plan(
    {**ctx,"status":"RESPONSE_CONTEXT_CLARIFICATION",
     "clarification_questions":["Please clarify your current course."]},
    {"decision":{"decision":"DECISION_CLARIFY","response_allowed":False}}
)
check("clarification status", partial.plan.status == RESPONSE_CLARIFICATION)
check("clarification mode", partial.plan.mode == MODE_CLARIFY)
check("clarification blocks normal response", partial.plan.mode != MODE_GROUNDED)
check("clarification question preserved", len(partial.plan.clarification_questions)==1)

review = build_grounded_response_plan(
    {**ctx,"status":"RESPONSE_CONTEXT_REVIEW"},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False,"human_handoff_required":True}}
)
check("review status", review.plan.status == RESPONSE_HUMAN_REVIEW)
check("review mode", review.plan.mode == MODE_HUMAN)
check("review handoff", review.plan.human_handoff_required is True)
check("review blocks response", review.plan.mode != MODE_GROUNDED)

missing = build_grounded_response_plan(
    {**ctx,"status":"RESPONSE_CONTEXT_INSUFFICIENT"},
    {"decision":{"decision":"DECISION_OBTAIN_CRM","response_allowed":False}}
)
check("missing state status", missing.plan.status == RESPONSE_OBTAIN_STATE)
check("missing state mode", missing.plan.mode == MODE_OBTAIN_STATE)

unknown = build_grounded_response_plan(
    {"status":"RESPONSE_CONTEXT_UNKNOWN","lead_id":None,"course_ids":[],"facts":[]},
    {"decision":{"decision":"DECISION_UNKNOWN","response_allowed":False}}
)
check("unknown status", unknown.plan.status == RESPONSE_UNKNOWN)
check("unknown mode", unknown.plan.mode == MODE_NONE)
check("unknown has no response", unknown.plan.mode != MODE_GROUNDED)

# Downstream restriction cannot be overridden by ready context
restricted = build_grounded_response_plan(
    ctx,
    {"decision":{"decision":"DECISION_CLARIFY","response_allowed":False}}
)
check("downstream restriction honored", restricted.plan.status == RESPONSE_CLARIFICATION)
check("downstream restriction mode", restricted.plan.mode == MODE_CLARIFY)

# Safety validation
check("ready validates", validate_grounded_response(r) == [])
r.plan.message_send_allowed = True
check("validator catches message permission", len(validate_grounded_response(r)) > 0)
r.plan.message_send_allowed = False
r.safety["crm_writes_enabled"] = True
check("validator catches CRM write flag", len(validate_grounded_response(r)) > 0)
r.safety["crm_writes_enabled"] = False

# Unsafe evidence
unsafe_ctx = {**ctx,"facts":[
    {"field":"unknown_fact","value":"invented","source":"UNKNOWN","usable":False}
]}
unsafe = build_grounded_response_plan(unsafe_ctx, decision)
check("unsafe evidence validator", len(validate_grounded_response(unsafe)) > 0)

# Serialization
payload = grounded_response_to_dict(r)
check("serialization dict", isinstance(payload, dict))
check("serialized plan", "plan" in payload)
check("serialized evidence", "evidence" in payload["plan"])
check("serialized safety", "safety" in payload)

layer = build_grounded_response_layer()
check("layer read only", layer["read_only"] is True)
check("layer response planning", layer["response_planning"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer messaging disabled", layer["messaging_enabled"] is False)
check("layer execution disabled", layer["execution_enabled"] is False)
check("layer external actions disabled", layer["external_actions_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)

# No invention / missing values
minimal = build_grounded_response_plan(
    {"status":"RESPONSE_CONTEXT_READY","lead_id":"SE-00002","course_ids":[],"facts":[]},
    {"decision":{"decision":"DECISION_CONTINUE","response_allowed":True}}
)
check("minimal lead preserved", minimal.plan.lead_id == "SE-00002")
check("minimal course stays unknown", minimal.plan.course_ids == [])
check("minimal intent stays unknown", minimal.plan.intent is None)
check("minimal stage stays unknown", minimal.plan.lead_stage is None)

# Auxiliary planning layers are provenance only, not execution
full = build_grounded_response_plan(
    ctx, decision,
    course_answer={"answer":"course evidence"},
    commercial_plan={"answer":"fee evidence"},
    counselling_plan={"answer":"counselling evidence"},
    objection_plan={"answer":"objection evidence"},
    enrollment_readiness={"status":"ENROLLMENT_FLOW_READY"}
)
for src in ["COURSE_ANSWER","COMMERCIAL_PLAN","COUNSELLING_PLAN","OBJECTION_PLAN","ENROLLMENT_READINESS"]:
    check(f"{src} provenance preserved", src in full.plan.provenance)
check("full plan remains non-executable", full.safety["execution_enabled"] is False)

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
