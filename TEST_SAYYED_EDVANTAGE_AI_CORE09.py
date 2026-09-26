import os, sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE09 import (
    COUNSELLING_DISCOVERY, COUNSELLING_RECOMMENDATION,
    COUNSELLING_CLARIFICATION, COUNSELLING_REVIEW,
    CounsellingQuestion, CounsellingPlan,
    build_counselling_plan, counselling_response_guidance,
    counselling_plan_to_dict, validate_counselling_plan,
    run_counselling_intelligence,
)
from Sayyed_EdVantage_AI_CORE07 import StudentNeedProfile, NEED_READY
from Sayyed_EdVantage_AI_CORE08 import (
    DECISION_RECOMMEND, DECISION_CLARIFICATION, DECISION_UNKNOWN,
    DECISION_REVIEW,
)

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

def decision(status, primary=None, candidates=None, rationale=None, questions=None):
    return SimpleNamespace(
        session_id="DEC", status=status, primary_course_id=primary,
        candidate_course_ids=list(candidates or ([] if primary is None else [primary])),
        scores=[], rationale=list(rationale or []),
        clarification_questions=list(questions or []), source_ids=[],
        no_invention=True, execution_enabled=False, messaging_enabled=False,
        external_actions_enabled=False, crm_writes_enabled=False,
    )

# 1–10 discovery
n0 = StudentNeedProfile(session_id="COUN-001", status="NEED_UNKNOWN")
p0 = build_counselling_plan(n0, decision(DECISION_UNKNOWN))
check(p0.session_id == "COUN-001", "Discovery session mismatch")
check(p0.stage == COUNSELLING_DISCOVERY, "Unknown need should enter discovery")
check(p0.primary_course_id is None, "Discovery must not select course")
check(p0.questions, "Discovery question missing")
check(p0.questions[0].field == "learning_goal", "Goal question should lead discovery")
check("goal" in p0.questions[0].question.lower(), "Goal question wording missing")
check(p0.next_steps, "Discovery next step missing")
check(p0.no_invention is True, "Discovery no-invention failed")
check(p0.execution_enabled is False, "Discovery execution must be disabled")
check(validate_counselling_plan(p0)["valid"], "Discovery plan invalid")

# 11–22 recommendation
n1 = StudentNeedProfile(session_id="COUN-002", stated_goal="become a Data Scientist",
    experience_level="fresher", education="B.Tech", course_ids=["SE-DS-001"], status=NEED_READY)
d1 = decision(DECISION_RECOMMEND, primary="SE-DS-001", candidates=["SE-DS-001"],
              rationale=["Single supported recommendation candidate is available."])
p1 = build_counselling_plan(n1, d1)
check(p1.stage == COUNSELLING_RECOMMENDATION, "Single recommendation should enter recommendation stage")
check(p1.primary_course_id == "SE-DS-001", "Counselling primary mismatch")
check(p1.candidate_course_ids == ["SE-DS-001"], "Counselling candidates mismatch")
check("learning_goal" in p1.confirmed_need_fields, "Goal confirmation missing")
check("experience" in p1.confirmed_need_fields, "Experience confirmation missing")
check("education" in p1.confirmed_need_fields, "Education confirmation missing")
check("budget" in p1.unknown_need_fields, "Unknown budget not tracked")
check(p1.questions == [], "Recommendation should not require clarification question")
check(p1.recommendation_rationale, "Recommendation rationale missing")
check(p1.next_steps, "Recommendation next steps missing")
check(any("fee" in step.lower() or "region" in step.lower() for step in p1.next_steps), "Region-aware commercial next step missing")
check(validate_counselling_plan(p1)["valid"], "Recommendation plan invalid")

# 23–32 clarification
n2 = StudentNeedProfile(session_id="COUN-003", status="NEED_CLARIFICATION")
d2 = decision(DECISION_CLARIFICATION, candidates=["SE-DS-001", "SE-DA-001"],
              rationale=["Multiple supported course candidates were returned."],
              questions=["Which course or course area are you most interested in?"])
