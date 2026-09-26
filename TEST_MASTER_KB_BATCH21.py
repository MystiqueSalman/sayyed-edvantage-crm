import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH21 import (
    answer_multi_course_query,
    build_master_kb_with_multi_course_answers,
    compose_multi_course_answer,
    group_response_plan_by_course,
    multi_course_answer_to_dict,
    select_primary_course,
    validate_course_groups,
    validate_multi_course_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import build_response_plan

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_multi_course_answers()

# 1–4: single-course grouping
plan = build_response_plan(kb, "Python programming", top_k=5)
groups = group_response_plan_by_course(plan)
check(len(groups) >= 1, "Python should produce at least one evidence group")
check(groups[0].course_id == "SE-PY-001",
      "Python must be the strongest course group")
check(all(g.course_id for g in groups), "Every group needs a course ID")
check(validate_course_groups(groups)["valid"] is True,
      "Course groups failed validation")

# 5–7: primary-course selection
primary = select_primary_course(groups)
check(primary == "SE-PY-001", "Primary course selection failed")
check(select_primary_course([]) is None,
      "Empty groups should have no primary course")
check(select_primary_course(groups) in [g.course_id for g in groups],
      "Primary course must belong to evidence groups")

# 8–11: answer composition
answer = compose_multi_course_answer(plan)
check(answer.response_status == "READY", "Python answer should be READY")
check(answer.grounded is True, "Python answer must be grounded")
check(answer.primary_course_id == "SE-PY-001",
      "Primary Python course ID missing")
check("Python Professional Program" in answer.answer,
      "Official Python terminology missing")

# 12–14: provenance/isolation
check(answer.course_ids == [g.course_id for g in answer.evidence_groups],
      "Course IDs do not match groups")
check(answer.source_ids, "Source IDs must be preserved")
check(all(
    item["provenance"]["course_id"] == group.course_id
    for group in answer.evidence_groups
    for item in group.evidence
), "Evidence provenance was not preserved")

# 15–17: no-match behavior
no_match = answer_multi_course_query(
    kb, "zzzz completely nonexistent topic", top_k=10
)
check(no_match.response_status == "NO_MATCH", "No-match status failed")
check(no_match.grounded is False, "No-match cannot be grounded")
check(no_match.evidence_groups == [], "No-match cannot contain groups")

# 18–20: explicit course isolation
linux = answer_multi_course_query(
    kb, "Linux administration", top_k=10, course_id="SE-LINUX-001"
)
check(linux.course_ids == ["SE-LINUX-001"],
      "Linux isolation failed")
check(all(
    g.course_id == "SE-LINUX-001" for g in linux.evidence_groups
), "Linux evidence leaked across courses")
wrong = answer_multi_course_query(
    kb, "Linux administration", top_k=10, course_id="SE-PY-001"
)
check(wrong.response_status == "NO_MATCH",
      "Wrong course filter should safely no-match")

# 21–23: multi-course query remains separated
multi = answer_multi_course_query(
    kb, "Python Linux programming", top_k=10
)
check(multi.response_status == "READY",
      "Mixed course query should remain answerable")
check(len(multi.evidence_groups) >= 2,
      "Mixed Python/Linux query should retain separate course groups")
check("Python" in multi.answer and "Linux" in multi.answer,
      "Mixed answer should retain both official course references")

# 24–25: serialization and validation
serialized = multi_course_answer_to_dict(answer)
check(serialized["primary_course_id"] == "SE-PY-001",
      "Serialization lost primary course")
check(validate_multi_course_answer(answer)["valid"] is True,
      "Multi-course answer validation failed")

# 26–29: hard safety invariants
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(answer.safety[key] is False, f"{key} must remain False")

print(f"MASTER KB BATCH 21: {passed}/{total} PASSED")
