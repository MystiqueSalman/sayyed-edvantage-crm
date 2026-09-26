import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH23 import (
    COMMERCIAL_SOURCE_ID,
    answer_commercial_aware_query,
    build_master_kb_with_commercial_answering,
    commercial_aware_answer_to_dict,
    validate_commercial_aware_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import build_response_plan
from Sayyed_EdVantage_Master_KB_BATCH23 import generate_commercial_aware_answer

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_commercial_answering()

# 1–5: Data Science Indian fee
ds = answer_commercial_aware_query(
    kb, "What is the fee for Data Science in India?"
)
check(ds.response_status == "READY", "DS fee answer should be READY")
check(ds.commercial_status == "VERIFIED_INDIA_FEE",
      "DS fee should be verified")
check(ds.fee == 50000, "DS fee incorrect")
check(ds.currency == "INR", "DS currency incorrect")
check(COMMERCIAL_SOURCE_ID in ds.source_ids,
      "Commercial source provenance missing")

# 6–10: other verified Indian fees
da = answer_commercial_aware_query(kb, "Data Analytics fee India")
check(da.fee == 40000, "Data Analytics fee incorrect")

ai = answer_commercial_aware_query(kb, "AI + Generative AI fee India")
check(ai.fee == 70000, "AI + Generative AI fee incorrect")

py = answer_commercial_aware_query(kb, "Python fee India")
check(py.fee == 35000, "Python fee incorrect")

combo = answer_commercial_aware_query(
    kb, "Data Science + Data Analytics Combo fee India"
)
check(combo.fee == 80000, "DS+DA combo fee incorrect")

# 11–14: international protection
intl = answer_commercial_aware_query(
    kb, "What is the fee for Data Science outside India?"
)
check(intl.commercial_status == "INTERNATIONAL_UNDEFINED",
      "International status incorrect")
check(intl.fee is None, "International fee must be undefined")
check(intl.human_handoff_required is True,
      "International query must require handoff")
check("Indian pricing must not be substituted" in intl.answer,
      "No-India-fallback rule missing")

# 15–17: region required and non-commercial routing
unknown_region = answer_commercial_aware_query(
    kb, "What is the fee for Python?"
)
check(unknown_region.commercial_status == "REGION_REQUIRED",
      "Unknown region should require region")
check(unknown_region.fee is None,
      "Unknown region must not quote fee")

general = answer_commercial_aware_query(
    kb, "What is Python programming?"
)
check(general.commercial_status is None,
      "General query should not be treated as commercial")

# 18–20: native plan integration and serialization
plan = build_response_plan(kb, "What is the fee for DevOps in India?")
devops = generate_commercial_aware_answer(kb, plan)
check(devops.fee == 45000, "DevOps fee incorrect")
check(devops.grounded is True, "Commercial answer must be grounded")
serialized = commercial_aware_answer_to_dict(devops)
check(serialized["fee"] == 45000 and
      serialized["currency"] == "INR",
      "Commercial answer serialization failed")

# 21–24: remaining verified offerings
linux = answer_commercial_aware_query(kb, "Linux fee India")
check(linux.fee == 25000, "Linux fee incorrect")

devops_combo = answer_commercial_aware_query(
    kb, "Linux + DevOps Combo fee India"
)
check(devops_combo.fee == 60000, "Linux+DevOps combo fee incorrect")

ehc = answer_commercial_aware_query(
    kb, "Ethical Hacking & Cybersecurity fee India"
)
check(ehc.fee == 60000, "Ethical Hacking fee incorrect")

# 25–27: safety
check(validate_commercial_aware_answer(ds)["valid"] is True,
      "DS commercial answer validation failed")
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(ds.safety[key] is False, f"{key} must remain False")

print(f"MASTER KB BATCH 23: {passed}/{total} PASSED")
