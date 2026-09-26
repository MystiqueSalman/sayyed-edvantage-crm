import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH18 import (
    AnswerContext,
    build_answer_context,
    build_master_kb_with_answer_context,
    context_to_dict,
    get_context_text,
    validate_answer_context,
)

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_answer_context()

# 1–3: successful context construction
ctx = build_answer_context(kb, "Python programming", top_k=3)
check(isinstance(ctx, AnswerContext), "Expected AnswerContext")
check(ctx.matched is True, "Python query should match")
check(len(ctx.items) >= 1, "Expected at least one context item")

# 4–6: course isolation and provenance
check(ctx.items[0].course_id == "SE-PY-001",
      "Python programming should produce Python as top context")
check(ctx.items[0].provenance["course_id"] == "SE-PY-001",
      "Provenance course ID mismatch")
check(ctx.items[0].source_ids,
      "Context item must preserve source IDs")

# 7–9: aggregate metadata
check(ctx.course_ids == list(dict.fromkeys(i.course_id for i in ctx.items)),
      "course_ids aggregation is incorrect")
expected_sources = list(dict.fromkeys(
    sid for item in ctx.items for sid in item.source_ids
))
check(ctx.source_ids == expected_sources,
      "source_ids aggregation is incorrect")
check(ctx.policies["india_pricing"] is not None,
      "India pricing policy missing")

# 10–12: safe no-match
empty = build_answer_context(kb, "zzzz completely nonexistent topic", top_k=5)
check(empty.matched is False, "No-match must be explicit")
check(empty.items == [], "No-match must contain no evidence items")
check(empty.no_match_reason is not None, "No-match reason missing")

# 13–15: serialization/text evidence
serialized = context_to_dict(ctx)
check(serialized["matched"] is True, "Serialized matched flag incorrect")
check(serialized["items"][0]["course_id"] == "SE-PY-001",
      "Serialized course ID incorrect")
evidence = get_context_text(ctx)
check("Python Professional Program" in evidence,
      "Evidence text should preserve official course wording")

# 16–18: validation and safety invariants
report = validate_answer_context(ctx)
check(report["valid"] is True, f"Valid context failed: {report['errors']}")
check(ctx.safety["execution_enabled"] is False,
      "Execution must remain disabled")
check(ctx.safety["crm_writes_enabled"] is False,
      "CRM writes must remain disabled")

# 19–20: filter isolation / defensive behavior
linux_ctx = build_answer_context(
    kb, "Linux administration", top_k=5, course_id="SE-LINUX-001"
)
check(linux_ctx.matched is True and
      all(i.course_id == "SE-LINUX-001" for i in linux_ctx.items),
      "Course filter isolation failed")

wrong_ctx = build_answer_context(
    kb, "Linux administration", top_k=5, course_id="SE-PY-001"
)
check(wrong_ctx.matched is False,
      "Wrong course filter should safely produce no match")

print(f"MASTER KB BATCH 18: {passed}/{total} PASSED")
