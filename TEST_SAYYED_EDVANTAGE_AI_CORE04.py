import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE04 import (
    RECOMMENDATION_READY,
    RECOMMENDATION_NEEDS_CLARIFICATION,
    RECOMMENDATION_EXPLICIT,
    build_course_candidates,
    recommend_courses,
    recommendation_to_dict,
    validate_recommendation,
    build_recommendation_layer,
)
from Sayyed_EdVantage_AI_CORE03 import understand_message
from Sayyed_EdVantage_AI_CORE02 import create_conversation_context
from Sayyed_EdVantage_AI_CORE01 import create_session

passed = total = 0
def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_recommendation_layer()

# 1–8: explicit single-course selection
ds = recommend_courses(kb, "I want Data Science")
check(ds.status == RECOMMENDATION_EXPLICIT, "Explicit DS should be explicit")
check(ds.primary_course_id == "SE-DS-001", "DS primary missing")
check(len(ds.candidates) == 1, "Single explicit course should have one candidate")
check(ds.candidates[0].course_id == "SE-DS-001", "DS candidate mismatch")
check(ds.candidates[0].score == 100, "Explicit candidate score mismatch")
check(ds.clarification_needed is False, "Explicit course should not need clarification")
check(ds.no_invention is True, "No-invention must remain true")
check(validate_recommendation(ds)["valid"], "DS recommendation invalid")

# 9–15: explicit other courses
for phrase, expected in [
    ("Tell me about Python", "SE-PY-001"),
    ("I am interested in Linux", "SE-LINUX-001"),
    ("I want to learn DevOps", "SE-DEVOPS-001"),
    ("Tell me about cybersecurity", "SE-EHC-001"),
    ("I want generative AI", "SE-AIGEN-001"),
    ("I want Data Analytics", "SE-DA-001"),
]:
    result = recommend_courses(kb, phrase)
    check(result.primary_course_id == expected,
          f"Primary course mismatch for {phrase}")
    check(result.status == RECOMMENDATION_EXPLICIT,
          f"Explicit status mismatch for {phrase}")

# 16–22: established context
state = create_session("REC-CTX-001")
ctx = create_conversation_context(state.session_id)
first = recommend_courses(kb, "Tell me about Python", ctx)
ctx.active_course_ids = ["SE-PY-001"]
ctx.active_intent = "program_information"
follow = recommend_courses(kb, "How much does it cost?", ctx)
check(follow.status == RECOMMENDATION_READY,
      "Context-derived course should be ready")
check(follow.primary_course_id == "SE-PY-001",
      "Context-derived Python missing")
check(len(follow.candidates) == 1,
      "Context-derived result should have one candidate")
check(follow.candidates[0].score == 80,
      "Context candidate score mismatch")
check(follow.clarification_needed is False,
      "Established context should not need clarification")
check("conversation context" in follow.evidence[0],
      "Context evidence missing")
check(validate_recommendation(follow)["valid"],
      "Context recommendation invalid")

# 23–28: no course evidence requires clarification
unclear = recommend_courses(kb, "Which course should I choose?")
check(unclear.status == RECOMMENDATION_NEEDS_CLARIFICATION,
      "Generic recommendation must need clarification")
check(unclear.primary_course_id is None,
      "Generic recommendation must not choose a primary")
check(unclear.clarification_needed is True,
      "Clarification flag missing")
check(unclear.clarification_reason,
      "Clarification reason missing")
check(len(unclear.candidates) == 7,
      "Generic recommendation should expose all seven course candidates")
check(validate_recommendation(unclear)["valid"],
      "Generic clarification result invalid")

# 29–34: multiple courses are preserved, not silently selected
multi = recommend_courses(
    kb,
    "Compare Data Science and Data Analytics",
)
check(multi.status == RECOMMENDATION_NEEDS_CLARIFICATION,
      "Multi-course comparison should need clarification")
check(multi.primary_course_id is None,
      "Multi-course comparison must not select one")
check(multi.clarification_needed is True,
      "Multi-course clarification missing")
check(len(multi.candidates) == 2,
      "Multi-course candidates mismatch")
check(
    {c.course_id for c in multi.candidates}
    == {"SE-DS-001", "SE-DA-001"},
    "Multi-course IDs mismatch",
)
check(validate_recommendation(multi)["valid"],
      "Multi-course recommendation invalid")

# 35–39: deterministic candidate ordering
generic = recommend_courses(kb, "Which course is suitable?")
ids = [c.course_id for c in generic.candidates]
check(len(ids) == 7, "Generic candidate count mismatch")
check(ids == sorted(ids), "Generic candidates must be deterministic")
check(all(c.score == 80 for c in generic.candidates),
      "Catalog candidates should have equal neutral score")
check(all(c.reasons for c in generic.candidates),
      "Every candidate needs an evidence reason")
check(validate_recommendation(generic)["valid"],
      "Generic deterministic recommendation invalid")

# 40–44: serialization is complete and defensive
data = recommendation_to_dict(ds)
check(data["primary_course_id"] == "SE-DS-001",
      "Recommendation serialization primary mismatch")
check(data["candidates"][0]["course_id"] == "SE-DS-001",
      "Recommendation serialization candidate mismatch")
check(data["no_invention"] is True,
      "Recommendation serialization safety mismatch")
data["candidates"].append({"course_id": "MUTATION"})
check(len(ds.candidates) == 1,
      "Serialization mutated candidates")

# 45–50: no invented recommendation evidence
check(unclear.evidence == ["course-selection evidence is insufficient"],
      "Insufficient-evidence wording mismatch")
check(unclear.no_invention is True,
      "No-invention failed for generic recommendation")
check(multi.evidence == ["multiple explicit course references"],
      "Multi-course evidence mismatch")
check(multi.primary_course_id is None,
      "No invented primary for multi-course")
check(ds.evidence == ["single course explicitly identified by the user"],
      "Explicit evidence mismatch")
check(validate_recommendation(ds)["valid"],
      "Final explicit recommendation validation failed")

print(f"AI CORE 04: {passed}/{total} PASSED")
