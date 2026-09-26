import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from Sayyed_EdVantage_Master_KB_BATCH30 import (
    CLOSURE_READY,
    run_closure_regression,
    validate_closure_report,
    closure_report_to_dict,
    build_master_kb_for_closure,
    EXPECTED_COURSE_IDS,
    EXPECTED_OFFERING_IDS,
)


passed = 0
total = 0

def check(condition, label):
    global passed, total
    total += 1
    if not condition:
        raise AssertionError(label)
    passed += 1


kb = build_master_kb_for_closure()
report = run_closure_regression(kb)

# 1–8: final closure state
check(report.status == CLOSURE_READY,
      "Final closure must be CLOSURE_READY")
check(report.batch_sequence == "BATCH01-BATCH30",
      "Batch sequence closure mismatch")
check(report.course_count == 7,
      "Final closure must contain 7 courses")
check(report.offering_count == 9,
      "Final closure must contain 9 offerings")
check(report.regression_passed is True,
      "Final regression must pass")
check(report.safety_passed is True,
      "Final safety must pass")
check(report.provenance_passed is True,
      "Final provenance must pass")
check(report.handoff_passed is True,
      "Final handoff must pass")

# 9–15: all expected courses
for course_id in EXPECTED_COURSE_IDS:
    check(course_id in report.verified_course_ids,
          f"Missing course at closure: {course_id}")

# 16–24: all expected offerings
for offering_id in EXPECTED_OFFERING_IDS:
    check(offering_id in report.verified_offering_ids,
          f"Missing offering at closure: {offering_id}")

# 25–27: closure validation + serialization
check(report.read_only is True,
      "Closure must remain read-only")
check(validate_closure_report(report)["valid"] is True,
      "Closure validation failed")
serialized = closure_report_to_dict(report)
check(serialized["status"] == CLOSURE_READY,
      "Closure serialization status mismatch")

# 28–30: no hidden errors and stable counts
check(report.errors == [],
      "CLOSURE_READY must have no errors")
check(len(report.verified_course_ids) >= 7,
      "Closure course inventory incomplete")
check(len(report.verified_offering_ids) >= 9,
      "Closure offering inventory incomplete")

print(f"MASTER KB BATCH 30: {passed}/{total} PASSED")
