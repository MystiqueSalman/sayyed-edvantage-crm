"""
Sayyed EdVantage AI Agent — Master KB Batch 25
Knowledge Completeness, Missing-Field & Human-Handoff Controller

Purpose:
- Add a formal completeness layer before grounded answers are finalized.
- Distinguish verified information from unspecified information.
- Detect commercial-region requirements and missing commercial details.
- Preserve documented source inconsistencies without correcting them.
- Require admissions/faculty handoff when the Master KB cannot safely answer.
- Never invent, execute, message, call external systems, or write CRM data.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH24 import (
    OrchestratedAnswer,
    orchestrate_query,
    build_master_kb_with_orchestrator,
    validate_orchestrated_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH22 import (
    COMMERCIAL_SOURCE_ID,
    get_commercial_answer,
    validate_commercial_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import (
    ResponsePlan,
    build_response_plan,
    validate_response_plan,
)


@dataclass
class CompletenessReport:
    status: str
    query: str
    intent: str
    course_ids: List[str]
    source_ids: List[str]
    supported_points: List[str] = field(default_factory=list)
    missing_points: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    human_handoff_required: bool = False


@dataclass
class ControlledAnswer:
    query: str
    answer: str
    response_status: str
    completeness_status: str
    intent: str
    course_ids: List[str]
    source_ids: List[str]
    supported_points: List[str]
    missing_points: List[str]
    warnings: List[str]
    grounded: bool
    human_handoff_required: bool
    safety: Dict[str, Any]


def _unique(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def assess_completeness(
    kb: Any,
    plan: ResponsePlan,
) -> CompletenessReport:
    """
    Determine whether the current evidence is sufficient for a safe answer.

    Completeness is conservative:
    - NO_MATCH => incomplete
    - certification => certification status must be explicitly handled
    - commercial => region/fee availability must be explicitly handled
    - documented inconsistencies => warning, not silent correction
    """
    validation = validate_response_plan(plan)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    if plan.response_status == "NO_MATCH":
        return CompletenessReport(
            status="INCOMPLETE",
            query=plan.query,
            intent=plan.intent,
            course_ids=[],
            source_ids=[],
            missing_points=[
                "No sufficiently grounded Master KB evidence matched the query."
            ],
            warnings=["Do not answer by guessing or using unsupported general knowledge."],
            human_handoff_required=True,
        )

    supported = [
        f"{item.official_name}: {item.text}"
        for item in plan.evidence
        if str(item.text).strip()
    ]

    missing = []
    warnings = []

    if plan.intent == "certification":
        missing.append(
            "Verified Certification details are not currently defined in the Master KB."
        )

    if plan.intent == "commercial":
        commercial = get_commercial_answer(kb, plan.query)
        commercial_validation = validate_commercial_answer(commercial)
        if not commercial_validation["valid"]:
            raise ValueError(commercial_validation["errors"])

        if commercial["status"] == "INTERNATIONAL_UNDEFINED":
            missing.append("International pricing is not currently defined.")
        elif commercial["status"] == "REGION_REQUIRED":
            missing.append("Student pricing region must be confirmed.")
        elif commercial["status"] == "OFFERING_NOT_FOUND":
            missing.append("A verified fee for the requested offering was not identified.")

    for course_id in plan.course_ids:
        course = kb.get_course(course_id)
        if not course:
            continue

        duration = course.knowledge.get("duration", {})
        if duration.get("status") == "documented_source_inconsistency":
            declared = duration.get("declared_duration_hours")
            module_total = duration.get("module_hours_total")
            warnings.append(
                f"{course_id}: documented duration inconsistency "
                f"({declared} declared vs {module_total} module-total hours)."
            )

    status = "COMPLETE" if not missing else "PARTIAL"

    handoff = plan.human_handoff_required or bool(missing)

    return CompletenessReport(
        status=status,
        query=plan.query,
        intent=plan.intent,
        course_ids=list(plan.course_ids),
        source_ids=list(plan.source_ids),
        supported_points=supported,
        missing_points=_unique(missing),
        warnings=_unique(warnings),
        human_handoff_required=handoff,
    )


def _append_missing_information(
    answer: str,
    report: CompletenessReport,
) -> str:
    parts = [answer] if answer else []

    if report.missing_points:
        parts.append(
            "Information not fully defined in the current Master KB:\n"
            + "\n".join(f"• {item}" for item in report.missing_points)
        )

    if report.human_handoff_required:
        parts.append(
            "Admissions/team or faculty can confirm the missing details."
        )

    return "\n\n".join(parts)


def build_controlled_answer(
    kb: Any,
    plan: ResponsePlan,
) -> ControlledAnswer:
    """
    Build a final controlled answer state.

    This layer controls completeness; it does not invent missing content.
    """
    report = assess_completeness(kb, plan)

    # Use the already-established Batch 24 orchestrator for the grounded
    # factual response, then add only completeness metadata/warnings.
    orchestrated = orchestrate_query(kb, plan.query, top_k=max(5, len(plan.evidence)))

    if orchestrated.response_status == "NO_MATCH":
        answer = _append_missing_information(orchestrated.answer, report)
        return ControlledAnswer(
            query=plan.query,
            answer=answer,
            response_status="NO_MATCH",
            completeness_status=report.status,
            intent=plan.intent,
            course_ids=[],
            source_ids=[],
            supported_points=report.supported_points,
            missing_points=report.missing_points,
            warnings=report.warnings,
            grounded=False,
            human_handoff_required=True,
            safety=copy.deepcopy(orchestrated.safety),
        )

    answer = orchestrated.answer

    if report.warnings:
        answer += (
            "\n\nImportant source note:\n"
            + "\n".join(f"• {warning}" for warning in report.warnings)
        )

    if report.missing_points:
        answer = _append_missing_information(answer, report)

    return ControlledAnswer(
        query=plan.query,
        answer=answer,
        response_status="READY",
        completeness_status=report.status,
        intent=plan.intent,
        course_ids=list(orchestrated.course_ids),
        source_ids=_unique(
            list(orchestrated.source_ids) + list(report.source_ids)
        ),
        supported_points=report.supported_points,
        missing_points=report.missing_points,
        warnings=report.warnings,
        grounded=orchestrated.grounded,
        human_handoff_required=(
            orchestrated.human_handoff_required
            or report.human_handoff_required
        ),
        safety=copy.deepcopy(orchestrated.safety),
    )


def controlled_answer_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> ControlledAnswer:
    plan = build_response_plan(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return build_controlled_answer(kb, plan)


def controlled_answer_to_dict(
    answer: ControlledAnswer,
) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "answer": answer.answer,
        "response_status": answer.response_status,
        "completeness_status": answer.completeness_status,
        "intent": answer.intent,
        "course_ids": list(answer.course_ids),
        "source_ids": list(answer.source_ids),
        "supported_points": list(answer.supported_points),
        "missing_points": list(answer.missing_points),
        "warnings": list(answer.warnings),
        "grounded": answer.grounded,
        "human_handoff_required": answer.human_handoff_required,
        "safety": copy.deepcopy(answer.safety),
    }


def validate_completeness_report(
    report: CompletenessReport,
) -> Dict[str, Any]:
    errors = []

    if report.status not in {"COMPLETE", "PARTIAL", "INCOMPLETE"}:
        errors.append("Invalid completeness status.")

    if report.status == "COMPLETE" and report.missing_points:
        errors.append("COMPLETE report cannot have missing points.")

    if report.status == "INCOMPLETE" and not report.human_handoff_required:
        errors.append("INCOMPLETE report must require handoff.")

    if report.human_handoff_required and report.status == "COMPLETE":
        # A complete factual answer may still require handoff due to a
        # deliberate commercial policy, so this is not automatically invalid.
        pass

    return {"valid": not errors, "errors": errors}


def validate_controlled_answer(
    answer: ControlledAnswer,
) -> Dict[str, Any]:
    errors = []

    if answer.response_status not in {"READY", "NO_MATCH"}:
        errors.append("Invalid response status.")

    if answer.completeness_status not in {
        "COMPLETE", "PARTIAL", "INCOMPLETE"
    }:
        errors.append("Invalid completeness status.")

    if answer.response_status == "READY":
        if not answer.grounded:
            errors.append("READY controlled answer must be grounded.")
        if not answer.answer.strip():
            errors.append("READY controlled answer cannot be empty.")
        if not answer.course_ids:
            errors.append("READY answer requires course IDs.")
        if not answer.source_ids:
            errors.append("READY answer requires source IDs.")

    if answer.response_status == "NO_MATCH":
        if answer.grounded:
            errors.append("NO_MATCH cannot be grounded.")
        if answer.course_ids or answer.source_ids:
            errors.append("NO_MATCH cannot contain course/source IDs.")

    if answer.completeness_status == "INCOMPLETE" and not answer.human_handoff_required:
        errors.append("INCOMPLETE answer must require handoff.")

    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if answer.safety.get(key) is not False:
            errors.append(f"Safety invariant violated: {key} must be False.")

    if answer.safety.get("no_invention") is not True:
        errors.append("No-invention policy must be True.")

    return {"valid": not errors, "errors": errors}


def build_master_kb_with_completeness_control() -> Any:
    return build_master_kb_with_orchestrator()


# Explicit downstream aliases.
check_answer_completeness = assess_completeness
generate_controlled_answer = build_controlled_answer


if __name__ == "__main__":
    kb = build_master_kb_with_completeness_control()
    answer = controlled_answer_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 25 validation:", validate_controlled_answer(answer))
    print(answer.answer)
