
"""
Test suite — Sayyed EdVantage AI Agent AI Core 11
Conversation Objection Handling Intelligence Contract
"""

from Sayyed_EdVantage_AI_CORE11 import (
    OBJECTION_NONE,
    OBJECTION_FEE,
    OBJECTION_TIME,
    OBJECTION_PREREQUISITE,
    OBJECTION_CAREER_OUTCOME,
    OBJECTION_PARENTAL_APPROVAL,
    OBJECTION_TRUST,
    OBJECTION_COMPARISON,
    OBJECTION_COURSE_FIT,
    OBJECTION_DIFFICULTY,
    OBJECTION_FORMAT,
    OBJECTION_UNKNOWN,
    HANDLING_READY,
    HANDLING_CLARIFICATION,
    HANDLING_HANDOFF,
    HANDLING_UNKNOWN,
    ObjectionSignal,
    ObjectionResponsePlan,
    detect_objection,
    build_objection_response_plan,
    objection_response_to_dict,
    validate_objection_response_plan,
    run_objection_intelligence,
)


passed = 0
total = 0


def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


# Detection
s = detect_objection("The fees are too expensive for me.")
check(s.objection_type == OBJECTION_FEE, "Fee objection detection")

s = detect_objection("I am working and do not have enough time.")
check(s.objection_type == OBJECTION_TIME, "Time objection detection")

s = detect_objection("I don't have a technical background. Is that a problem?")
check(s.objection_type == OBJECTION_PREREQUISITE, "Prerequisite objection detection")

s = detect_objection("Will you guarantee a job or salary?")
check(s.objection_type == OBJECTION_CAREER_OUTCOME, "Career outcome objection detection")

s = detect_objection("I need to discuss this with my parents.")
check(s.objection_type == OBJECTION_PARENTAL_APPROVAL, "Parental approval detection")

s = detect_objection("How do I know this is genuine and not a scam?")
check(s.objection_type == OBJECTION_TRUST, "Trust objection detection")

s = detect_objection("I want to compare this with another institute.")
check(s.objection_type == OBJECTION_COMPARISON, "Comparison objection detection")

s = detect_objection("I am not sure which course is right for me.")
check(s.objection_type == OBJECTION_COURSE_FIT, "Course fit objection detection")

s = detect_objection("I am worried the coding will be too difficult.")
check(s.objection_type == OBJECTION_DIFFICULTY, "Difficulty objection detection")

s = detect_objection("Do you offer online classes?")
check(s.objection_type == OBJECTION_FORMAT, "Format objection detection")

s = detect_objection("")
check(s.objection_type == OBJECTION_UNKNOWN, "Empty message should be unknown")

s = detect_objection("Hello, tell me more about the course.")
check(s.objection_type == OBJECTION_NONE, "Non-objection should not be forced into a category")

# Basic plans
p = build_objection_response_plan("The course fee is too expensive.", session_id="O11-001")
check(p.status == HANDLING_READY, "Fee plan should be ready")
check(p.objection.objection_type == OBJECTION_FEE, "Fee plan preserves type")
check(bool(p.acknowledgement), "Fee plan has acknowledgement")
check(bool(p.response_points), "Fee plan has response points")
check(bool(p.clarification_questions), "Fee plan has clarification question")
check(bool(p.safe_next_steps), "Fee plan has next steps")

p = build_objection_response_plan("I need to think about it with my parents.", session_id="O11-002")
check(p.objection.objection_type == OBJECTION_PARENTAL_APPROVAL, "Family plan type")
check(p.status == HANDLING_READY, "Family plan ready")

p = build_objection_response_plan("I don't have the background for this.", session_id="O11-003")
check(p.status == HANDLING_READY, "Prerequisite plan ready")

# Multi-objection safety
p = build_objection_response_plan(
    "The fees are expensive and I also don't have enough time.",
    session_id="O11-004",
)
check(p.status == HANDLING_CLARIFICATION, "Multiple objections should clarify")
check(len(p.clarification_questions) >= 2, "Multiple objections should have clarification questions")

# Unknown/none safety
p = build_objection_response_plan("", session_id="O11-005")
check(p.status == HANDLING_CLARIFICATION, "Unknown objection should clarify")
check(bool(p.clarification_questions), "Unknown objection has question")

p = build_objection_response_plan("Please explain the course.", session_id="O11-006")
check(p.status == HANDLING_UNKNOWN, "Non-objection should remain unknown handling")

# Safety flags
p = run_objection_intelligence("Will I definitely get a job?", session_id="O11-007")
check(p.objection.objection_type == OBJECTION_CAREER_OUTCOME, "Career concern type")
check(p.no_invention is True, "No invention stays enabled")
check(p.execution_enabled is False, "Execution disabled")
check(p.messaging_enabled is False, "Messaging disabled")
check(p.external_actions_enabled is False, "External actions disabled")
check(p.crm_writes_enabled is False, "CRM writes disabled")
check(bool(p.prohibited_claims), "Prohibited claims present")

