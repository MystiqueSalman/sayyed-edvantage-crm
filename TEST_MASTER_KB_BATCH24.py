import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH24 import (
    COMMERCIAL_SOURCE_ID,
    answer_query_orchestrated,
    build_master_kb_with_orchestrator,
    orchestrated_answer_to_dict,
    orchestrate_response,
    validate_orchestrated_answer,
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


kb = build_master_kb_with_orchestrator()

# 1–5: Indian commercial orchestration
ds = answer_query_orchestrated(
    kb, "What is the fee for Data Science in India?"
)
check(ds.response_status == "READY", "DS orchestration should be READY")
check(ds.commercial_status == "VERIFIED_INDIA_FEE",
      "DS commercial status incorrect")
check(ds.fee == 50000, "DS fee incorrect")
check(ds.currency == "INR", "DS currency incorrect")
check(COMMERCIAL_SOURCE_ID in ds.source_ids,
      "Commercial provenance missing")

# 6–8: course evidence + commercial evidence remain distinct
check(ds.evidence_groups, "Course evidence groups missing")
check(ds.evidence_groups[0].course_id == "SE-DS-001",
      "DS course evidence should remain isolated")
check("₹50,000 + GST" in ds.answer,
      "Verified Indian fee not included in answer")

# 9–11: international safety
intl = answer_query_orchestrated(
    kb, "What is the fee for Data Science outside India?"
)
check(intl.commercial_status == "INTERNATIONAL_UNDEFINED",
      "International commercial status incorrect")
check(intl.fee is None, "International fee must remain undefined")
check(intl.human_handoff_required is True,
      "International answer must require handoff")

# 12–14: unknown region
unknown = answer_query_orchestrated(
    kb, "What is the fee for Python?"
)
check(unknown.commercial_status == "REGION_REQUIRED",
      "Unknown region status incorrect")
check(unknown.fee is None, "Unknown region must not quote fee")
check("pricing region" in unknown.answer.lower(),
      "Region confirmation wording missing")

# 15–17: combo offerings
combo = answer_query_orchestrated(
    kb, "Data Science + Data Analytics Combo fee India"
)
check(combo.commercial_status == "VERIFIED_INDIA_FEE",
      "Combo commercial status incorrect")
check(combo.fee == 80000, "Combo fee incorrect")
check("Data Science + Data Analytics Combo" in combo.answer,
      "Combo name missing")

# 18–20: non-commercial and mixed-course behavior
general = answer_query_orchestrated(
    kb, "What is Python programming?"
)
check(general.commercial_status is None,
      "General query must not invoke commercial pricing")
check(general.course_ids[0] == "SE-PY-001",
      "Python must remain primary course")

mixed = answer_query_orchestrated(
    kb, "Python Linux programming", top_k=10
)
check(len(mixed.evidence_groups) >= 2,
      "Mixed course query should preserve multiple groups")

# 21–23: direct plan integration
plan = build_response_plan(
    kb, "What is the fee for DevOps in India?"
)
devops = orchestrate_response(kb, plan)
check(devops.fee == 45000, "DevOps fee incorrect")
check(devops.grounded is True, "DevOps answer must be grounded")
check(devops.primary_course_id == "SE-DEVOPS-001",
      "DevOps primary course incorrect")

# 24–25: serialization and validation
serialized = orchestrated_answer_to_dict(ds)
check(serialized["fee"] == 50000 and
      serialized["currency"] == "INR",
      "Serialization failed")
check(validate_orchestrated_answer(ds)["valid"] is True,
      "DS orchestration validation failed")

# 26–30: safety invariants
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(ds.safety[key] is False, f"{key} must remain False")

print(f"MASTER KB BATCH 24: {passed}/{total} PASSED")
