
from Sayyed_EdVantage_AI_CORE21 import *

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
plan = {
    "status":"RESPONSE_READY","mode":"GROUNDED_RESPONSE",
    "prohibited_claims":["Do not invent fees or admissions outcomes."]
}
decision = {"decision":{"decision":"DECISION_CONTINUE","response_allowed":True}}

r = compose_agent_turn(
    ctx, plan, decision,
    {"active_course_ids":["SE-DS-001"],"active_intent":"commercial"},
    {"intent":"commercial"}
)
c = r.contract
check("ready turn", c.turn_status == TURN_READY)
check("respond mode", c.mode == MODE_RESPONSE)
check("response preparation allowed", c.response_preparation_allowed is True)
check("lead preserved", c.lead_id == "SE-00001")
check("course preserved", c.course_ids == ["SE-DS-001"])
check("intent preserved", c.intent == "commercial")
check("stage preserved", c.lead_stage == "Counselling")
check("evidence preserved", len(c.evidence) == 3)
check("prohibited claims preserved", len(c.prohibited_claims) == 1)
check("CRM provenance", "CRM_READ" in c.provenance)
check("response plan provenance", "RESPONSE_PLAN" in c.provenance)
check("decision provenance", "CRM_DECISION" in c.provenance)
check("messaging disabled", c.message_send_allowed is False)
check("CRM writes disabled", c.crm_write_allowed is False)
check("external actions disabled", c.external_action_allowed is False)

clar = compose_agent_turn(
    {**ctx,"status":"RESPONSE_CONTEXT_CLARIFICATION",
     "clarification_questions":["Please clarify your current course."]},
    {"status":"RESPONSE_CLARIFICATION","mode":"ASK_CLARIFICATION"},
    {"decision":{"decision":"DECISION_CLARIFY","response_allowed":False}}
)
check("clarification turn", clar.contract.turn_status == TURN_CLARIFICATION)
check("clarification mode", clar.contract.mode == MODE_CLARIFY)
check("clarification prep blocked", clar.contract.response_preparation_allowed is False)
check("clarification question retained", len(clar.contract.clarification_questions)==1)

review = compose_agent_turn(
    {**ctx,"status":"RESPONSE_CONTEXT_REVIEW"},
    {"status":"RESPONSE_HUMAN_REVIEW","mode":"HUMAN_REVIEW"},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False,"human_handoff_required":True}}
)
check("review turn", review.contract.turn_status == TURN_HUMAN_REVIEW)
check("review mode", review.contract.mode == MODE_HUMAN)
check("review handoff", review.contract.human_handoff_required is True)
check("review prep blocked", review.contract.response_preparation_allowed is False)

obtain = compose_agent_turn(
    {**ctx,"status":"RESPONSE_CONTEXT_INSUFFICIENT"},
    {"status":"RESPONSE_OBTAIN_STATE","mode":"OBTAIN_CRM_STATE"},
    {"decision":{"decision":"DECISION_OBTAIN_CRM","response_allowed":False}}
)
check("obtain-state turn", obtain.contract.turn_status == TURN_OBTAIN_STATE)
check("obtain-state mode", obtain.contract.mode == MODE_OBTAIN_STATE)
check("obtain-state prep blocked", obtain.contract.response_preparation_allowed is False)

unknown = compose_agent_turn(
    {"status":"RESPONSE_CONTEXT_UNKNOWN","lead_id":None,"course_ids":[],"facts":[]},
    {"status":"RESPONSE_UNKNOWN","mode":"NO_RESPONSE"},
    {"decision":{"decision":"DECISION_UNKNOWN","response_allowed":False}}
)
check("unknown turn", unknown.contract.turn_status == TURN_UNKNOWN)
check("unknown mode", unknown.contract.mode == MODE_NONE)
check("unknown prep blocked", unknown.contract.response_preparation_allowed is False)

# Precedence: conflict beats a downstream normal response plan
precedence = compose_agent_turn(
    {**ctx,"status":"RESPONSE_CONTEXT_REVIEW"},
    {"status":"RESPONSE_READY","mode":"GROUNDED_RESPONSE"},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False}}
)
check("conflict precedence", precedence.contract.turn_status == TURN_HUMAN_REVIEW)
check("conflict blocks preparation", precedence.contract.response_preparation_allowed is False)

# Safety validation
check("ready validates", validate_agent_turn(r) == [])
r.contract.message_send_allowed = True
check("validator catches message permission", len(validate_agent_turn(r)) > 0)
r.contract.message_send_allowed = False
r.contract.crm_write_allowed = True
check("validator catches CRM permission", len(validate_agent_turn(r)) > 0)
r.contract.crm_write_allowed = False
r.contract.external_action_allowed = True
check("validator catches external permission", len(validate_agent_turn(r)) > 0)
r.contract.external_action_allowed = False

# Unsafe evidence
unsafe = compose_agent_turn(
    {**ctx,"facts":[{"field":"invented","value":"x","source":"UNKNOWN","usable":False}]},
    plan, decision
)
check("validator catches unsafe evidence", len(validate_agent_turn(unsafe)) > 0)

# Serialization
payload = agent_turn_to_dict(r)
check("serialization dict", isinstance(payload, dict))
check("serialized contract", "contract" in payload)
check("serialized evidence", "evidence" in payload["contract"])
check("serialized safety", "safety" in payload)

layer = build_agent_turn_composition_layer()
check("layer read-only", layer["read_only"] is True)
check("layer response preparation", layer["response_preparation"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer messaging disabled", layer["messaging_enabled"] is False)
check("layer external actions disabled", layer["external_actions_enabled"] is False)
check("layer execution disabled", layer["execution_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)

# Multiple courses preserved
multi = compose_agent_turn(
    {**ctx,"course_ids":["SE-DS-001","SE-DA-001"],"status":"RESPONSE_CONTEXT_REVIEW"},
    {"status":"RESPONSE_HUMAN_REVIEW","mode":"HUMAN_REVIEW"},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False}}
)
check("multiple courses preserved", multi.contract.course_ids == ["SE-DS-001","SE-DA-001"])
check("multiple course review", multi.contract.turn_status == TURN_HUMAN_REVIEW)

# Auxiliary inputs are provenance only and cannot enable execution
full = compose_agent_turn(
    ctx, plan, decision,
    {"active_course_ids":["SE-DS-001"]},
    {"intent":"commercial","execution_enabled":True}
)
check("conversation provenance retained", "CONVERSATION_CONTEXT" in full.contract.provenance)
check("AI provenance retained", "AI_INTELLIGENCE" in full.contract.provenance)
check("execution remains disabled", full.safety["execution_enabled"] is False)
check("messaging remains disabled", full.safety["messaging_enabled"] is False)

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
