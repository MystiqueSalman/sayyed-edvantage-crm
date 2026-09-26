import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH29 import (
    run_end_to_end_verification,
    verify_serialization_integrity,
    validate_end_to_end_report,
    build_master_kb_for_end_to_end_verification,
)


passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_for_end_to_end_verification()

# 1–4: complete end-to-end scenario suite
report = run_end_to_end_verification(kb)
check(report["total"] == 8, "Expected 8 end-to-end scenarios")
check(report["passed"] == 8, "All end-to-end scenarios must pass")
check(report["all_passed"] is True, "End-to-end all_passed flag failed")
check(validate_end_to_end_report(report)["valid"] is True,
      "End-to-end report validation failed")

# 5–10: inspect individual scenario outcomes
for scenario in report["scenarios"]:
    check(scenario.passed is True,
          f"Scenario failed: {scenario.scenario}")

# 11–15: representative content and safety properties
india = report["scenarios"][0]
check(india.grounded is True, "India fee must be grounded")
check(india.source_ids, "India fee provenance missing")
check("SE-DS-001" in india.course_ids,
      "Data Science course identity missing")

international = report["scenarios"][3]
check(international.human_handoff_required is True,
      "International pricing handoff missing")

nomatch = report["scenarios"][7]
check(nomatch.human_handoff_required is True,
      "NO_MATCH handoff missing")
check(nomatch.grounded is False,
      "NO_MATCH must not be grounded")

# 16–19: global read-only safety
for key in (
    "execution_enabled",
    "messaging_enabled",
    "external_actions_enabled",
    "crm_writes_enabled",
):
    check(report["safety"][key] is False,
          f"Report safety invariant failed: {key}")

check(report["safety"]["no_invention"] is True,
      "No-invention report invariant failed")

# 20–22: serialization integrity
serialization = verify_serialization_integrity(kb)
check(serialization["passed"] is True,
      "Serialization integrity failed")
check(not serialization["errors"],
      "Serialization should have no errors")
check(report["read_only"] is True,
      "End-to-end harness must be read-only")

print(f"MASTER KB BATCH 29: {passed}/{total} PASSED")
