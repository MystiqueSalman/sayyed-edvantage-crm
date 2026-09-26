import os, sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_AI_CORE10 import (
    READINESS_READY, READINESS_INSUFFICIENT,
    READINESS_CLARIFICATION, READINESS_REVIEW,
    ReadinessEvidence, AdmissionReadiness,
    assess_admission_readiness, build_admission_readiness,
    admission_readiness_to_dict, validate_admission_readiness,
    run_admission_readiness,
)
from Sayyed_EdVantage_AI_CORE07 import StudentNeedProfile, NEED_READY
from Sayyed_EdVantage_AI_CORE08 import (
    DECISION_RECOMMEND, DECISION_CLARIFICATION,
    DECISION_UNKNOWN, DECISION_REVIEW,
)
from Sayyed_EdVantage_AI_CORE09 import (
    COUNSELLING_RECOMMENDATION, COUNSELLING_CLARIFICATION,
    COUNSELLING_DISCOVERY, COUNSELLING_REVIEW,
)

passed = total = 0
def check(c, label):
    global passed, total
    total += 1
    if not c: raise AssertionError(label)
    passed += 1

def decision(status, primary=None, candidates=None):
    return SimpleNamespace(
        session_id="DEC", status=status, primary_course_id=primary,
        candidate_course_ids=list(candidates or ([] if primary is None else [primary])),
        scores=[], rationale=[], clarification_questions=[], source_ids=[],
        no_invention=True, execution_enabled=False, messaging_enabled=False,
        external_actions_enabled=False, crm_writes_enabled=False,
    )

def counselling(stage, primary=None, candidates=None, handoff=False, reason=None):
    return SimpleNamespace(
        session_id="COUN", stage=stage, primary_course_id=primary,
        candidate_course_ids=list(candidates or ([] if primary is None else [primary])),
        confirmed_need_fields=[], unknown_need_fields=[], questions=[],
        recommendation_rationale=[], next_steps=["Next step"],
        handoff_required=handoff, handoff_reason=reason,
        no_invention=True, execution_enabled=False, messaging_enabled=False,
        external_actions_enabled=False, crm_writes_enabled=False,
    )

# 1–10: no recommendation -> insufficient
n0 = StudentNeedProfile(session_id="ADM-001", status="NEED_UNKNOWN")
r0 = assess_admission_readiness(n0, decision(DECISION_UNKNOWN),
                                counselling(COUNSELLING_DISCOVERY))
check(r0.session_id == "ADM-001", "Session mismatch")
check(r0.status == READINESS_INSUFFICIENT, "Unknown should be insufficient")
check(r0.course_id is None, "Unknown must not select course")
check(r0.blockers, "Unknown blockers missing")
check(r0.next_steps, "Unknown next steps missing")
check(r0.application_confirmed is False, "Application cannot be confirmed")
check(r0.payment_confirmed is False, "Payment cannot be confirmed")
check(r0.no_invention is True, "No-invention failed")
check(r0.crm_writes_enabled is False, "CRM writes disabled failed")
check(validate_admission_readiness(r0)["valid"], "Unknown readiness invalid")

# 11–20: ambiguous recommendation -> clarification
n1 = StudentNeedProfile(session_id="ADM-002", status="NEED_CLARIFICATION")
r1 = assess_admission_readiness(
    n1,
    decision(DECISION_CLARIFICATION, candidates=["SE-DS-001", "SE-DA-001"]),
    counselling(COUNSELLING_CLARIFICATION, candidates=["SE-DS-001", "SE-DA-001"]),
)
check(r1.status == READINESS_CLARIFICATION, "Ambiguous recommendation should clarify")
check(r1.course_id is None, "Clarification must not select course")
check("Course selection" in r1.blockers[0], "Course blocker missing")
check(r1.next_steps, "Clarification next steps missing")
check(validate_admission_readiness(r1)["valid"], "Clarification readiness invalid")
check(r1.admission_confirmed is False, "Admission cannot be confirmed")
check(r1.enrollment_confirmed is False, "Enrollment cannot be confirmed")
check(r1.execution_enabled is False, "Execution disabled failed")
check(r1.messaging_enabled is False, "Messaging disabled failed")
check(r1.external_actions_enabled is False, "External actions disabled failed")

