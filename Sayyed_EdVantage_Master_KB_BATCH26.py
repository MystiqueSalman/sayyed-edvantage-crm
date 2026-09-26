"""
Sayyed EdVantage AI Agent — Master KB Batch 26
Controlled Knowledge Answer Finalization & Safety Gate

Purpose:
- Establish the final deterministic gate after Batch 25 completeness control.
- Finalize only grounded, provenance-backed, safety-compliant answers.
- Block unsafe or structurally invalid answer states.
- Preserve PARTIAL/INCOMPLETE + human-handoff behavior.
- Never invent missing information.
- Never execute actions, send messages, call external systems, or write CRM data.

This batch is a gate, not a new knowledge source.
It does not alter course content, fees, curriculum, or source records.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH25 import (
    ControlledAnswer,
    controlled_answer_query,
    validate_controlled_answer,
    build_master_kb_with_completeness_control,
)


FINALIZED = "FINALIZED"
BLOCKED = "BLOCKED"


@dataclass
class FinalizedAnswer:
    query: str
    answer: str
    finalization_status: str
    response_status: str
    completeness_status: str
    intent: str
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    supported_points: List[str] = field(default_factory=list)
    missing_points: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    grounded: bool = False
    human_handoff_required: bool = False
    safety: Dict[str, Any] = field(default_factory=dict)
    gate_errors: List[str] = field(default_factory=list)


def _required_safety_is_safe(safety: Dict[str, Any]) -> List[str]:
    errors = []
    required_false = (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    )
    for key in required_false:
        if safety.get(key) is not False:
            errors.append(f"{key} must be False.")

    if safety.get("no_invention") is not True:
        errors.append("no_invention must be True.")

    return errors


def _gate_controlled_answer(answer: ControlledAnswer) -> List[str]:
    errors = []

    validation = validate_controlled_answer(answer)
    if not validation["valid"]:
        errors.extend(validation["errors"])

    errors.extend(_required_safety_is_safe(answer.safety))

    if not answer.answer or not answer.answer.strip():
        errors.append("Final answer text cannot be empty.")

    if answer.response_status == "READY":
        if not answer.grounded:
            errors.append("READY answer must be grounded.")
        if not answer.source_ids:
            errors.append("READY answer must retain provenance source IDs.")
        if answer.completeness_status == "INCOMPLETE":
            errors.append("READY answer cannot be INCOMPLETE.")

    if answer.response_status == "NO_MATCH":
        # Batch 26 is the final-answer boundary. A NO_MATCH result is
        # deliberately blocked rather than finalized as a normal answer.
        errors.append("NO_MATCH answers cannot be finalized.")
        if answer.grounded:
            errors.append("NO_MATCH answer cannot be grounded.")
        if answer.completeness_status != "INCOMPLETE":
            errors.append("NO_MATCH answer must be INCOMPLETE.")
        if not answer.human_handoff_required:
            errors.append("NO_MATCH answer must require human handoff.")

    if answer.completeness_status in {"PARTIAL", "INCOMPLETE"}:
        if not answer.human_handoff_required:
            errors.append(
                "PARTIAL/INCOMPLETE answer must require human handoff."
            )

    return errors


def finalize_controlled_answer(
    answer: ControlledAnswer,
) -> FinalizedAnswer:
    """
    Apply the final safety/provenance/completeness gate.

    No content is invented or silently rewritten. A valid controlled answer
    is copied into a FINALIZED result. An invalid answer becomes BLOCKED and
    exposes gate_errors for diagnostics.
    """
    errors = _gate_controlled_answer(answer)

    if errors:
        return FinalizedAnswer(
            query=answer.query,
            answer="",
            finalization_status=BLOCKED,
            response_status=answer.response_status,
            completeness_status=answer.completeness_status,
            intent=answer.intent,
            course_ids=list(answer.course_ids),
            source_ids=list(answer.source_ids),
            supported_points=list(answer.supported_points),
            missing_points=list(answer.missing_points),
            warnings=list(answer.warnings),
            grounded=False,
            human_handoff_required=True,
            safety=copy.deepcopy(answer.safety),
            gate_errors=list(dict.fromkeys(errors)),
        )

    return FinalizedAnswer(
        query=answer.query,
        answer=answer.answer,
        finalization_status=FINALIZED,
        response_status=answer.response_status,
        completeness_status=answer.completeness_status,
        intent=answer.intent,
        course_ids=list(answer.course_ids),
        source_ids=list(answer.source_ids),
        supported_points=list(answer.supported_points),
        missing_points=list(answer.missing_points),
        warnings=list(answer.warnings),
        grounded=answer.grounded,
        human_handoff_required=answer.human_handoff_required,
        safety=copy.deepcopy(answer.safety),
        gate_errors=[],
    )


def finalize_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> FinalizedAnswer:
    controlled = controlled_answer_query(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return finalize_controlled_answer(controlled)


def build_final_answer(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> FinalizedAnswer:
    return finalize_query(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )


def finalized_answer_to_dict(
    answer: FinalizedAnswer,
) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "answer": answer.answer,
        "finalization_status": answer.finalization_status,
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
        "gate_errors": list(answer.gate_errors),
    }


def validate_finalized_answer(
    answer: FinalizedAnswer,
) -> Dict[str, Any]:
    errors = []

    if answer.finalization_status not in {FINALIZED, BLOCKED}:
        errors.append("Invalid finalization status.")

    if answer.finalization_status == FINALIZED:
        if not answer.answer.strip():
            errors.append("FINALIZED answer cannot be empty.")
        if answer.gate_errors:
            errors.append("FINALIZED answer cannot contain gate errors.")
        if answer.response_status == "READY":
            if not answer.grounded:
                errors.append("FINALIZED READY answer must be grounded.")
            if not answer.source_ids:
                errors.append("FINALIZED READY answer requires source IDs.")
        if answer.response_status == "NO_MATCH":
            errors.append("NO_MATCH cannot be FINALIZED as a normal answer.")

    if answer.finalization_status == BLOCKED:
        if answer.answer.strip():
            errors.append("BLOCKED answer must not expose final answer text.")
        if not answer.gate_errors:
            errors.append("BLOCKED answer must contain gate errors.")
        if not answer.human_handoff_required:
            errors.append("BLOCKED answer must require human handoff.")

    errors.extend(_required_safety_is_safe(answer.safety))

    return {"valid": not errors, "errors": list(dict.fromkeys(errors))}


def build_master_kb_with_finalization_gate() -> Any:
    return build_master_kb_with_completeness_control()


# Explicit downstream aliases.
finalize_answer = finalize_controlled_answer
answer_query_finalized = finalize_query


if __name__ == "__main__":
    kb = build_master_kb_with_finalization_gate()
    result = finalize_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 26 validation:", validate_finalized_answer(result))
    print(result.finalization_status)
    print(result.answer)
