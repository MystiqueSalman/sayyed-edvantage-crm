import os, sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE08 import (
    DECISION_RECOMMEND, DECISION_CLARIFICATION, DECISION_UNKNOWN,
    DECISION_REVIEW,
    RecommendationScore, RecommendationDecision,
    score_recommendation, decide_recommendation,
    build_recommendation_decision, run_recommendation_decision,
    recommendation_decision_to_dict, validate_recommendation_decision,
)
from Sayyed_EdVantage_AI_CORE07 import (
    StudentNeedProfile, NEED_READY, NEED_CLARIFICATION,
    NEED_UNKNOWN, validate_need_profile,
)
from Sayyed_EdVantage_AI_CORE04 import recommend_courses
from Sayyed_EdVantage_AI_CORE07 import build_need_synthesis_layer

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c:
        raise AssertionError(label)
    passed += 1

kb = build_need_synthesis_layer()

# Helpers create controlled recommendation objects so Core 08 can be tested
# without assuming undocumented Core 04 constructor details.
def rec(candidates, primary=None, clarification=False, source_ids=None):
    return SimpleNamespace(
        candidates=candidates,
        primary_course_id=primary,
        clarification_needed=clarification,
        source_ids=source_ids or [],
    )

def cand(course_id, score=None, reasons=None, evidence=None):
    return SimpleNamespace(
        course_id=course_id,
        official_name=course_id,
        score=score,
        reasons=reasons or [],
        evidence=evidence or [],
    )

# 1–10: empty/unknown decision
need0 = StudentNeedProfile(session_id="DEC-001")
r0 = rec([])
d0 = decide_recommendation(need0, r0)
check(d0.session_id == "DEC-001", "Session ID mismatch")
check(d0.status == DECISION_UNKNOWN, "Empty recommendation should be unknown")
check(d0.primary_course_id is None, "Unknown decision must not select course")
check(d0.candidate_course_ids == [], "Unknown candidates must be empty")
check(d0.clarification_questions, "Unknown decision needs a question")
check(d0.no_invention is True, "No-invention failed")
check(validate_recommendation_decision(d0)["valid"], "Unknown decision invalid")
check(score_recommendation(need0, r0) == [], "Empty scoring should be empty")
check(d0.execution_enabled is False, "Execution must be disabled")
check(d0.crm_writes_enabled is False, "CRM writes must be disabled")

# 11–22: one supported candidate -> recommend
need1 = StudentNeedProfile(
    session_id="DEC-002",
    stated_goal="become a Data Scientist",
    experience_level="fresher",
    course_ids=["SE-DS-001"],
    status=NEED_READY,
)
r1 = rec(
    [cand("SE-DS-001", 0.91, ["explicit course match"], ["KB-DS-001"])],
    primary="SE-DS-001",
    clarification=False,
    source_ids=["KB-DS-001"],
)
d1 = decide_recommendation(need1, r1)
check(d1.status == DECISION_RECOMMEND, "Single supported candidate should recommend")
check(d1.primary_course_id == "SE-DS-001", "Primary course mismatch")
check(d1.candidate_course_ids == ["SE-DS-001"], "Candidate IDs mismatch")
check(len(d1.scores) == 1, "Single score missing")
check(d1.scores[0].course_id == "SE-DS-001", "Score course mismatch")
check(d1.scores[0].rank == 1, "Rank mismatch")
check(d1.scores[0].upstream_score == 0.91, "Upstream score not preserved")
check(d1.scores[0].confidence == "HIGH", "Single candidate confidence mismatch")
check(d1.source_ids == ["KB-DS-001"], "Source IDs mismatch")
check(validate_recommendation_decision(d1)["valid"], "Recommend decision invalid")
check(d1.clarification_questions == [], "Recommend should not clarify")
check(d1.external_actions_enabled is False, "External actions must be disabled")

# 23–32: multi-course -> clarification, no silent selection
need2 = StudentNeedProfile(
    session_id="DEC-003",
    status=NEED_CLARIFICATION,
)
r2 = rec(
    [
        cand("SE-DS-001", 0.90, ["Data Science"], ["DS-SRC"]),
        cand("SE-DA-001", 0.89, ["Data Analytics"], ["DA-SRC"]),
    ],
    clarification=False,
)
d2 = decide_recommendation(need2, r2)
check(d2.status == DECISION_CLARIFICATION, "Multi-course must clarify")
check(d2.primary_course_id is None, "Multi-course must not select primary")
check(d2.candidate_course_ids == ["SE-DS-001", "SE-DA-001"],
      "Multi-course candidates changed")
