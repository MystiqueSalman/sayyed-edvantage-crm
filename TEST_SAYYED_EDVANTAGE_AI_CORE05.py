import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE05 import (
    PROFILE_READY, PROFILE_EMPTY, PROFILE_CLARIFICATION,
    create_prospect_profile, update_prospect_profile,
    identify_missing_fields, qualify_for_recommendation,
    validate_prospect_profile, profile_to_dict,
    qualification_to_dict, build_prospect_qualification_layer,
)

passed = total = 0
def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_prospect_qualification_layer()

# 1–8: empty profile
p = create_prospect_profile("PROF-001")
check(p.session_id == "PROF-001", "Profile session mismatch")
check(p.profile_status == PROFILE_EMPTY, "New profile should be empty")
check(p.experience.status == "unknown", "Experience should start unknown")
check(p.learning_goal.status == "unknown", "Learning goal should start unknown")
check(p.region.status == "unknown", "Region should start unknown")
check(p.budget.status == "unknown", "Budget should start unknown")
check(identify_missing_fields(p) == ["learning_goal", "experience"],
      "Missing recommendation fields mismatch")
check(validate_prospect_profile(p)["valid"], "Empty profile validation failed")

# 9–17: explicit facts are extracted
r1 = update_prospect_profile(
    p,
    "I am a fresher and I want to learn Data Science. I am from India."
)
check("experience" in r1.newly_extracted_fields, "Experience not extracted")
check(p.experience.value == "fresher", "Fresher value mismatch")
check(p.learning_goal.value == "learn Data Science", "Learning goal mismatch")
check(p.region.value == "India", "Region mismatch")
check(p.profile_status == PROFILE_READY, "Profile should become ready")
check(p.experience.evidence == [r1.profile.experience.evidence[0]],
      "Experience evidence not preserved")
check(r1.no_invention is True, "No-invention failed")
check(validate_prospect_profile(p)["valid"], "Profile validation failed")
check(qualify_for_recommendation(p).clarification_needed is False,
      "Complete recommendation context should not need clarification")

# 18–25: education/technical/career/current role
r2 = update_prospect_profile(
    p,
    "I have a B.Tech and I know Python and SQL. I am a developer and want "
    "to become a Data Scientist."
)
check(p.education.value == "B.Tech", "Education extraction failed")
check("python" in p.technical_background.value, "Python background missing")
check("sql" in p.technical_background.value, "SQL background missing")
check(p.current_role.value == "developer", "Current role extraction failed")
check(p.career_goal.value == "become a Data Scientist",
      "Career goal extraction failed")
check("education" in r2.newly_extracted_fields, "Education not reported")
check("career_goal" in r2.newly_extracted_fields, "Career goal not reported")
check(validate_prospect_profile(p)["valid"], "Expanded profile invalid")

# 26–31: existing known facts are not silently overwritten
before = p.experience.value
r3 = update_prospect_profile(p, "I am a student with 5 years of experience.")
check(p.experience.value == before, "Known experience was overwritten")
check(p.current_role.value == "developer",
      "Known current role was overwritten")
check("experience" not in r3.newly_extracted_fields,
      "Overwritten experience should not be reported as newly extracted")
check(p.learning_goal.value == "learn Data Science",
      "Known learning goal changed unexpectedly")
check(p.region.value == "India", "Known region changed unexpectedly")
check(validate_prospect_profile(p)["valid"], "Profile after conflict invalid")

# 32–37: missing context is explicit
p2 = create_prospect_profile("PROF-002")
update_prospect_profile(p2, "I am a fresher.")
q2 = qualify_for_recommendation(p2)
check(q2.clarification_needed is True, "Missing goal should need clarification")
check("learning_goal" in q2.clarification_reason,
      "Missing learning goal not identified")
check(p2.learning_goal.status == "unknown",
      "Unknown learning goal should remain unknown")
check(p2.experience.value == "fresher",
      "Fresher fact lost")
check(q2.no_invention is True, "No-invention failed in clarification")
check(validate_prospect_profile(p2)["valid"], "Partial profile invalid")

# 38–42: budget and international region are literal facts only
p3 = create_prospect_profile("PROF-003")
update_prospect_profile(
    p3,
    "I am an international student and my budget is ₹50,000."
)
check(p3.region.value == "International", "International region failed")
check(p3.budget.value == "₹50,000", "Budget literal value mismatch")
check(p3.budget.status == "known", "Budget should be known")
check(p3.budget.evidence, "Budget evidence missing")
check(validate_prospect_profile(p3)["valid"], "Budget profile invalid")

# 43–47: unknown facts are not inferred
p4 = create_prospect_profile("PROF-004")
update_prospect_profile(p4, "I want Data Analytics.")
check(p4.education.status == "unknown", "Education was invented")
check(p4.experience.status == "unknown", "Experience was invented")
check(p4.region.status == "unknown", "Region was invented")
check(p4.budget.status == "unknown", "Budget was invented")
check(p4.learning_goal.status == "unknown",
      "Learning goal should not be inferred from course mention")

# 48–52: serialization is defensive
d = profile_to_dict(p)
qd = qualification_to_dict(r2)
check(d["session_id"] == "PROF-001", "Profile serialization ID mismatch")
check(d["experience"]["value"] == "fresher", "Profile serialization value mismatch")
check("evidence" in d["learning_goal"], "Profile evidence serialization missing")
check(qd["no_invention"] is True, "Qualification serialization safety missing")
d["experience"]["evidence"].append("MUTATION")
check("MUTATION" not in p.experience.evidence,
      "Profile serialization mutated original")

# 53–56: final invariants
check(p.budget.status == "unknown", "Budget must remain unknown when unstated")
check(p.technical_background.status == "known",
      "Technical background should remain known")
check(validate_prospect_profile(p)["valid"],
      "Final profile validation failed")
check(qualify_for_recommendation(p).clarification_needed is False,
      "Final complete profile should qualify")

print(f"AI CORE 05: {passed}/{total} PASSED")