p2 = build_counselling_plan(n2, d2)
check(p2.stage == COUNSELLING_CLARIFICATION, "Multi-course should clarify")
check(p2.primary_course_id is None, "Clarification must not select primary")
check(p2.candidate_course_ids == ["SE-DS-001", "SE-DA-001"], "Clarification candidates changed")
check(len(p2.questions) == 1, "Exactly one course clarification question expected")
check(p2.questions[0].field == "course_interest", "Course clarification field mismatch")
check("Which course" in p2.questions[0].question, "Clarification wording mismatch")
check(p2.next_steps, "Clarification next step missing")
check(p2.no_invention is True, "Clarification no-invention failed")
check(p2.crm_writes_enabled is False, "Clarification CRM writes must be disabled")
check(validate_counselling_plan(p2)["valid"], "Clarification plan invalid")

# 33–40 partial
n3 = StudentNeedProfile(session_id="COUN-004", stated_goal="learn Python", status=NEED_READY)
d3 = decision(DECISION_RECOMMEND, primary="SE-PY-001", candidates=["SE-PY-001"],
              rationale=["Single supported recommendation candidate is available."])
p3 = run_counselling_intelligence(n3, d3)
check(p3.stage == COUNSELLING_RECOMMENDATION, "Partial need should not be blocked unnecessarily")
check(p3.primary_course_id == "SE-PY-001", "Partial need primary mismatch")
check("experience" in p3.unknown_need_fields, "Missing experience not tracked")
check("technical_background" in p3.unknown_need_fields, "Missing technical background not tracked")
check("budget" in p3.unknown_need_fields, "Missing budget not tracked")
check(p3.no_invention is True, "Partial need no-invention failed")
check(validate_counselling_plan(p3)["valid"], "Partial need plan invalid")
check(p3.external_actions_enabled is False, "External actions must be disabled")

# 41–47 review
n4 = StudentNeedProfile(session_id="COUN-005", status=NEED_READY)
d4 = decision(DECISION_REVIEW, candidates=["SE-PY-001"], rationale=["Recommendation requires review."])
p4 = build_counselling_plan(n4, d4)
check(p4.stage == COUNSELLING_REVIEW, "Review decision should enter review stage")
check(p4.handoff_required is True, "Review must require handoff")
check(p4.handoff_reason, "Review handoff reason missing")
check(p4.questions, "Review question missing")
check(p4.primary_course_id is None, "Review must not select primary")
check(validate_counselling_plan(p4)["valid"], "Review plan invalid")
check(p4.execution_enabled is False, "Review execution must be disabled")

# 48–54 validation safety
q = CounsellingQuestion("goal", "What is your goal?", "Goal missing")
plan = CounsellingPlan(session_id="COUN-006", stage=COUNSELLING_DISCOVERY, questions=[q])
check(validate_counselling_plan(plan)["valid"], "Basic plan should validate")
plan.execution_enabled = True
check(not validate_counselling_plan(plan)["valid"], "Unsafe execution flag must fail validation")
plan.execution_enabled = False
plan.no_invention = False
check(not validate_counselling_plan(plan)["valid"], "No-invention violation must fail validation")
plan.no_invention = True
plan.messaging_enabled = True
check(not validate_counselling_plan(plan)["valid"], "Messaging violation must fail validation")
plan.messaging_enabled = False
plan.handoff_required = True
check(not validate_counselling_plan(plan)["valid"], "Handoff without reason must fail validation")
plan.handoff_reason = "Human review required."
check(validate_counselling_plan(plan)["valid"], "Corrected handoff plan should validate")

# 55–60 serialization/guidance
g = counselling_response_guidance(p1)
check(g, "Recommendation guidance missing")
check(any("promise" in item.lower() for item in g), "Outcome safety guidance missing")
serialized = counselling_plan_to_dict(p1)
check(serialized["session_id"] == "COUN-002", "Serialization session mismatch")
check(serialized["primary_course_id"] == "SE-DS-001", "Serialization primary mismatch")
check(serialized["candidate_course_ids"] == ["SE-DS-001"], "Serialization candidates mismatch")
check(serialized["no_invention"] is True, "Serialization safety missing")
serialized["candidate_course_ids"].append("MUTATION")
check("MUTATION" not in p1.candidate_course_ids, "Serialization mutated original")

print(f"AI CORE 09: {passed}/{total} PASSED")
