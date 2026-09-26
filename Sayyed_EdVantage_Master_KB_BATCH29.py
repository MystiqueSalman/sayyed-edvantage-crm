"""
Sayyed EdVantage AI Agent — Master KB Batch 29
End-to-End Master KB → AI Agent Verification Harness

Purpose:
- Verify the complete read-only chain:
  Master KB → retrieval/answer policy → completeness → finalization
  → delivery contract → AI Agent integration contract.
- Exercise representative course, commercial, missing-information,
  inconsistency, and no-match scenarios.
- Verify provenance and safety invariants end-to-end.
- Verify that the integration layer remains read-only and does not expose
  action capabilities.
- This is a verification harness, not an execution layer.
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


@dataclass
class VerificationResult:
    passed: bool
    scenario: str
    query: str
    integration_status: str
    response_status: str
    completeness_status: str
    grounded: bool
    human_handoff_required: bool
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _verify_common_safety(safety: Dict[str, Any]) -> List[str]:
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


def verify_scenario(
    kb: Any,
    scenario: str,
    query: str,
    expected_status: str,
    expected_completeness: str,
    expected_grounded: bool = True,
    expected_handoff: bool = False,
    required_text: str = "",
) -> VerificationResult:
    answer = agent_response_query(kb, query)

    errors = []
    validation = validate_agent_response_contract(answer)
    errors.extend(validation["errors"])
    errors.extend(_verify_common_safety(answer.safety))

    if answer.integration_status != expected_status:
        errors.append(
            f"Expected integration status {expected_status}, "
            f"got {answer.integration_status}."
        )

    if answer.completeness_status != expected_completeness:
        errors.append(
            f"Expected completeness {expected_completeness}, "
            f"got {answer.completeness_status}."
        )

    if answer.grounded != expected_grounded:
        errors.append(
            f"Expected grounded={expected_grounded}, got {answer.grounded}."
        )

    if answer.human_handoff_required != expected_handoff:
        errors.append(
            f"Expected handoff={expected_handoff}, "
            f"got {answer.human_handoff_required}."
        )

    if required_text and required_text not in answer.response:
        errors.append(f"Required response text missing: {required_text}")

    if answer.integration_status == INTEGRATION_READY:
        if not answer.source_ids:
            errors.append("Integration-ready result lost provenance.")
        if not answer.response.strip():
            errors.append("Integration-ready result lost response text.")

    if answer.integration_status == INTEGRATION_HANDOFF:
        if answer.response.strip():
            errors.append("Handoff result exposed response text.")
        if not answer.gate_errors:
            errors.append("Handoff result lost diagnostic reason.")

    return VerificationResult(
        passed=not errors,
        scenario=scenario,
        query=query,
        integration_status=answer.integration_status,
        response_status=answer.response_status,
        completeness_status=answer.completeness_status,
        grounded=answer.grounded,
        human_handoff_required=answer.human_handoff_required,
        course_ids=list(answer.course_ids),
        source_ids=list(answer.source_ids),
        errors=_unique(errors),
    )


def run_end_to_end_verification(kb: Any = None) -> Dict[str, Any]:
    if kb is None:
        kb = build_master_kb_with_agent_integration()

    scenarios = [
        verify_scenario(
            kb,
            "Data Science India fee",
            "What is the fee for Data Science in India?",
            INTEGRATION_READY,
            "COMPLETE",
            True,
            False,
            "₹50,000 + GST",
        ),
        verify_scenario(
            kb,
            "Data Analytics India fee",
            "What is the fee for Data Analytics in India?",
            INTEGRATION_READY,
            "COMPLETE",
            True,
            False,
            "₹40,000 + GST",
        ),
        verify_scenario(
            kb,
            "Python program",
            "Python programming",
            INTEGRATION_READY,
            "COMPLETE",
            True,
            False,
        ),
        verify_scenario(
            kb,
            "International pricing protection",
            "What is the fee for Data Science outside India?",
            INTEGRATION_READY,
            "PARTIAL",
            True,
            True,
            "Indian pricing must not be substituted",
        ),
        verify_scenario(
            kb,
            "Unknown pricing region",
            "What is the fee for Python?",
            INTEGRATION_READY,
            "PARTIAL",
            True,
            True,
            "pricing region",
        ),
        verify_scenario(
            kb,
            "Certification uncertainty",
            "Does Data Science provide certification?",
            INTEGRATION_READY,
            "PARTIAL",
            True,
            True,
            "Certification details",
        ),
        verify_scenario(
            kb,
            "Linux documented inconsistency",
            "Linux administration duration",
            INTEGRATION_READY,
            "COMPLETE",
            True,
            False,
            "documented duration inconsistency",
        ),
        verify_scenario(
            kb,
            "No match",
            "zzzz completely nonexistent topic",
            INTEGRATION_HANDOFF,
            "INCOMPLETE",
            False,
            True,
        ),
    ]

    passed = sum(1 for item in scenarios if item.passed)

    return {
        "passed": passed,
        "total": len(scenarios),
        "all_passed": passed == len(scenarios),
        "scenarios": scenarios,
        "safety": {
            "execution_enabled": False,
            "messaging_enabled": False,
            "external_actions_enabled": False,
            "crm_writes_enabled": False,
            "no_invention": True,
        },
        "read_only": True,
    }


def verify_serialization_integrity(kb: Any = None) -> Dict[str, Any]:
    if kb is None:
        kb = build_master_kb_with_agent_integration()

    answer = agent_response_query(kb, "What is the fee for Data Science in India?")
    before = copy.deepcopy(agent_response_to_dict(answer))
    after = agent_response_to_dict(answer)

    errors = []
    if before != after:
        errors.append("Repeated serialization changed the contract.")

    after["source_ids"].append("MUTATION")
    after["safety"]["execution_enabled"] = True

    if "MUTATION" in answer.source_ids:
        errors.append("Serialized source IDs mutated original contract.")
    if answer.safety["execution_enabled"] is not False:
        errors.append("Serialized safety mutated original contract.")

    return {
        "passed": not errors,
        "errors": errors,
    }


def validate_end_to_end_report(
    report: Dict[str, Any],
) -> Dict[str, Any]:
    errors = []

    if report.get("all_passed") is not True:
        errors.append("Not all end-to-end scenarios passed.")

    if report.get("read_only") is not True:
        errors.append("Verification report must remain read-only.")

    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if report.get("safety", {}).get(key) is not False:
            errors.append(f"Report safety invariant failed: {key}")

    if report.get("safety", {}).get("no_invention") is not True:
        errors.append("Report no-invention invariant failed.")

    return {"valid": not errors, "errors": _unique(errors)}


def build_master_kb_for_end_to_end_verification() -> Any:
    return build_master_kb_with_agent_integration()


# Explicit downstream aliases.
run_e2e_verification = run_end_to_end_verification
verify_integration = run_end_to_end_verification


if __name__ == "__main__":
    kb = build_master_kb_for_end_to_end_verification()
    report = run_end_to_end_verification(kb)
    serialization = verify_serialization_integrity(kb)

    print(
        f"Batch 29 scenarios: "
        f"{report['passed']}/{report['total']} PASSED"
    )
    print("Batch 29 serialization:", serialization)
    print("Batch 29 report:", validate_end_to_end_report(report))