check(len(d2.scores) == 2, "Multi-course scores missing")
check(d2.scores[0].rank == 1 and d2.scores[1].rank == 2,
      "Ranks not preserved")
check(d2.scores[0].upstream_score == 0.90, "First score changed")
check(d2.scores[1].upstream_score == 0.89, "Second score changed")
check(d2.clarification_questions, "Multi-course question missing")
check("Which course" in d2.clarification_questions[0],
      "Course clarification wording missing")
check(validate_recommendation_decision(d2)["valid"], "Multi-course decision invalid")

# 33–40: upstream clarification flag forces clarification
need3 = StudentNeedProfile(
    session_id="DEC-004",
    stated_goal="learn data",
    status=NEED_READY,
)
r3 = rec([cand("SE-DS-001", 0.80)], primary="SE-DS-001", clarification=True)
d3 = decide_recommendation(need3, r3)
check(d3.status == DECISION_CLARIFICATION, "Upstream clarification must be preserved")
check(d3.primary_course_id is None, "Clarification must remove primary selection")
check(d3.candidate_course_ids == ["SE-DS-001"], "Candidate lost")
check(d3.clarification_questions, "Clarification question missing")
check(validate_recommendation_decision(d3)["valid"], "Clarification decision invalid")
check(d3.no_invention is True, "Clarification no-invention failed")
check(d3.messaging_enabled is False, "Messaging must be disabled")
check(d3.crm_writes_enabled is False, "CRM writes must be disabled")

# 41–47: invalid upstream primary -> review
need4 = StudentNeedProfile(
    session_id="DEC-005",
    stated_goal="learn Python",
    status=NEED_READY,
)
r4 = rec([cand("SE-PY-001", 0.77)], primary="SE-DS-001")
d4 = decide_recommendation(need4, r4)
check(d4.status == DECISION_REVIEW, "Invalid primary should require review")
check(d4.primary_course_id is None, "Review must not retain invalid primary")
check(d4.candidate_course_ids == ["SE-PY-001"], "Review candidates lost")
check(d4.clarification_questions, "Review question missing")
check(validate_recommendation_decision(d4)["valid"], "Review decision invalid")
check("not present" in d4.rationale[0], "Review rationale missing")
check(d4.no_invention is True, "Review no-invention failed")

# 48–54: invalid need profile is controlled
bad_need = StudentNeedProfile(
    session_id="DEC-006",
    status="BAD_STATUS",
)
r5 = rec([cand("SE-DS-001", 0.7)])
d5 = decide_recommendation(bad_need, r5)
check(d5.status == DECISION_REVIEW, "Invalid need should review")
check(d5.primary_course_id is None, "Invalid need must not select")
check(d5.clarification_questions, "Invalid need needs review question")
check(d5.no_invention is True, "Invalid need no-invention failed")
check(d5.execution_enabled is False, "Invalid need execution must stay off")
check(validate_recommendation_decision(d5)["valid"], "Controlled invalid need invalid")
check(d5.candidate_course_ids == [], "Invalid need should not copy candidates")

# 55–60: serialization, defensive data, real Core 04 integration smoke
data = recommendation_decision_to_dict(d1)
check(data["status"] == DECISION_RECOMMEND, "Serialization status mismatch")
check(data["primary_course_id"] == "SE-DS-001", "Serialization primary mismatch")
check(data["candidate_course_ids"] == ["SE-DS-001"], "Serialization candidates mismatch")
check(data["scores"][0]["upstream_score"] == 0.91, "Serialization score mismatch")
data["candidate_course_ids"].append("MUTATION")
check("MUTATION" not in d1.candidate_course_ids, "Serialization mutated decision")

real_rec = recommend_courses(kb, "Data Science")
real_need = StudentNeedProfile(
    session_id="DEC-REAL",
    stated_goal="Data Science",
    course_ids=["SE-DS-001"],
    status=NEED_READY,
)
real_decision = run_recommendation_decision(real_need, real_rec)
check(real_decision.candidate_course_ids or
      real_decision.status == DECISION_UNKNOWN,
      "Real Core 04 integration returned no controlled result")

print(f"AI CORE 08: {passed}/{total} PASSED")
