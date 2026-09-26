import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH20 import (
    answer_query,
    build_master_kb_with_answer_generator,
    generate_grounded_answer,
    grounded_answer_to_dict,
    validate_grounded_answer,
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


kb = build_master_kb_with_answer_generator()

# 1–4: basic grounded answer
ans = answer_query(kb, "Python programming", top_k=3)
check(ans.response_status == "READY", "Python answer should be READY")
check(ans.grounded is True, "Python answer must be grounded")
check(ans.course_ids and ans.course_ids[0] == "SE-PY-001",
      "Python course ID missing or incorrect")
check(ans.source_ids, "Python answer must preserve source IDs")

# 5–7: evidence terminology
check("Python Professional Program" in ans.answer,
      "Official Python terminology missing")
check("invent" not in ans.answer.lower(),
      "Normal grounded answer should not contain unnecessary invention warning")
check(validate_grounded_answer(ans)["valid"] is True,
      "Grounded answer validation failed")

# 8–10: no-match behavior
empty = answer_query(kb, "zzzz completely nonexistent topic", top_k=5)
check(empty.response_status == "NO_MATCH", "No-match status failed")
check(empty.grounded is False, "No-match cannot be grounded")
check(empty.human_handoff_required is True, "No-match must require safe handoff")

# 11–13: commercial safety without unsupported fee
fee = answer_query(kb, "What is the fee for Data Science in India?", top_k=5)
check(fee.response_status == "READY", "Commercial query should still be answerable")
check("should not invent" in fee.answer.lower(),
      "Missing verified fee must trigger no-invention wording")
check("execution_enabled" not in fee.answer,
      "Internal safety fields must not leak into answer")

# 14–16: international pricing
intl = answer_query(
    kb, "What is the fee for Data Science outside India?", top_k=5
)
check(intl.human_handoff_required is True,
      "International fee query should require handoff")
check("Indian pricing should not be substituted" in intl.answer,
      "International no-India-fallback rule missing")
check("Admissions/team" in intl.answer,
      "International commercial handoff missing")

# 17–18: career safety
career = answer_query(kb, "What jobs can I get after Data Science?", top_k=5)
check("guaranteed employment" in career.answer.lower(),
      "Career safety wording missing")
check("salary" in career.answer.lower(),
      "Career safety should cover salary")

# 19–20: duration inconsistency preservation
linux = answer_query(kb, "Linux administration duration", top_k=5)
check(linux.response_status == "READY", "Linux duration should match")
check("documented duration inconsistency" in linux.answer.lower(),
      "Linux duration inconsistency must be disclosed")

# 21–22: course isolation and serialization
isolated = answer_query(
    kb, "Linux administration", top_k=5, course_id="SE-LINUX-001"
)
check(isolated.course_ids == ["SE-LINUX-001"],
      "Course isolation failed in answer generator")

serialized = grounded_answer_to_dict(ans)
check(serialized["grounded"] is True and
      serialized["course_ids"] == ans.course_ids,
      "Answer serialization failed")

# 23–25: hard safety invariants
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(ans.safety[key] is False, f"{key} must remain False")

# 26–27: response-plan integration
plan = build_response_plan(kb, "machine learning", top_k=3)
ml = generate_grounded_answer(plan)
check(ml.course_ids[0] == "SE-DS-001",
      "Machine learning answer must remain Data Science")
check(ml.source_ids,
      "Generated answer must preserve provenance source IDs")

print(f"MASTER KB BATCH 20: {passed}/{total} PASSED")
