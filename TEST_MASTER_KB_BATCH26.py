import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH26 import (
    FINALIZED,
    BLOCKED,
    FinalizedAnswer,
    finalize_controlled_answer,
    finalize_query,
    finalized_answer_to_dict,
    validate_finalized_answer,
    build_master_kb_with_finalization_gate,
)
from Sayyed_EdVantage_Master_KB_BATCH25 import (
    controlled_answer_query,
)

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_finalization_gate()

# 1–5: verified Indian commercial answer finalizes
ds = finalize_query(kb, "What is the fee for Data Science in India?")
check(ds.finalization_status == FINALIZED, "Indian fee should finalize")
check(ds.response_status == "READY", "Indian fee should be READY")
check(ds.grounded is True, "Finalized Indian fee must be grounded")
check(ds.source_ids, "Finalized answer must retain provenance")
check("₹50,000 + GST" in ds.answer, "Indian fee missing")

# 6–9: international answer remains finalized but partial + handoff
intl = finalize_query(kb, "What is the fee for Data Science outside India?")
check(intl.finalization_status == FINALIZED,
      "Safe partial international answer should finalize")
check(intl.completeness_status == "PARTIAL",
      "International answer should remain PARTIAL")
check(intl.human_handoff_required is True,
      "International answer must retain handoff")
check("Indian pricing must not be substituted" in intl.answer,
      "International protection missing")

# 10–12: certification remains partial + controlled
cert = finalize_query(kb, "Does Data Science provide certification?")
check(cert.finalization_status == FINALIZED,
      "Safe certification-unknown answer should finalize")
check(cert.completeness_status == "PARTIAL",
      "Certification must remain PARTIAL")
check("Certification details" in cert.answer,
      "Certification wording missing")

# 13–15: documented Linux inconsistency preserved
linux = finalize_query(kb, "Linux administration duration")
check(linux.finalization_status == FINALIZED,
      "Linux duration answer should finalize")
check("40" in linux.answer and "44" in linux.answer,
      "Linux source figures must be preserved")
check("documented duration inconsistency" in linux.answer.lower(),
      "Linux inconsistency warning missing")

# 16–18: no-match is blocked from normal finalization
none = finalize_query(kb, "zzzz completely nonexistent topic")
check(none.finalization_status == BLOCKED,
      "NO_MATCH must be blocked by finalization gate")
check(none.gate_errors,
      "Blocked NO_MATCH must expose gate errors")
check(none.human_handoff_required is True,
      "Blocked NO_MATCH must require handoff")

# 19–22: validation + serialization
check(validate_finalized_answer(ds)["valid"] is True,
      "Finalized answer validation failed")
serialized = finalized_answer_to_dict(ds)
check(serialized["finalization_status"] == FINALIZED,
      "Serialization finalization mismatch")
check(serialized["source_ids"] == ds.source_ids,
      "Serialization provenance mismatch")
check(serialized["safety"]["no_invention"] is True,
      "Serialization safety mismatch")

# 23–26: deliberately unsafe answer is blocked
unsafe = controlled_answer_query(kb, "Python programming")
unsafe.safety["execution_enabled"] = True
blocked = finalize_controlled_answer(unsafe)
check(blocked.finalization_status == BLOCKED,
      "Unsafe execution flag must block finalization")
check(blocked.answer == "",
      "Blocked answer must not expose final answer text")
check(blocked.gate_errors,
      "Unsafe answer must expose gate errors")
check(blocked.human_handoff_required is True,
      "Blocked unsafe answer must require handoff")

# 27–30: other safety flags are independently enforced
for key in (
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    unsafe2 = controlled_answer_query(kb, "Python programming")
    unsafe2.safety[key] = True
    blocked2 = finalize_controlled_answer(unsafe2)
    check(blocked2.finalization_status == BLOCKED,
          f"{key} must block finalization")

# 31–33: no-invention and provenance gates
unsafe3 = controlled_answer_query(kb, "Python programming")
unsafe3.safety["no_invention"] = False
blocked3 = finalize_controlled_answer(unsafe3)
check(blocked3.finalization_status == BLOCKED,
      "no_invention=False must block finalization")
check(any("no_invention" in e for e in blocked3.gate_errors),
      "no_invention gate error missing")

unsafe4 = controlled_answer_query(kb, "Python programming")
unsafe4.source_ids = []
blocked4 = finalize_controlled_answer(unsafe4)
check(blocked4.finalization_status == BLOCKED,
      "Missing provenance must block finalization")

# 34–36: invalid READY/INCOMPLETE state is blocked
invalid = controlled_answer_query(kb, "Python programming")
invalid.grounded = False
blocked5 = finalize_controlled_answer(invalid)
check(blocked5.finalization_status == BLOCKED,
      "Ungrounded READY answer must block")
check(blocked5.answer == "",
      "Blocked invalid answer must hide answer text")

invalid2 = controlled_answer_query(kb, "Python programming")
invalid2.completeness_status = "INCOMPLETE"
invalid2.human_handoff_required = False
blocked6 = finalize_controlled_answer(invalid2)
check(blocked6.finalization_status == BLOCKED,
      "INCOMPLETE without handoff must block")

# 37–40: defensive-copy / invariant checks
check(ds.gate_errors == [], "Finalized answer should have no gate errors")
check(ds.safety["execution_enabled"] is False,
      "Execution invariant failed")
check(ds.safety["messaging_enabled"] is False,
      "Messaging invariant failed")
check(ds.safety["external_actions_enabled"] is False,
      "External action invariant failed")

print(f"MASTER KB BATCH 26: {passed}/{total} PASSED")
