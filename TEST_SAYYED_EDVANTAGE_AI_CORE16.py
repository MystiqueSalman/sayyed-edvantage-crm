
from Sayyed_EdVantage_AI_CORE16 import *

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

crm = {"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Counselling","region":"India"}
conv = {"active_course_ids":["SE-DS-001"],"active_intent":"commercial"}
intel = {"course_ids":["SE-DS-001"],"intent":"commercial"}

r = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel, {"state":"UNKNOWN"}, "SEND_MESSAGE")
check("result exists", isinstance(r, CRMAwareAgentResult))
check("CRM lead preserved", r.context.lead_id == "SE-00001")
check("course preserved", r.context.active_course_ids == ["SE-DS-001"])
check("intent preserved", r.context.active_intent == "commercial")
check("CRM provenance", "CRM_READ" in r.context.provenance)
check("message blocked without authorization", r.action_decisions[0].status == ACTION_BLOCKED)
check("not executable", r.action_decisions[0].executable is False)
check("authorization required", r.authorization_required is True)

for state in ["REVOKED","EXPIRED","DENIED"]:
    rr = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel,
        {"state":state,"authorization_granted":True,"execution_authorized":True,"send_status":"SENT"},
        "SEND_MESSAGE")
    check(f"{state} grants cleared", rr.context.authorization.authorization_granted is False)
    check(f"{state} execution cleared", rr.context.authorization.execution_authorized is False)
    check(f"{state} not sent", rr.context.authorization.send_status == "NOT_SENT")
    check(f"{state} action blocked", rr.action_decisions[0].status == ACTION_BLOCKED)

granted = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel,
    {"state":"GRANTED","authorization_granted":True,"execution_authorized":True},
    "SEND_MESSAGE")
check("granted still not executable", granted.action_decisions[0].executable is False)
check("granted status remains blocked by read-only layer", granted.action_decisions[0].status == ACTION_BLOCKED)
check("authorized flag can be represented", granted.action_decisions[0].authorized is True)

prep = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel, {"state":"UNKNOWN"}, "PREPARE_RESPONSE")
check("preparation allowed as recommendation", prep.action_decisions[0].status == ACTION_RECOMMENDED)
check("preparation not executable", prep.action_decisions[0].executable is False)

human = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel, {"state":"UNKNOWN"}, "REQUEST_HUMAN_REVIEW")
check("human review status", human.status == STATUS_HANDOFF)
check("human handoff required", human.human_handoff_required is True)

unknown = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel, {"state":"UNKNOWN"}, "SOME_UNSAFE_ACTION")
check("unknown action blocked", unknown.action_decisions[0].status == ACTION_BLOCKED)
check("unknown action not executable", unknown.action_decisions[0].executable is False)

bad_auth = AuthorizationSnapshot(state=AUTH_REVOKED, authorization_granted=True, execution_authorized=True, send_status="SENT")
check("bad auth validation catches inconsistency", len(validate_authorization_snapshot(bad_auth)) == 3)

bad_result = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel, {"state":"UNKNOWN"}, "SEND_MESSAGE")
bad_result.safety["execution_enabled"] = True
check("validator catches unsafe execution flag", len(validate_crm_aware_result(bad_result)) > 0)

serialized = crm_aware_result_to_dict(r)
check("serialization returns dict", isinstance(serialized, dict))
check("serialization has context", "context" in serialized)
check("serialization has decisions", "action_decisions" in serialized)
check("serialization has safety", "safety" in serialized)

layer = build_crm_aware_agent_layer()
check("layer read only", layer["read_only"] is True)
check("layer authorization aware", layer["authorization_aware"] is True)
check("layer fail closed", layer["fail_closed"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)

# defensive-copy check
snap = {"lead_id":"SE-00002","notes":{"x":1}}
ctx = build_crm_aware_context(crm_snapshot=snap)
snap["notes"]["x"] = 99
check("CRM snapshot defensive copy", ctx.crm_snapshot["notes"]["x"] == 1)

# execution actions all blocked
for action in sorted(EXECUTION_ACTIONS):
    rr = orchestrate_crm_aware_agent("SE-00001", crm, conv, intel,
        {"state":"GRANTED","authorization_granted":True,"execution_authorized":True},
        action)
    check(f"{action} blocked", rr.action_decisions[0].status == ACTION_BLOCKED)
    check(f"{action} not executable", rr.action_decisions[0].executable is False)

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
