import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE06 import (
    ELIGIBILITY_READY, ELIGIBILITY_INSUFFICIENT, ELIGIBILITY_CLARIFICATION,
    evaluate_course_eligibility, evaluate_eligibility,
    eligibility_to_dict, validate_eligibility, build_eligibility_layer,
)
from Sayyed_EdVantage_AI_CORE05 import create_prospect_profile, update_prospect_profile

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

kb = build_eligibility_layer()

# 1–8: course evaluation is KB-grounded
p = create_prospect_profile("ELIG-001")
update_prospect_profile(p, "I am a fresher and I want to learn Data Science.")
r = evaluate_course_eligibility(kb, p, "SE-DS-001")
check(r.course_id == "SE-DS-001", "Course ID mismatch")
check(r.official_name, "Official name missing")
check(r.status in {"SUPPORTED","INSUFFICIENT_INFORMATION","NOT_ESTABLISHED","UNKNOWN_COURSE"}, "Invalid course status")
check(isinstance(r.satisfied, list), "Satisfied list missing")
check(isinstance(r.unknown, list), "Unknown list missing")
check(isinstance(r.unsupported, list), "Unsupported list missing")
check(r.evidence is not None, "Evidence missing")
check(not (set(r.satisfied) & set(r.unknown)), "Satisfied/unknown overlap")

# 9–15: no course is insufficient
x = evaluate_eligibility(kb, p, [])
check(x.status == ELIGIBILITY_INSUFFICIENT, "No-course status")
check(x.clarification_needed is True, "No-course clarification")
check(x.recommendation_ready is False, "No-course recommendation readiness")
check(x.clarification_reason, "No-course reason")
check(x.course_results == [], "No-course results should be empty")
check(x.no_invention is True, "No-invention failed")
check(validate_eligibility(x)["valid"], "No-course validation")

# 16–23: multiple courses remain separate
p2 = create_prospect_profile("ELIG-002")
update_prospect_profile(p2, "I am a B.Tech graduate and a fresher. I know Python.")
m = evaluate_eligibility(kb, p2, ["SE-DS-001", "SE-DA-001"])
check(len(m.course_results) == 2, "Two course results required")
check({r.course_id for r in m.course_results} == {"SE-DS-001","SE-DA-001"}, "Course IDs mismatch")
check(all(r.official_name for r in m.course_results), "Official names missing")
check(m.status in {ELIGIBILITY_READY, ELIGIBILITY_INSUFFICIENT, ELIGIBILITY_CLARIFICATION}, "Invalid multi status")
check(m.no_invention is True, "Multi no-invention failed")
check(validate_eligibility(m)["valid"], "Multi validation")
check(m.recommendation_ready in {True, False}, "Recommendation flag invalid")
check(m.clarification_needed in {True, False}, "Clarification flag invalid")

# 24–31: sparse profile never invents facts
p3 = create_prospect_profile("ELIG-003")
update_prospect_profile(p3, "I want Data Analytics.")
s = evaluate_eligibility(kb, p3, ["SE-DA-001"])
check(s.no_invention is True, "Sparse no-invention")
check(validate_eligibility(s)["valid"], "Sparse validation")
check(p3.education.status == "unknown", "Education invented")
check(p3.experience.status == "unknown", "Experience invented")
check(p3.region.status == "unknown", "Region invented")
check(p3.budget.status == "unknown", "Budget invented")
check(p3.learning_goal.status == "unknown", "Learning goal invented")
check(s.clarification_needed or s.status == ELIGIBILITY_READY, "Unsafe sparse result")

# 32–39: unknown course is explicit
u = evaluate_course_eligibility(kb, p3, "SE-NOT-A-REAL-COURSE")
check(u.status == "UNKNOWN_COURSE", "Unknown course status")
check(u.unknown == ["course record"], "Unknown course diagnostic")
check(u.satisfied == [], "Unknown course satisfied facts")
check(u.unsupported == [], "Unknown course unsupported facts")
check(u.evidence, "Unknown course evidence")
ue = evaluate_eligibility(kb, p3, ["SE-NOT-A-REAL-COURSE"])
check(ue.clarification_needed is True, "Unknown course clarification")
check(ue.recommendation_ready is False, "Unknown course readiness")
check(validate_eligibility(ue)["valid"], "Unknown course validation")

# 40–46: serialization defensive
d = eligibility_to_dict(m)
check(d["session_id"] == "ELIG-002", "Serialization session")
check(len(d["course_results"]) == 2, "Serialization course count")
check("satisfied" in d["course_results"][0], "Satisfied serialization")
check("unknown" in d["course_results"][0], "Unknown serialization")
check(d["no_invention"] is True, "Serialization safety")
d["course_results"].append({"course_id":"MUTATION"})
check(len(m.course_results) == 2, "Serialization mutated original")

# 47–52: final invariants
check(validate_eligibility(m)["valid"], "Final validation")
check(all(r.course_id for r in m.course_results), "Missing result ID")
check(all(r.official_name for r in m.course_results), "Missing official name")
check(all(r.status for r in m.course_results), "Missing result status")
check(m.no_invention is True, "Final no-invention")
check(isinstance(m.evidence, list), "Final evidence structure")

print(f"AI CORE 06: {passed}/{total} PASSED")