# 21–32: supported recommendation is NOT admission
n2 = StudentNeedProfile(
    session_id="ADM-003",
    stated_goal="become a Data Scientist",
    experience_level="fresher",
    education="B.Tech",
    region="India",
    course_ids=["SE-DS-001"],
    status=NEED_READY,
)
r2 = assess_admission_readiness(
    n2,
    decision(DECISION_RECOMMEND, primary="SE-DS-001", candidates=["SE-DS-001"]),
    counselling(COUNSELLING_RECOMMENDATION, primary="SE-DS-001", candidates=["SE-DS-001"]),
)
check(r2.status == READINESS_INSUFFICIENT, "Recommendation alone must not mean admission ready")
check(r2.course_id == "SE-DS-001", "Recommended course missing")
check(r2.blockers, "Admission blockers missing")
check(any("Application" in b for b in r2.blockers), "Application blocker missing")
check(any("Payment" in b for b in r2.blockers), "Payment blocker missing")
check(any("Admission" in b for b in r2.blockers), "Admission blocker missing")
check(any("Enrollment" in b for b in r2.blockers), "Enrollment blocker missing")
check(r2.application_confirmed is False, "Application falsely confirmed")
check(r2.payment_confirmed is False, "Payment falsely confirmed")
check(r2.admission_confirmed is False, "Admission falsely confirmed")
check(r2.enrollment_confirmed is False, "Enrollment falsely confirmed")
check(validate_admission_readiness(r2)["valid"], "Recommendation readiness invalid")

# 33–40: review -> human handoff
n3 = StudentNeedProfile(session_id="ADM-004", status=NEED_READY)
r3 = assess_admission_readiness(
    n3,
    decision(DECISION_REVIEW, candidates=["SE-PY-001"]),
    counselling(COUNSELLING_REVIEW, candidates=["SE-PY-001"], handoff=True,
                reason="Recommendation review required."),
)
check(r3.status == READINESS_REVIEW, "Review should remain review")
check(r3.human_handoff_required is True, "Review must require handoff")
check(r3.handoff_reason, "Handoff reason missing")
check(r3.next_steps, "Review next steps missing")
check(r3.primary_course_id is None if hasattr(r3, "primary_course_id") else True,
      "No unsupported primary field")
check(validate_admission_readiness(r3)["valid"], "Review readiness invalid")
check(r3.no_invention is True, "Review no-invention failed")
check(r3.crm_writes_enabled is False, "Review CRM writes disabled")
check(r3.application_confirmed is False, "Review application confirmation must remain false")

# 41–48: evidence/missing fields
n4 = StudentNeedProfile(
    session_id="ADM-005",
    stated_goal="learn Python",
    region="India",
    status=NEED_READY,
)
r4 = assess_admission_readiness(
    n4,
    decision(DECISION_RECOMMEND, primary="SE-PY-001", candidates=["SE-PY-001"]),
    counselling(COUNSELLING_RECOMMENDATION, primary="SE-PY-001", candidates=["SE-PY-001"]),
)
check("learning_goal" in [e.field for e in r4.evidence], "Goal evidence missing")
check("experience" in r4.missing_fields, "Missing experience not tracked")
check("budget" in r4.missing_fields, "Missing budget not tracked")
check(r4.course_id == "SE-PY-001", "Python course missing")
check(r4.next_steps, "Partial readiness next steps missing")
check(r4.no_invention is True, "Partial no-invention failed")
check(validate_admission_readiness(r4)["valid"], "Partial readiness invalid")
check(r4.human_handoff_required is False, "Partial profile should not force handoff")

# 49–54: validation safety
bad = AdmissionReadiness(session_id="ADM-BAD", status=READINESS_READY)
bad.course_id = "SE-DS-001"
bad.blockers = []
check(validate_admission_readiness(bad)["valid"], "Minimal ready shape should validate")
bad.execution_enabled = True
check(not validate_admission_readiness(bad)["valid"], "Unsafe execution must fail")
bad.execution_enabled = False
bad.application_confirmed = True
check(not validate_admission_readiness(bad)["valid"], "Application confirmation must not be asserted")
bad.application_confirmed = False
bad.no_invention = False
check(not validate_admission_readiness(bad)["valid"], "No-invention violation must fail")
bad.no_invention = True
bad.human_handoff_required = True
check(not validate_admission_readiness(bad)["valid"], "Handoff without reason must fail")

# 55–60: serialization/defensive copy
data = admission_readiness_to_dict(r2)
check(data["session_id"] == "ADM-003", "Serialization session mismatch")
check(data["status"] == READINESS_INSUFFICIENT, "Serialization status mismatch")
check(data["course_id"] == "SE-DS-001", "Serialization course mismatch")
check(data["application_confirmed"] is False, "Serialization application safety missing")
check(data["no_invention"] is True, "Serialization no-invention missing")
data["missing_fields"].append("MUTATION")
check("MUTATION" not in r2.missing_fields, "Serialization mutated original")

print(f"AI CORE 10: {passed}/{total} PASSED")
