import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH19 import (
    build_master_kb_with_response_policy,
    build_response_plan,
    classify_intent,
    compose_response_plan,
    response_plan_to_dict,
    validate_response_plan,
)
from Sayyed_EdVantage_Master_KB_BATCH18 import build_answer_context

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1

kb = build_master_kb_with_response_policy()

# 1–4: intent classification
check(classify_intent("What is the fee?") == "commercial",
      "Fee intent classification failed")
check(classify_intent("What are the prerequisites?") == "eligibility",
      "Eligibility intent classification failed")
check(classify_intent("How long is the course?") == "program_information",
      "Program-information intent classification failed")
check(classify_intent("Do you provide certification?") == "certification",
      "Certification intent classification failed")

# 5–8: grounded ready plan
plan = build_response_plan(kb, "Python programming", top_k=3)
check(plan.response_status == "READY", "Python plan should be READY")
check(plan.intent == "general_information", "General intent classification failed")
check(plan.evidence, "READY plan must contain evidence")
check(plan.course_ids[0] == "SE-PY-001",
      "Python should remain the top isolated course")

# 9–11: provenance and policies
check(plan.evidence[0].provenance["course_id"] == "SE-PY-001",
      "Evidence provenance mismatch")
check("Do not invent missing facts" in " ".join(plan.instructions),
      "No-invention instruction missing")
check(plan.safety_policy["execution_enabled"] is False,
      "Execution must remain disabled")

# 12–14: commercial policy
fee_plan = build_response_plan(kb, "What is the fee for Data Science in India?", top_k=5)
check(fee_plan.intent == "commercial", "Commercial intent failed")
check(any("Indian pricing" in x for x in fee_plan.instructions),
      "Indian pricing policy instruction missing")

intl_plan = build_response_plan(kb, "What is the fee for Data Science outside India?", top_k=5)
check(intl_plan.human_handoff_required is True,
      "International commercial query should require handoff")
check(any("Do not quote Indian pricing" in x for x in intl_plan.instructions),
      "International no-India-fallback instruction missing")

# 15–16: no-match safety
no_match = build_response_plan(kb, "zzzz completely nonexistent topic", top_k=5)
check(no_match.response_status == "NO_MATCH", "No-match status failed")
check(no_match.human_handoff_required is True,
      "No-match should require a safe handoff")

# 17–18: plan validation and serialization
valid = validate_response_plan(plan)
check(valid["valid"] is True, f"Response plan validation failed: {valid['errors']}")
serialized = response_plan_to_dict(plan)
check(serialized["response_status"] == "READY",
      "Serialized response status incorrect")

# 19–20: course isolation and safety
linux_plan = build_response_plan(
    kb, "Linux administration", top_k=5, course_id="SE-LINUX-001"
)
check(linux_plan.course_ids == ["SE-LINUX-001"],
      "Linux course isolation failed")

check(all(
    linux_plan.safety_policy[k] is False
    for k in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    )
), "One or more action safety flags are enabled")

# 21–22: context-to-plan consistency
ctx = build_answer_context(kb, "machine learning", top_k=3)
ml_plan = compose_response_plan(ctx)
check(ml_plan.course_ids[0] == "SE-DS-001",
      "Machine learning should remain Data Science")
check(ml_plan.source_ids,
      "Response plan must preserve source IDs")

print(f"MASTER KB BATCH 19: {passed}/{total} PASSED")
