import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH22 import (
    COMMERCIAL_SOURCE_ID,
    INDIA_OFFERINGS,
    build_master_kb_with_commercial_knowledge,
    commercial_layer_snapshot,
    get_commercial_answer,
    validate_commercial_answer,
)

passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_with_commercial_knowledge()
layer = kb.commercial_layer

# 1–4: commercial layer structure
check(len(layer.india_offerings) == 9, "Expected 9 Indian commercial offerings")
check(layer.source_id == COMMERCIAL_SOURCE_ID,
      "Commercial source ID mismatch")
check(layer.international_defined is False,
      "International pricing must remain undefined")
check(layer.validate()["valid"] is True,
      "Commercial layer validation failed")

# 5–8: key Indian fees
ds = get_commercial_answer(kb, "What is the fee for Data Science in India?")
check(ds["status"] == "VERIFIED_INDIA_FEE", "Data Science fee status failed")
check(ds["fee"] == 50000, "Data Science Indian fee incorrect")
check(ds["currency"] == "INR", "Data Science currency incorrect")
check(ds["source_id"] == COMMERCIAL_SOURCE_ID,
      "Data Science provenance missing")

# 9–12: other verified Indian offerings
da = get_commercial_answer(kb, "Data Analytics fee India")
check(da["fee"] == 40000, "Data Analytics fee incorrect")

combo = get_commercial_answer(
    kb, "Data Science + Data Analytics Combo fee in India"
)
check(combo["fee"] == 80000, "DS+DA combo fee incorrect")

devops = get_commercial_answer(kb, "DevOps fee India")
check(devops["fee"] == 45000, "DevOps fee incorrect")

# 13–15: remaining offering coverage
ai = get_commercial_answer(kb, "AI + Generative AI fee in India")
check(ai["fee"] == 70000, "AI + Generative AI fee incorrect")

linux_combo = get_commercial_answer(
    kb, "Linux + DevOps Combo fee in India"
)
check(linux_combo["fee"] == 60000, "Linux + DevOps combo fee incorrect")

ehc = get_commercial_answer(
    kb, "Ethical Hacking & Cybersecurity fee in India"
)
check(ehc["fee"] == 60000, "Ethical Hacking fee incorrect")

# 16–18: international protection
intl = get_commercial_answer(
    kb, "What is the fee for Data Science outside India?"
)
check(intl["status"] == "INTERNATIONAL_UNDEFINED",
      "International fee status failed")
check(intl["fee"] is None, "International fee must be undefined")
check("Indian pricing must not be substituted" in intl["message"],
      "International no-India-fallback missing")

# 19–21: region required and missing offering
unknown_region = get_commercial_answer(kb, "What is the fee for Python?")
check(unknown_region["status"] == "REGION_REQUIRED",
      "Unknown region should require region")
check(unknown_region["fee"] is None,
      "Unknown region must not quote fee")

missing = get_commercial_answer(kb, "What is the fee for a nonexistent course in India?")
check(missing["status"] == "OFFERING_NOT_FOUND",
      "Unknown offering status failed")

# 22–24: tax and source safety
check("+ GST" in ds["message"], "GST/tax note missing")
check(validate_commercial_answer(ds)["valid"] is True,
      "Indian commercial response validation failed")
check(validate_commercial_answer(intl)["valid"] is True,
      "International commercial response validation failed")

# 25–27: snapshot and native offering integration
snapshot = commercial_layer_snapshot(kb)
check(len(snapshot["offerings"]) == 9, "Commercial snapshot count incorrect")
check(kb.get_fee("SE-OFFER-DS-INDIA", "india") == 50000,
      "Native Master KB offering lookup failed")
check(kb.get_fee("SE-OFFER-DS-INDIA", "international") is None,
      "Native international fee must remain undefined")

# 28–30: all expected offering names and no action capability
names = {x["name"] for x in layer.list_offerings()}
check(names == {x["name"] for x in INDIA_OFFERINGS.values()},
      "Offering names do not match verified schedule")
check(kb.get_common_knowledge("international_pricing_defined") is False,
      "International pricing policy flag incorrect")

for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(kb.get_common_knowledge(key) is False,
          f"{key} must remain False")

print(f"MASTER KB BATCH 22: {passed}/{total} PASSED")
