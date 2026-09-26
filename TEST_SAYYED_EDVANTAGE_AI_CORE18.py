
from Sayyed_EdVantage_AI_CORE18 import *

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

crm = {"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Counselling","region":"India","intent":"commercial"}
ctx = {"lead_id":"SE-00001","active_course_ids":["SE-DS-001"],"active_intent":"commercial"}
sync_ready = {"status":"SYNC_READY"}

r = build_conversation_decision(crm, ctx, sync_ready, {"intent":"commercial"})
check("ready decision", r.decision.decision == DECISION_CONTINUE)
check("response preparation", r.decision.next_step == NEXT_RESPONSE)
check("lead preserved", r.lead_id == "SE-00001")
check("course preserved", r.active_course_ids == ["SE-DS-001"])
check("stage preserved", r.lead_stage == "Counselling")
check("intent preserved", r.active_intent == "commercial")
check("CRM provenance", "CRM_READ" in r.provenance)
check("sync provenance", "STATE_SYNCHRONIZATION" in r.provenance)
check("response allowed", r.decision.response_allowed is True)
check("CRM writes disabled", r.decision.crm_write_allowed is False)
check("message sending disabled", r.decision.message_send_allowed is False)

partial = build_conversation_decision(crm, ctx, {"status":"SYNC_CLARIFICATION"}, {})
check("partial state clarification", partial.decision.decision == DECISION_CLARIFY)
check("partial state next step", partial.decision.next_step == NEXT_CLARIFICATION)
check("partial state remains non-writing", partial.decision.crm_write_allowed is False)

conflict = build_conversation_decision(
    crm, {**ctx, "active_intent":"career"},
    {"status":"SYNC_REVIEW","clarification_questions":["Please clarify the current intent."]},
    {"intent":"career"}
)
check("conflict becomes human review", conflict.decision.decision == DECISION_HUMAN_REVIEW)
check("conflict next step review", conflict.decision.next_step == NEXT_REVIEW)
check("conflict requires handoff", conflict.decision.human_handoff_required is True)
check("conflict blocks normal response", conflict.decision.response_allowed is False)
check("conflict does not enable CRM write", conflict.decision.crm_write_allowed is False)
check("conflict question preserved", len(conflict.decision.clarification_questions) == 1)

missing_crm = build_conversation_decision(
    {}, ctx, {"status":"SYNC_INSUFFICIENT"}, {}
)
check("missing CRM obtains CRM state", missing_crm.decision.decision == DECISION_OBTAIN_CRM)
check("missing CRM next step", missing_crm.decision.next_step == NEXT_CRM_STATE)
check("missing CRM response blocked", missing_crm.decision.response_allowed is False)

unknown = build_conversation_decision(
    {}, {}, {"status":"SYNC_UNKNOWN"}, {}
)
check("unknown state decision", unknown.decision.decision == DECISION_UNKNOWN)
check("unknown state no action", unknown.decision.next_step == NEXT_NO_ACTION)
check("unknown state no response", unknown.decision.response_allowed is False)

# Safety validation
check("ready result validates", validate_conversation_decision(r) == [])
r.decision.crm_write_allowed = True
check("validator catches CRM write", len(validate_conversation_decision(r)) > 0)
r.decision.crm_write_allowed = False
r.decision.message_send_allowed = True
check("validator catches message send", len(validate_conversation_decision(r)) > 0)
r.decision.message_send_allowed = False

# Serialization
payload = decision_to_dict(conflict)
check("serialization dict", isinstance(payload, dict))
check("serialized decision", "decision" in payload)
check("serialized provenance", "provenance" in payload)
check("serialized safety", "safety" in payload)

layer = build_crm_conversation_decision_layer()
check("layer read only", layer["read_only"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer messaging disabled", layer["messaging_enabled"] is False)
check("layer execution disabled", layer["execution_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)

# No invention: absent optional values stay absent
minimal = build_conversation_decision(
    {"lead_id":"SE-00002"}, {"lead_id":"SE-00002"}, {"status":"SYNC_READY"}, {}
)
check("minimal lead preserved", minimal.lead_id == "SE-00002")
check("minimal course remains unknown", minimal.active_course_ids == [])
check("minimal stage remains unknown", minimal.lead_stage is None)
check("minimal intent remains unknown", minimal.active_intent is None)

# Defensive copy
crm2 = {"lead_id":"SE-00003","course_id":"SE-PY-001","stage":"Interested"}
ctx2 = {"lead_id":"SE-00003","active_course_ids":["SE-PY-001"]}
intel2 = {"intent":"program_information","nested":{"x":1}}
rr = build_conversation_decision(crm2, ctx2, {"status":"SYNC_READY"}, intel2)
intel2["nested"]["x"] = 99
check("intelligence copied defensively", rr.active_intent == "program_information")

# Secondary sync statuses
for status, expected in [
    ("SYNC_REVIEW", DECISION_HUMAN_REVIEW),
    ("SYNC_INSUFFICIENT", DECISION_OBTAIN_CRM),
    ("SYNC_UNKNOWN", DECISION_UNKNOWN),
    ("SYNC_CLARIFICATION", DECISION_CLARIFY),
    ("SYNC_READY", DECISION_CONTINUE),
]:
    x = build_conversation_decision(crm, ctx, {"status":status}, {})
    check(f"status {status} mapped safely", x.decision.decision == expected)

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
