
from Sayyed_EdVantage_AI_CORE13 import *

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

# Stage inference
check(infer_enrollment_stage("I am interested in Data Science.") == READINESS_INTERESTED, "Interested stage")
check(infer_enrollment_stage("I want to apply now.") == READINESS_APPLICATION, "Application stage")
check(infer_enrollment_stage("How do I pay?") == READINESS_PAYMENT, "Payment stage")
check(infer_enrollment_stage("I want to enroll.") == READINESS_ENROLLMENT, "Enrollment stage")
check(infer_enrollment_stage("I already paid.") == READINESS_ENROLLMENT, "Completed payment requires enrollment verification path")

# Interested
r = assess_enrollment_readiness("I am interested.", "E13-01", course_id="SE-DS-001")
check(r.status == STATUS_READY, "Interested with course is ready")
check(r.stage == READINESS_INTERESTED, "Interested stage preserved")
check(r.course_id == "SE-DS-001", "Course preserved")

r = assess_enrollment_readiness("I am interested.", "E13-02")
check(r.status == STATUS_CLARIFICATION, "Interested without course clarifies")
check(bool(r.clarification_questions), "Interested clarification question")

# Application
r = assess_enrollment_readiness("I want to apply now.", "E13-03", course_id="SE-PY-001")
check(r.status == STATUS_CLARIFICATION, "Application without application requirements clarifies")
check("required" in " ".join(r.blockers).lower(), "Application blocker documented")
check(all("application" in q.lower() or "details" in q.lower() or "documents" in q.lower() for q in r.clarification_questions), "Application questions are relevant")
check(r.application_confirmed is False, "Application not falsely confirmed")

r = assess_enrollment_readiness(
    "I want to apply now.", "E13-04",
    course_id="SE-PY-001", required_application_details_known=True
)
check(r.status == STATUS_READY, "Application readiness with known requirements")
check(r.application_confirmed is False, "Ready does not mean application submitted")

# Payment
r = assess_enrollment_readiness("I am ready to pay.", "E13-05", course_id="SE-DS-001")
check(r.status == STATUS_CLARIFICATION, "Payment without fee/region clarifies")
check(r.payment_confirmed is False, "Payment not confirmed")

r = assess_enrollment_readiness(
    "I am ready to pay.", "E13-06",
    course_id="SE-DS-001", region="india", verified_fee_known=True
)
check(r.status == STATUS_READY, "Payment readiness with verified prerequisites")
check(r.payment_confirmed is False, "Payment readiness is not payment confirmation")

# International region cannot be inferred as India
r = assess_enrollment_readiness(
    "I am ready to pay.", "E13-07",
    course_id="SE-DS-001", region="international", verified_fee_known=False
)
check(r.status == STATUS_CLARIFICATION, "International payment requires fee confirmation")
check(r.payment_confirmed is False, "International payment not confirmed")

# Enrollment
r = assess_enrollment_readiness("I want to enroll.", "E13-08", course_id="SE-DS-001")
check(r.status == STATUS_HANDOFF, "Enrollment requires authorized verification")
check(r.human_handoff_required is True, "Enrollment handoff required")
check(r.enrollment_confirmed is False, "Enrollment not falsely confirmed")
check("verification" in (r.handoff_reason or "").lower(), "Enrollment handoff reason")

r = assess_enrollment_readiness("I want to enroll.")
check(r.status == STATUS_CLARIFICATION, "Enrollment without course clarifies")

# Completed-action claims are not system confirmation
for msg in (
    "I already paid.",
    "Payment done.",
    "I already enrolled.",
    "I am enrolled.",
    "Application submitted already.",
):
    r = assess_enrollment_readiness(msg, "E13-09", course_id="SE-DS-001")
    check(r.status == STATUS_HANDOFF, f"Completed claim requires handoff: {msg}")
    check(r.application_confirmed is False, "Application flag remains false")
    check(r.payment_confirmed is False, "Payment flag remains false")
    check(r.enrollment_confirmed is False, "Enrollment flag remains false")

# Unknown/irrelevant
r = assess_enrollment_readiness("Tell me more.", "E13-10", course_id="SE-DS-001")
check(r.status == STATUS_READY, "General selected-course conversation remains safely at interested stage")
check(r.stage == READINESS_INTERESTED, "General message does not force enrollment stage")

# Explicit evidence
r = assess_enrollment_readiness(
    "I want to pay.", "E13-11",
    course_id="SE-DA-001", region="india", verified_fee_known=True,
    required_application_details_known=True
)
fields = {x.field for x in r.evidence}
check("course_id" in fields, "Course evidence present")
check("region" in fields, "Region evidence present")
check("verified_fee_known" in fields, "Fee evidence present")

# Safety invariants
check(r.no_invention is True, "No invention")
check(r.execution_enabled is False, "Execution disabled")
check(r.messaging_enabled is False, "Messaging disabled")
check(r.external_actions_enabled is False, "External actions disabled")
check(r.crm_writes_enabled is False, "CRM writes disabled")

# Validation
v = validate_enrollment_readiness(r)
check(v["valid"] is True, "Valid readiness validates")

bad = assess_enrollment_readiness("I am ready to pay.", "BAD-01", course_id="SE-DS-001", region="india", verified_fee_known=True)
bad.payment_confirmed = True
check(not validate_enrollment_readiness(bad)["valid"], "Payment confirmation mutation rejected")

bad = assess_enrollment_readiness("I am ready to pay.", "BAD-02", course_id="SE-DS-001", region="india", verified_fee_known=True)
bad.enrollment_confirmed = True
check(not validate_enrollment_readiness(bad)["valid"], "Enrollment confirmation mutation rejected")

bad = assess_enrollment_readiness("I am ready to pay.", "BAD-03", course_id="SE-DS-001", region="india", verified_fee_known=True)
bad.execution_enabled = True
check(not validate_enrollment_readiness(bad)["valid"], "Execution mutation rejected")

bad = assess_enrollment_readiness("I am interested.", "BAD-04", course_id="SE-DS-001")
bad.status = STATUS_CLARIFICATION
bad.clarification_questions = []
check(not validate_enrollment_readiness(bad)["valid"], "Empty clarification rejected")

bad = assess_enrollment_readiness("I want to enroll.", "BAD-05", course_id="SE-DS-001")
bad.human_handoff_required = False
check(not validate_enrollment_readiness(bad)["valid"], "Invalid handoff rejected")

# Serialization
r = run_enrollment_readiness("I am ready to pay.", "E13-12", course_id="SE-DS-001", region="india", verified_fee_known=True)
d = enrollment_readiness_to_dict(r)
check(d["session_id"] == "E13-12", "Serialization session")
check(d["status"] == r.status, "Serialization status")
check(d["stage"] == r.stage, "Serialization stage")
check(d["course_id"] == "SE-DS-001", "Serialization course")
check(d["payment_confirmed"] is False, "Serialization payment safety")
check(d["enrollment_confirmed"] is False, "Serialization enrollment safety")

# Determinism
a = infer_enrollment_stage("I want to apply now.")
b = infer_enrollment_stage("I want to apply now.")
check(a == b, "Stage inference deterministic")

print(f"AI CORE 13: {passed}/{total} PASSED")
