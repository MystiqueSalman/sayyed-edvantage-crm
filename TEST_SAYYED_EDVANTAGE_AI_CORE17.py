
from Sayyed_EdVantage_AI_CORE17 import *

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
    "lead_id":"SE-00001","course_id":"SE-DS-001",
    "stage":"Counselling","region":"India","intent":"commercial"
}
ctx = {
    "lead_id":"SE-00001","active_course_ids":["SE-DS-001"],
    "active_intent":"commercial"
}

r = compare_lead_state(crm, ctx)
check("partial state gets clarification", r.status == SYNC_CLARIFICATION)
check("lead preserved", r.lead_id == "SE-00001")
check("course aligned", "course_id" in r.aligned_fields)
check("region CRM-only is detected", "region" in r.crm_only_fields)
check("stage CRM-only is detected", "stage" in r.crm_only_fields)
check("CRM provenance", "CRM_READ" in r.source_provenance)
check("context provenance", "CONVERSATION_CONTEXT" in r.source_provenance)
check("no CRM write permission", r.crm_write_allowed is False)
check("no handoff for missing context field", r.human_handoff_required is False)

# Complete matching context
ctx2 = dict(ctx)
ctx2.update({"stage":"Counselling","region":"India"})
r2 = compare_lead_state(crm, ctx2)
check("fully aligned status", r2.status == SYNC_READY)
check("stage aligned", "stage" in r2.aligned_fields)
check("region aligned", "region" in r2.aligned_fields)
check("no conflicts", r2.conflicting_fields == [])

# Conflict
ctx3 = dict(ctx2)
ctx3["active_intent"] = "career"
r3 = compare_lead_state(crm, ctx3)
check("conflict detected", "intent" in r3.conflicting_fields)
check("conflict status review", r3.status == SYNC_REVIEW)
check("handoff required", r3.human_handoff_required is True)
check("clarification question generated", len(r3.clarification_questions) >= 1)
check("write still disabled", r3.crm_write_allowed is False)
check("write may be required diagnostically", r3.crm_write_required is True)

# CRM unavailable
r4 = compare_lead_state(None, ctx)
check("missing CRM is insufficient", r4.status == SYNC_INSUFFICIENT)
check("CRM unavailable error", len(r4.errors) == 1)
check("context provenance retained", r4.source_provenance == ["CONVERSATION_CONTEXT"])

# Both unavailable
r5 = compare_lead_state(None, None)
check("both missing is unknown", r5.status == SYNC_UNKNOWN)
check("unknown error present", len(r5.errors) == 1)

# Runtime routing
rr = run_state_synchronization(crm, ctx3)
check("runtime routes conflict to review", rr.recommended_next_step == "HUMAN_REVIEW")
check("runtime safety", rr.safety["crm_writes_enabled"] is False)
check("runtime execution disabled", rr.safety["execution_enabled"] is False)
check("runtime messaging disabled", rr.safety["messaging_enabled"] is False)

rr2 = run_state_synchronization(crm, ctx2)
check("runtime aligned continues", rr2.recommended_next_step == "CONTINUE_CONVERSATION")

# Missing fields remain explicitly sourced
ctx4 = {"lead_id":"SE-00001","active_course_ids":["SE-DS-001"]}
r6 = compare_lead_state(crm, ctx4)
check("missing fields do not become conflicts", "stage" not in r6.conflicting_fields)
check("missing CRM facts remain CRM-only", "stage" in r6.crm_only_fields)

# Course conflict
ctx5 = dict(ctx2)
ctx5["active_course_ids"] = ["SE-DA-001"]
r7 = compare_lead_state(crm, ctx5)
check("course conflict detected", "course_id" in r7.conflicting_fields)
check("course conflict review", r7.status == SYNC_REVIEW)

# Multi-course context is not silently reduced
ctx6 = dict(ctx2)
ctx6["active_course_ids"] = ["SE-DS-001","SE-DA-001"]
r8 = compare_lead_state(crm, ctx6)
check("multi-course context retained as conflict", "course_id" in r8.conflicting_fields)
check("multi-course requires review", r8.human_handoff_required is True)

# Defensive-copy/evidence safety
crm_copy = {"lead_id":"SE-00002","course_id":"SE-PY-001","nested":{"x":1}}
ctx_copy = {"lead_id":"SE-00002"}
r9 = compare_lead_state(crm_copy, ctx_copy)
crm_copy["nested"]["x"] = 99
check("input mutation does not alter sync evidence", r9.lead_id == "SE-00002")

# Validation
check("valid sync has no errors", validate_sync(r2) == [])
bad = r2
bad.crm_write_allowed = True
check("validator catches CRM write permission", len(validate_sync(bad)) > 0)
bad.crm_write_allowed = False

# Serialization
payload = runtime_to_dict(rr)
check("runtime serializes to dict", isinstance(payload, dict))
check("serialized sync present", "sync" in payload)
check("serialized evidence present", "evidences" in payload["sync"])
check("serialized safety present", "safety" in payload)

layer = build_crm_state_sync_layer()
check("layer read-only", layer["read_only"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)
check("layer conflict policy", layer["conflict_policy"] == "do_not_silently_choose")

# Secondary CRM-state conflict
crm2 = dict(crm)
crm2["follow_up"] = {"status":"pending"}
ctx7 = dict(ctx2)
ctx7["follow_up"] = {"status":"completed"}
r10 = compare_lead_state(crm2, ctx7)
check("follow-up conflict detected", "follow_up" in r10.conflicting_fields)
check("secondary conflict requires review", r10.status == SYNC_REVIEW)

# Stage-only CRM fact remains visible
crm3 = dict(crm)
ctx8 = {"lead_id":"SE-00001","active_course_ids":["SE-DS-001"],"active_intent":"commercial"}
r11 = compare_lead_state(crm3, ctx8)
check("stage evidence exists", any(e.field == "stage" for e in r11.evidences))
check("stage value preserved", any(e.field == "stage" and e.crm_value == "Counselling" for e in r11.evidences))

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
