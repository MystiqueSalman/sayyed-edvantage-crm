"""
Sayyed EdVantage AI Agent — Master KB Batch 30
Master KB / AI Agent Integration Closure & Regression Contract

Purpose:
- Establish the final closure contract for the 30-batch Master KB
  implementation sequence.
- Verify that the complete pipeline remains internally consistent.
- Verify all nine commercial offerings and all seven course records exist.
- Verify representative answer, safety, provenance, handoff, and
  read-only invariants through the final Batch-28 integration boundary.
- Provide a deterministic closure snapshot for downstream development.
- This batch is verification/closure only. It does not activate execution,
  messaging, external actions, or CRM writes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
import copy

from Sayyed_EdVantage_Master_KB_BATCH28 import (
    INTEGRATION_READY,
    INTEGRATION_HANDOFF,
    agent_response_query,
    agent_response_to_dict,
    validate_agent_response_contract,
    build_master_kb_with_agent_integration,
)
from Sayyed_EdVantage_Master_KB_BATCH29 import (
    run_end_to_end_verification,
    verify_serialization_integrity,
    validate_end_to_end_report,
)


CLOSURE_READY = "CLOSURE_READY"
CLOSURE_BLOCKED = "CLOSURE_BLOCKED"

EXPECTED_COURSE_IDS = [
    "SE-DS-001",
    "SE-DA-001",
    "SE-AIGEN-001",
    "SE-PY-001",
    "SE-LINUX-001",
    "SE-DEVOPS-001",
    "SE-EHC-001",
]

EXPECTED_OFFERING_IDS = [
    "SE-OFFER-DS-INDIA",
    "SE-OFFER-DA-INDIA",
    "SE-OFFER-DSDA-COMBO-INDIA",
    "SE-OFFER-AIGEN-INDIA",
    "SE-OFFER-PY-INDIA",
    "SE-OFFER-LINUX-INDIA",
    "SE-OFFER-DEVOPS-INDIA",
    "SE-OFFER-LINUXDEVOPS-COMBO-INDIA",
    "SE-OFFER-EHC-INDIA",
]


@dataclass
class ClosureReport:
    status: str
    batch_sequence: str
    course_count: int
    offering_count: int
    verified_course_ids: List[str] = field(default_factory=list)
    verified_offering_ids: List[str] = field(default_factory=list)
    regression_passed: bool = False
    safety_passed: bool = False
    provenance_passed: bool = False
    handoff_passed: bool = False
    read_only: bool = True
    errors: List[str] = field(default_factory=list)


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _safety_errors(safety: Dict[str, Any]) -> List[str]:
    errors = []
    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if safety.get(key) is not False:
            errors.append(f"{key} must be False.")
    if safety.get("no_invention") is not True:
        errors.append("no_invention must be True.")
    return errors


def _verify_kb_inventory(kb: Any) -> Dict[str, Any]:
    errors = []

    actual_courses = list(kb.courses.keys())
    actual_offerings = list(kb.offerings.keys())

    for course_id in EXPECTED_COURSE_IDS:
        if course_id not in actual_courses:
            errors.append(f"Missing expected course: {course_id}")

    for offering_id in EXPECTED_OFFERING_IDS:
        if offering_id not in actual_offerings:
            errors.append(f"Missing expected offering: {offering_id}")

    return {
        "passed": not errors,
        "course_ids": actual_courses,
        "offering_ids": actual_offerings,
        "errors": errors,
    }


def run_closure_regression(kb: Any = None) -> ClosureReport:
    if kb is None:
        kb = build_master_kb_with_agent_integration()

    errors = []

    inventory = _verify_kb_inventory(kb)
    errors.extend(inventory["errors"])

    e2e = run_end_to_end_verification(kb)
    if not e2e["all_passed"]:
        errors.append("Batch 29 end-to-end regression did not fully pass.")

    e2e_validation = validate_end_to_end_report(e2e)
    errors.extend(e2e_validation["errors"])

    serialization = verify_serialization_integrity(kb)
    if not serialization["passed"]:
        errors.extend(serialization["errors"])

    # Final representative contract checks.
    india = agent_response_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    errors.extend(validate_agent_response_contract(india)["errors"])
    errors.extend(_safety_errors(india.safety))

    nomatch = agent_response_query(
        kb,
        "zzzz completely nonexistent topic",
    )
    errors.extend(validate_agent_response_contract(nomatch)["errors"])
    errors.extend(_safety_errors(nomatch.safety))

    if india.integration_status != INTEGRATION_READY:
        errors.append("Verified Indian answer did not reach INTEGRATION_READY.")
    if not india.source_ids:
        errors.append("Final regression lost Indian answer provenance.")
    if nomatch.integration_status != INTEGRATION_HANDOFF:
        errors.append("NO_MATCH did not reach INTEGRATION_HANDOFF.")
    if nomatch.response.strip():
        errors.append("NO_MATCH exposed response text at closure.")

    errors = _unique(errors)

    safety_passed = (
        not _safety_errors(india.safety)
        and not _safety_errors(nomatch.safety)
    )
    provenance_passed = bool(india.source_ids)
    handoff_passed = (
        nomatch.integration_status == INTEGRATION_HANDOFF
        and nomatch.human_handoff_required
        and bool(nomatch.gate_errors)
    )
    regression_passed = (
        inventory["passed"]
        and e2e["all_passed"]
        and serialization["passed"]
    )

    status = CLOSURE_READY if not errors else CLOSURE_BLOCKED

    return ClosureReport(
        status=status,
        batch_sequence="BATCH01-BATCH30",
        course_count=len(inventory["course_ids"]),
        offering_count=len(inventory["offering_ids"]),
        verified_course_ids=list(inventory["course_ids"]),
        verified_offering_ids=list(inventory["offering_ids"]),
        regression_passed=regression_passed,
        safety_passed=safety_passed,
        provenance_passed=provenance_passed,
        handoff_passed=handoff_passed,
        read_only=True,
        errors=errors,
    )


def validate_closure_report(report: ClosureReport) -> Dict[str, Any]:
    errors = []

    if report.status not in {CLOSURE_READY, CLOSURE_BLOCKED}:
        errors.append("Invalid closure status.")

    if report.status == CLOSURE_READY and report.errors:
        errors.append("CLOSURE_READY cannot contain errors.")

    if report.status == CLOSURE_READY:
        if report.batch_sequence != "BATCH01-BATCH30":
            errors.append("Final batch sequence mismatch.")
        if report.course_count != 7:
            errors.append("Closure must contain 7 course records.")
        if report.offering_count != 9:
            errors.append("Closure must contain 9 commercial offerings.")
        if not report.regression_passed:
            errors.append("Closure regression must pass.")
        if not report.safety_passed:
            errors.append("Closure safety checks must pass.")
        if not report.provenance_passed:
            errors.append("Closure provenance check must pass.")
        if not report.handoff_passed:
            errors.append("Closure handoff check must pass.")

    if report.read_only is not True:
        errors.append("Closure must remain read-only.")

    return {"valid": not errors, "errors": _unique(errors)}


def closure_report_to_dict(report: ClosureReport) -> Dict[str, Any]:
    return {
        "status": report.status,
        "batch_sequence": report.batch_sequence,
        "course_count": report.course_count,
        "offering_count": report.offering_count,
        "verified_course_ids": list(report.verified_course_ids),
        "verified_offering_ids": list(report.verified_offering_ids),
        "regression_passed": report.regression_passed,
        "safety_passed": report.safety_passed,
        "provenance_passed": report.provenance_passed,
        "handoff_passed": report.handoff_passed,
        "read_only": report.read_only,
        "errors": list(report.errors),
    }


def build_master_kb_for_closure() -> Any:
    return build_master_kb_with_agent_integration()


def build_master_kb() -> Any:
    """Discovery-compatible entry point for the Phase-4 authoritative bridge.

    Sayyed_EdVantage_PHASE4_INTEGRATION04 discovers the first importable
    module exposing build_master_kb()/MasterKnowledgeBase and uses it as the
    AI's course catalogue. BATCH30 is the current catalogue (7 courses,
    including SE-EHC-001 Ethical Hacking & Cybersecurity). Without this
    alias the bridge silently falls through to the stale BATCH01 module,
    which contains only SE-DSP-001, so the bot denies all other courses.
    """
    return build_master_kb_for_closure()


# Explicit downstream aliases.
run_final_closure = run_closure_regression
validate_closure = validate_closure_report


if __name__ == "__main__":
    kb = build_master_kb_for_closure()
    report = run_closure_regression(kb)
    print("Batch 30 closure:", report.status)
    print("Batch 30 validation:", validate_closure_report(report))
    print("Courses:", report.course_count)
    print("Offerings:", report.offering_count)