# Career safety wording
career_text = " ".join(p.response_points + p.prohibited_claims).lower()
check("guarantee" in career_text, "Career response addresses guarantee safety")
check("placement" in career_text, "Career response addresses placement safety")
check("salary" in career_text, "Career response addresses salary safety")

# International fee safety
p = build_objection_response_plan("The fees are too high.", session_id="O11-008")
fee_text = " ".join(p.response_points).lower()
check("international" in fee_text, "Fee handling mentions international region safety")
check("indian pricing" in fee_text, "Fee handling prevents India pricing fallback")

# Trust/certification safety
p = run_objection_intelligence("Is the certification accredited?", session_id="O11-009")
trust_text = " ".join(p.response_points + p.prohibited_claims).lower()
check(p.objection.objection_type == OBJECTION_TRUST, "Certification trust type")
check("certification" in trust_text, "Certification safety is explicit")
check("accreditation" in trust_text, "Accreditation safety is explicit")

# Comparison safety
p = run_objection_intelligence("Is your institute better than another institute?", session_id="O11-010")
comparison_text = " ".join(p.response_points + p.prohibited_claims).lower()
check(p.status == HANDLING_READY, "Comparison objection ready")
check("competitor" in comparison_text, "Comparison avoids unsupported competitor facts")
check("superiority" in comparison_text, "Comparison avoids unsupported superiority")

# Course-fit safety
p = run_objection_intelligence("Which course is right for me?", session_id="O11-011")
check(p.objection.objection_type == OBJECTION_COURSE_FIT, "Course-fit type")
check(len(p.clarification_questions) >= 1, "Course-fit asks targeted question")

# Difficulty safety
p = run_objection_intelligence("I am worried this will be too difficult.", session_id="O11-012")
check(p.status == HANDLING_READY, "Difficulty handling ready")
difficulty_text = " ".join(p.response_points + p.prohibited_claims).lower()
check("guarantee" in difficulty_text, "Difficulty avoids guaranteed success")

# Format safety
p = run_objection_intelligence("Can I attend offline?", session_id="O11-013")
check(p.objection.objection_type == OBJECTION_FORMAT, "Format type")
check("documented" in " ".join(p.response_points).lower(), "Format uses documented information")

# Handoff preservation from readiness
class ReviewReadiness:
    human_handoff_required = True
    handoff_reason = "Existing admission review required."

p = build_objection_response_plan(
    "The fees are too high.",
    session_id="O11-014",
    admission_readiness=ReviewReadiness(),
)
check(p.status == HANDLING_HANDOFF, "Existing readiness review should handoff")
check(p.human_handoff_required is True, "Readiness handoff flag preserved")
check("admission review" in (p.handoff_reason or "").lower(), "Readiness handoff reason preserved")

# Validation
p = run_objection_intelligence("I need to compare courses.", session_id="O11-015")
v = validate_objection_response_plan(p)
check(v["valid"] is True, "Valid plan validates")

d = objection_response_to_dict(p)
check(d["session_id"] == "O11-015", "Serialization preserves session")
check(d["status"] == p.status, "Serialization preserves status")
check(d["objection"]["objection_type"] == p.objection.objection_type, "Serialization preserves objection")
check(d["no_invention"] is True, "Serialization preserves no invention")

# Defensive list serialization
check(d["response_points"] is not p.response_points, "Serialization copies response points")
check(d["prohibited_claims"] is not p.prohibited_claims, "Serialization copies prohibited claims")

# Explicit-text preservation
check(p.objection.explicit_text == "I need to compare courses.", "Explicit message preserved")

# Handoff validator
bad = ObjectionResponsePlan(
    session_id="BAD-01",
    status=HANDLING_HANDOFF,
    objection=ObjectionSignal(OBJECTION_FEE, "high"),
)
v = validate_objection_response_plan(bad)
check(v["valid"] is False, "Invalid handoff must fail validation")
check(any("human_handoff_required" in e for e in v["errors"]), "Invalid handoff reports flag error")

# Safety mutation tests
bad = run_objection_intelligence("The price is high.", session_id="O11-016")
bad.execution_enabled = True
v = validate_objection_response_plan(bad)
check(v["valid"] is False, "Execution mutation must fail validation")

bad = run_objection_intelligence("The price is high.", session_id="O11-017")
bad.crm_writes_enabled = True
v = validate_objection_response_plan(bad)
check(v["valid"] is False, "CRM mutation must fail validation")

# Fail-closed behavior
bad = run_objection_intelligence("The price is high.", session_id="O11-018")
bad.prohibited_claims = []
v = validate_objection_response_plan(bad)
check(v["valid"] is False, "Missing prohibited claims must fail validation")

# Determinism
a = detect_objection("The fees are expensive.")
b = detect_objection("The fees are expensive.")
check(a.objection_type == b.objection_type, "Detection is deterministic")
check(a.matched_terms == b.matched_terms, "Matched terms are deterministic")

print(f"AI CORE 11: {passed}/{total} PASSED")
