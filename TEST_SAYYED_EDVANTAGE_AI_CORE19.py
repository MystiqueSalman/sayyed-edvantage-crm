
from Sayyed_EdVantage_AI_CORE19 import *

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

crm = {
    "lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Counselling",
    "region":"India","counselling":{"status":"completed"},
    "follow_up":{"status":"pending"},"pending_items":["fee confirmation"]
}
ctx = {
    "lead_id":"SE-00001","active_course_ids":["SE-DS-001"],
    "active_intent":"commercial"
}
intel = {"intent":"commercial"}
sync = {"status":"SYNC_READY"}
decision = {"decision":{"decision":"DECISION_CONTINUE","response_allowed":True}}

r = build_lead_aware_response_context(crm, ctx, intel, sync, decision)
c = r.context
check("ready response context", c.status == RESPONSE_CONTEXT_READY)
check("response allowed", c.response_allowed is True)
check("grounded response mode", r.recommended_response_mode == "GROUNDED_RESPONSE")
check("lead identity preserved", c.lead_id == "SE-00001")
check("course preserved", c.course_ids == ["SE-DS-001"])
check("intent preserved", c.intent == "commercial")
check("stage preserved", c.lead_stage == "Counselling")
check("CRM provenance", SOURCE_CRM in c.provenance)
check("conversation provenance", SOURCE_CONVERSATION in c.provenance)
check("intelligence provenance", SOURCE_INTELLIGENCE in c.provenance)
check("sync provenance", SOURCE_SYNC in c.provenance)
check("decision provenance", SOURCE_DECISION in c.provenance)
check("CRM region included", any(f.field=="region" and f.source==SOURCE_CRM for f in c.facts))
check("pending item included", any(f.field=="pending_items" for f in c.facts))
check("all included facts usable", all(f.usable for f in c.facts))
check("CRM writes disabled", r.safety["crm_writes_enabled"] is False)
check("messaging disabled", r.safety["messaging_enabled"] is False)
check("execution disabled", r.safety["execution_enabled"] is False)

partial = build_lead_aware_response_context(crm, ctx, intel,
    {"status":"SYNC_CLARIFICATION"}, None)
check("partial state blocks normal response", partial.context.response_allowed is False)
check("partial state asks clarification", partial.recommended_response_mode == "ASK_CLARIFICATION")
check("partial status", partial.context.status == RESPONSE_CONTEXT_CLARIFICATION)

conflict = build_lead_aware_response_context(crm, {**ctx,"active_intent":"career"}, intel,
    {"status":"SYNC_REVIEW","human_handoff_required":True,
     "clarification_questions":["Please clarify current intent."]},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False}})
check("conflict review context", conflict.context.status == RESPONSE_CONTEXT_REVIEW)
check("conflict blocks response", conflict.context.response_allowed is False)
check("conflict requires handoff", conflict.context.human_handoff_required is True)
check("conflict question preserved", len(conflict.context.clarification_questions)==1)
check("review mode", conflict.recommended_response_mode == "HUMAN_REVIEW")

missing = build_lead_aware_response_context({}, ctx, intel,
    {"status":"SYNC_INSUFFICIENT"}, None)
check("missing CRM blocks response", missing.context.response_allowed is False)
check("missing CRM mode", missing.recommended_response_mode == "OBTAIN_CRM_STATE")
check("missing CRM status", missing.context.status == RESPONSE_CONTEXT_INSUFFICIENT)

unknown = build_lead_aware_response_context({}, {}, {},
    {"status":"SYNC_UNKNOWN"}, None)
check("unknown context blocks response", unknown.context.response_allowed is False)
check("unknown mode", unknown.recommended_response_mode == "NO_RESPONSE_CONTEXT")
check("unknown status", unknown.context.status == RESPONSE_CONTEXT_UNKNOWN)

# Downstream decision can restrict an otherwise ready context
restricted = build_lead_aware_response_context(
    crm, ctx, intel, sync,
    {"decision":{"decision":"DECISION_CLARIFY","response_allowed":False}}
)
check("decision restriction honored", restricted.context.response_allowed is False)
check("decision restriction mode", restricted.recommended_response_mode == "ASK_CLARIFICATION")
check("decision restriction status", restricted.context.status == RESPONSE_CONTEXT_CLARIFICATION)

# No invention of unsupported fields
check("unsupported arbitrary field not included",
      not any(f.field=="salary" for f in c.facts))
check("unsupported certification not invented",
      not any(f.field=="certification" for f in c.facts))

# Validation
check("ready context validates", validate_response_context(r) == [])
r.context.response_allowed = True
r.context.status = RESPONSE_CONTEXT_REVIEW
r.context.human_handoff_required = False
check("validator catches invalid review context", len(validate_response_context(r)) > 0)
r.context.status = RESPONSE_CONTEXT_READY
r.context.human_handoff_required = False

# Serialization
payload = response_context_to_dict(r)
check("serialization dict", isinstance(payload, dict))
check("serialized context", "context" in payload)
check("serialized facts", "facts" in payload["context"])
check("serialized safety", "safety" in payload)

layer = build_lead_aware_response_layer()
check("layer read only", layer["read_only"] is True)
check("layer response-context only", layer["response_context_only"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer messaging disabled", layer["messaging_enabled"] is False)
check("layer execution disabled", layer["execution_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)

# Defensive copy
crm2 = {"lead_id":"SE-00002","course_id":"SE-PY-001","region":"India"}
ctx2 = {"lead_id":"SE-00002","active_course_ids":["SE-PY-001"]}
r2 = build_lead_aware_response_context(crm2, ctx2, {}, sync, decision)
crm2["region"] = "Changed"
check("CRM input defensively copied",
      next(f.value for f in r2.context.facts if f.field=="region") == "India")

# Multiple course context preserved, never silently reduced
ctx3 = {"lead_id":"SE-00003","active_course_ids":["SE-DS-001","SE-DA-001"]}
r3 = build_lead_aware_response_context(
    {"lead_id":"SE-00003"}, ctx3, {},
    {"status":"SYNC_REVIEW","human_handoff_required":True,
     "clarification_questions":["Please clarify current course."]},
    {"decision":{"decision":"DECISION_HUMAN_REVIEW","response_allowed":False}}
)
check("multiple courses preserved", r3.context.course_ids == ["SE-DS-001","SE-DA-001"])
check("multiple courses review", r3.context.status == RESPONSE_CONTEXT_REVIEW)

# Decision absent: sync remains authoritative
r4 = build_lead_aware_response_context(crm, ctx, intel, sync, None)
check("no decision still permits ready context", r4.context.response_allowed is True)
check("no decision still grounded", r4.recommended_response_mode == "GROUNDED_RESPONSE")

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
