import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH25 import (
    assess_completeness,
    build_controlled_answer,
    build_master_kb_with_completeness_control,
    controlled_answer_query,
    controlled_answer_to_dict,
    validate_completeness_report,
    validate_controlled_answer,
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


kb = build_master_kb_with_completeness_control()

# 1–4: complete/general query
plan = build_response_plan(kb, "Python programming", top_k=5)
report = assess_completeness(kb, plan)
check(report.status == "COMPLETE", "Python information should be complete")
check(report.supported_points, "Supported points missing")
check(validate_completeness_report(report)["valid"] is True,
      "Completeness report validation failed")
answer = build_controlled_answer(kb, plan)
check(answer.response_status == "READY", "Python answer should be READY")

# 5–8: commercial India
ds = controlled_answer_query(
    kb, "What is the fee for Data Science in India?"
)
check(ds.completeness_status == "COMPLETE",
      "Verified Indian fee should be complete")
check(ds.grounded is True, "Indian fee answer must be grounded")
check(ds.fee if hasattr(ds, "fee") else True,
      "Compatibility check")
check("₹50,000 + GST" in ds.answer,
      "Verified Indian fee missing from controlled answer")

# 9–12: international
intl = controlled_answer_query(
    kb, "What is the fee for Data Science outside India?"
)
check(intl.completeness_status == "PARTIAL",
      "International fee should be partial")
check(intl.human_handoff_required is True,
      "International fee must require handoff")
check(intl.missing_points,
      "International missing point should be recorded")
check("Indian pricing must not be substituted" in intl.answer,
      "International protection missing")

# 13–15: unknown region
unknown = controlled_answer_query(
    kb, "What is the fee for Python?"
)
check(unknown.completeness_status == "PARTIAL",
      "Unknown region should be partial")
check(unknown.human_handoff_required is True,
      "Unknown region should require handoff")
check("pricing region" in unknown.answer.lower(),
      "Region requirement missing")

# 16–18: certification
cert = controlled_answer_query(
    kb, "Does Data Science provide certification?"
)
check(cert.completeness_status == "PARTIAL",
      "Certification should be partial/undefined")
check(cert.missing_points,
      "Certification missing point not recorded")
check("Certification details" in cert.answer,
      "Certification safety wording missing")

# 19–21: documented Linux inconsistency
linux = controlled_answer_query(
    kb, "Linux administration duration"
)
check(linux.warnings,
      "Linux source warning should be preserved")
check("40" in linux.answer and "44" in linux.answer,
      "Linux duration figures should remain visible")
check("documented duration inconsistency" in linux.answer.lower(),
      "Linux inconsistency note missing")

# 22–24: no-match
none = controlled_answer_query(
    kb, "zzzz completely nonexistent topic"
)
check(none.response_status == "NO_MATCH",
      "No-match status failed")
check(none.completeness_status == "INCOMPLETE",
      "No-match completeness failed")
check(none.human_handoff_required is True,
      "No-match must require handoff")

# 25–27: serialization/validation
serialized = controlled_answer_to_dict(ds)
check(serialized["completeness_status"] == ds.completeness_status,
      "Serialization completeness mismatch")
check(validate_controlled_answer(ds)["valid"] is True,
      "Controlled answer validation failed")

# 28–31: hard safety
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(ds.safety[key] is False, f"{key} must remain False")

print(f"MASTER KB BATCH 25: {passed}/{total} PASSED")
