import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE07 import (
    NEED_READY, NEED_CLARIFICATION, NEED_UNKNOWN,
    synthesize_student_need, synthesize_need_from_recommendation,
    build_need_profile, validate_need_profile,
    need_profile_to_dict, build_need_synthesis_layer,
)
from Sayyed_EdVantage_AI_CORE05 import (
    create_prospect_profile, update_prospect_profile,
)
from Sayyed_EdVantage_AI_CORE04 import recommend_courses

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c:
        raise AssertionError(label)
    passed += 1

kb = build_need_synthesis_layer()

# 1–8: empty/unknown need profile
p = create_prospect_profile("NEED-001")
n = synthesize_student_need(p)
check(n.session_id == "NEED-001", "Session ID mismatch")
check(n.status == NEED_UNKNOWN, "Empty need should be unknown")
check(n.stated_goal is None, "Goal should be unknown")
check(n.experience_level is None, "Experience should be unknown")
check(n.course_ids == [], "Course IDs should be empty")
check("learning_goal" in n.unknown_fields, "Goal missing field")
check("experience" in n.unknown_fields, "Experience missing field")
check(validate_need_profile(n)["valid"], "Empty need validation failed")

# 9–18: explicit profile facts become explicit need signals
p2 = create_prospect_profile("NEED-002")
update_prospect_profile(
    p2,
    "I am a fresher with a B.Tech. I know Python and SQL. "
    "I want to become a Data Scientist. I am from India."
)
n2 = synthesize_student_need(
    p2, intent="course_recommendation", course_ids=["SE-DS-001"]
)
check(n2.status == NEED_READY, "Complete need should be ready")
check(n2.stated_goal == "become a Data Scientist", "Goal mismatch")
check(n2.experience_level == "fresher", "Experience mismatch")
check(n2.education == "B.Tech", "Education mismatch")
check("python" in n2.technical_background, "Python background missing")
check("sql" in n2.technical_background, "SQL background missing")
check(n2.region == "India", "Region mismatch")
check(n2.course_ids == ["SE-DS-001"], "Course context mismatch")
check(n2.intent == "course_recommendation", "Intent mismatch")
check(validate_need_profile(n2)["valid"], "Complete need invalid")

# 19–26: unstated facts remain unknown and generate clarification
p3 = create_prospect_profile("NEED-003")
update_prospect_profile(p3, "I am a fresher.")
n3 = synthesize_student_need(p3)
check(n3.status == NEED_CLARIFICATION, "Partial need should need clarification")
check(n3.experience_level == "fresher", "Fresher fact lost")
check(n3.stated_goal is None, "Goal should remain unknown")
check("learning_goal" in n3.unknown_fields, "Goal unknown not tracked")
check(n3.clarification_questions, "Clarification questions missing")
check(any("goal" in q.lower() for q in n3.clarification_questions),
      "Goal question missing")
check(n3.no_invention is True, "No-invention failed")
check(validate_need_profile(n3)["valid"], "Partial need invalid")

# 27–34: recommendation evidence is kept separate
p4 = create_prospect_profile("NEED-004")
update_prospect_profile(p4, "I want Data Science.")
rec = recommend_courses(kb, "I want Data Science.")
n4 = synthesize_need_from_recommendation(
    p4, rec, intent="program_information"
)
check("SE-DS-001" in n4.course_ids, "Recommendation course missing")
check(n4.status in {NEED_READY, NEED_CLARIFICATION},
      "Recommendation need status invalid")
check(n4.no_invention is True, "Recommendation no-invention failed")
check(validate_need_profile(n4)["valid"], "Recommendation need invalid")
check(n4.course_ids.count("SE-DS-001") == 1,
      "Duplicate recommendation course")
check(n4.intent == "program_information", "Recommendation intent mismatch")
check(isinstance(n4.signals, list), "Need signals missing")
check(isinstance(n4.unknown_fields, list), "Unknown fields missing")

# 35–42: multiple courses do not silently select one
p5 = create_prospect_profile("NEED-005")
rec_multi = recommend_courses(
    kb, "Compare Data Science and Data Analytics"
)
n5 = synthesize_need_from_recommendation(
    p5, rec_multi, intent="comparison"
)
check(n5.course_ids == ["SE-DS-001", "SE-DA-001"],
      "Multi-course IDs must be preserved")
check(n5.status == NEED_CLARIFICATION,
      "Multi-course need should require clarification")
check(n5.clarification_questions, "Multi-course questions missing")
check(n5.no_invention is True, "Multi-course no-invention failed")
check(validate_need_profile(n5)["valid"], "Multi-course need invalid")
check(n5.stated_goal is None, "Goal should not be invented")
check(n5.experience_level is None, "Experience should not be invented")
check(n5.budget is None, "Budget should not be invented")

# 43–49: literal budget/region are retained only if explicitly stated
p6 = create_prospect_profile("NEED-006")
update_prospect_profile(
    p6, "I am an international student and my budget is ₹50,000."
)
n6 = synthesize_student_need(p6)
check(n6.region == "International", "International region lost")
check(n6.budget == "₹50,000", "Budget literal value lost")
check("region" not in n6.unknown_fields, "Known region still unknown")
check("budget" not in n6.unknown_fields, "Known budget still unknown")
check(n6.no_invention is True, "Literal fact no-invention failed")
check(validate_need_profile(n6)["valid"], "Literal fact need invalid")
check(n6.course_ids == [], "No course should be invented")

# 50–55: defensive serialization
data = need_profile_to_dict(n2)
check(data["session_id"] == "NEED-002", "Serialization ID mismatch")
check(data["stated_goal"] == "become a Data Scientist",
      "Serialization goal mismatch")
check(data["course_ids"] == ["SE-DS-001"],
      "Serialization course mismatch")
check(data["no_invention"] is True, "Serialization safety missing")
check(data["signals"], "Serialization signals missing")
data["course_ids"].append("MUTATION")
check("MUTATION" not in n2.course_ids,
      "Serialization mutated original")

# 56–60: invalid profile is controlled
p_bad = create_prospect_profile("NEED-BAD")
p_bad.experience.status = "bad_status"
bad = synthesize_student_need(p_bad)
check(bad.status == NEED_CLARIFICATION, "Invalid profile must clarify")
check(bad.clarification_questions, "Invalid profile needs question")
check(bad.no_invention is True, "Invalid profile no-invention failed")
check(validate_need_profile(bad)["valid"], "Returned controlled need invalid")
check(bad.course_ids == [], "Invalid profile must not invent courses")

print(f"AI CORE 07: {passed}/{total} PASSED")
