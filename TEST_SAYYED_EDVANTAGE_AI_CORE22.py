
from Sayyed_EdVantage_AI_CORE22 import *

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

base_crm = {"lead_id":"SE-00001","course_id":"SE-DS-001","stage":"Interested","region":"India"}
ctx = {"lead_id":"SE-00001","active_course_ids":["SE-DS-001"],"active_intent":"program_information"}
sync = {"status":"SYNC_READY"}
turn = {"turn_status":"TURN_READY"}

r = build_admission_journey_plan(base_crm, ctx, None, turn, sync)
p = r.plan
check("interested status", p.status == JOURNEY_INTERESTED)
check("interested next step", p.next_step == NEXT_DISCUSS)
check("lead preserved", p.lead_id == "SE-00001")
check("course preserved", p.course_ids == ["SE-DS-001"])
check("stage preserved", p.crm_stage == "Interested")
check("no application claim", p.application_occurred is False)
check("no payment claim", p.payment_occurred is False)
check("no enrollment claim", p.enrollment_occurred is False)
check("CRM write disabled", p.crm_write_allowed is False)
check("message disabled", p.message_send_allowed is False)
check("external action disabled", p.external_action_allowed is False)

application = build_admission_journey_plan(
    {**base_crm,"stage":"Application"}, ctx,
    {"status":"ADMISSION_READY"}, turn, sync
)
check("application stage", application.plan.status == JOURNEY_APPLICATION)
check("application guidance", application.plan.next_step == NEXT_APPLICATION)
check("application not claimed", application.plan.application_occurred is False)

payment = build_admission_journey_plan(
    {**base_crm,"stage":"Payment Pending"}, ctx,
    {"status":"ADMISSION_READY"}, turn, sync
)
check("payment stage", payment.plan.status == JOURNEY_PAYMENT)
check("payment guidance", payment.plan.next_step == NEXT_PAYMENT)
check("payment not claimed", payment.plan.payment_occurred is False)

enrolled = build_admission_journey_plan(
    {**base_crm,"stage":"Enrolled"}, ctx,
    {"status":"ADMISSION_READY"}, turn, sync
)
check("enrollment stage", enrolled.plan.status == JOURNEY_ENROLLMENT)
check("enrollment guidance", enrolled.plan.next_step == NEXT_ENROLLMENT)
check("enrollment not claimed", enrolled.plan.enrollment_occurred is False)

review = build_admission_journey_plan(
    base_crm, ctx, None,
    {"turn_status":"TURN_HUMAN_REVIEW"},
    {"status":"SYNC_REVIEW","clarification_questions":["Clarify current stage."],
     "human_handoff_required":True}
)
check("review status", review.plan.status == JOURNEY_REVIEW)
check("review next step", review.plan.next_step == NEXT_REVIEW)
check("review handoff", review.plan.human_handoff_required is True)
check("review question retained", len(review.plan.clarification_questions)==1)

clar = build_admission_journey_plan(
    base_crm, ctx, None, {"turn_status":"TURN_CLARIFICATION"},
    {"status":"SYNC_CLARIFICATION","clarification_questions":["Clarify course."]}
)
check("clarification status", clar.plan.status == JOURNEY_CLARIFICATION)
check("clarification next step", clar.plan.next_step == NEXT_CLARIFY)
check("clarification question retained", len(clar.plan.clarification_questions)==1)

unknown = build_admission_journey_plan(
    {}, {}, None, {"turn_status":"TURN_UNKNOWN"},
    {"status":"SYNC_UNKNOWN"}
)
check("unknown status", unknown.plan.status == JOURNEY_UNKNOWN)
check("unknown state step", unknown.plan.next_step == NEXT_OBTAIN_STATE)

# Provenance
full = build_admission_journey_plan(
    base_crm, ctx, {"status":"ENROLLMENT_FLOW_READY"},
    turn, sync
)
for src in ["CRM_READ","CONVERSATION_CONTEXT","ADMISSION_READINESS","AGENT_TURN","STATE_SYNCHRONIZATION"]:
    check(f"{src} provenance", src in full.plan.provenance)

# Safety claims
check("application safety claim", any("application" in x.lower() for x in p.prohibited_claims))
check("payment safety claim", any("payment" in x.lower() for x in p.prohibited_claims))
check("enrollment safety claim", any("enrollment" in x.lower() for x in p.prohibited_claims))
check("outcome safety claim", any("employment" in x.lower() for x in p.prohibited_claims))

# Validation
check("valid plan", validate_admission_journey(r) == [])
r.plan.payment_occurred = True
check("validator catches payment claim", len(validate_admission_journey(r)) > 0)
r.plan.payment_occurred = False
r.plan.crm_write_allowed = True
check("validator catches CRM write", len(validate_admission_journey(r)) > 0)
r.plan.crm_write_allowed = False

# Serialization
payload = admission_journey_to_dict(full)
check("serialization dict", isinstance(payload, dict))
check("serialized plan", "plan" in payload)
check("serialized evidence", "evidence" in payload["plan"])
check("serialized safety", "safety" in payload)

layer = build_admission_journey_layer()
check("layer read only", layer["read_only"] is True)
check("layer journey intelligence", layer["admission_journey_intelligence"] is True)
check("layer CRM writes disabled", layer["crm_writes_enabled"] is False)
check("layer messaging disabled", layer["messaging_enabled"] is False)
check("layer external disabled", layer["external_actions_enabled"] is False)
check("layer execution disabled", layer["execution_enabled"] is False)
check("layer fail closed", layer["fail_closed"] is True)

# No invention of unsupported stages
unknown_stage = build_admission_journey_plan(
    {**base_crm,"stage":"Some Future Stage"}, ctx, None, turn, sync
)
check("unsupported stage is unknown", unknown_stage.plan.status == JOURNEY_UNKNOWN)
check("unsupported stage no action", unknown_stage.plan.next_step == NEXT_NONE)

# Multiple courses retained
multi = build_admission_journey_plan(
    {**base_crm,"stage":"Application"},
    {**ctx,"active_course_ids":["SE-DS-001","SE-DA-001"]},
    {"status":"ADMISSION_READY"}, turn, sync
)
check("multiple courses preserved", multi.plan.course_ids == ["SE-DS-001","SE-DA-001"])

print(f"\nTOTAL: {passed}/{total} PASSED")
raise SystemExit(0 if passed == total else 1)
