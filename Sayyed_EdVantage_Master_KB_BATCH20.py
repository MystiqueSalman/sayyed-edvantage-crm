"""
Sayyed EdVantage AI Agent — Master KB Batch 20
Knowledge-Grounded Answer Generator

Purpose:
- Generate a concise, deterministic answer from Batch 19 ResponsePlan evidence.
- Use only Master KB evidence plus explicit policy metadata.
- Preserve unknowns and documented source inconsistencies.
- Never invent fees, certifications, outcomes, or commercial terms.
- Never send messages, execute actions, call external systems, or write CRM data.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH19 import (
    ResponsePlan,
    build_master_kb_with_response_policy,
    build_response_plan,
    validate_response_plan,
)


@dataclass
class GroundedAnswer:
    query: str
    answer: str
    response_status: str
    course_ids: List[str]
    source_ids: List[str]
    grounded: bool
    human_handoff_required: bool
    safety: Dict[str, Any]


def _clean_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


def _format_evidence(plan: ResponsePlan) -> List[str]:
    bullets = []
    seen = set()

    for evidence in plan.evidence:
        text = _clean_text(evidence.text)
        if not text:
            continue

        key = (evidence.course_id, evidence.path, text)
        if key in seen:
            continue
        seen.add(key)

        if evidence.path == "__course_identity__":
            bullets.append(f"{evidence.official_name}.")
        else:
            bullets.append(f"{text}.")

    return bullets


def _commercial_note(plan: ResponsePlan) -> Optional[str]:
    q = plan.query.lower()

    international = any(
        x in q for x in ("international", "outside india", "overseas", "abroad")
    )

    if international:
        return (
            "International pricing is not currently defined in the Master KB, "
            "so Indian pricing should not be substituted. Admissions/team "
            "should provide the applicable fee and enrollment details."
        )

    if plan.intent == "commercial":
        evidence_text = " ".join(e.text.lower() for e in plan.evidence)
        has_explicit_fee = any(
            token in evidence_text
            for token in ("₹", "inr", "rs ", "rupees", "base_fee", "fee")
        )

        if not has_explicit_fee:
            return (
                "The retrieved Master KB context does not contain a verified "
                "fee amount for this query, so I should not invent one. "
                "Admissions can confirm the applicable fee and final enrollment details."
            )

    return None


def _find_documented_duration_inconsistencies(
    kb: Any,
    course_ids: List[str],
) -> List[str]:
    """
    Read authoritative course metadata to preserve documented source
    inconsistencies even when retrieval top_k does not include the nested
    duration status field.

    This does not reconcile or change the source.
    """
    found = []

    for course_id in course_ids:
        course = kb.get_course(course_id)
        if not course:
            continue

        duration = course.knowledge.get("duration", {})
        status = duration.get("status")
        declared = duration.get("declared_duration_hours")
        module_total = duration.get("module_hours_total")

        if (
            status == "documented_source_inconsistency"
            and declared is not None
            and module_total is not None
        ):
            found.append(
                f"{course_id}: declared duration is {declared} hours while "
                f"the detailed module total is {module_total} hours."
            )

    return found


def generate_grounded_answer(
    plan: ResponsePlan,
    duration_inconsistencies: Optional[List[str]] = None,
) -> GroundedAnswer:
    """
    Generate a user-facing answer using only the ResponsePlan and explicitly
    supplied authoritative metadata.
    """
    validation = validate_response_plan(plan)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    safety = copy.deepcopy(plan.safety_policy)

    # Batch 19's ResponsePlan API uses response_status, not matched.
    if plan.response_status == "NO_MATCH":
        answer = (
            "I couldn't find sufficiently grounded information for that "
            "request in the current Sayyed EdVantage Master Knowledge Base. "
            "I don't want to guess or invent the missing details."
        )

        return GroundedAnswer(
            query=plan.query,
            answer=answer,
            response_status="NO_MATCH",
            course_ids=[],
            source_ids=[],
            grounded=False,
            human_handoff_required=True,
            safety=safety,
        )

    bullets = _format_evidence(plan)
    parts = []

    if bullets:
        parts.append("Based on the Sayyed EdVantage Master Knowledge Base:")
        parts.append("\n".join(f"• {bullet}" for bullet in bullets))

    commercial_note = _commercial_note(plan)
    if commercial_note:
        parts.append(commercial_note)

    if plan.intent == "certification" and any(
        "Certification details" in u for u in plan.unknowns
    ):
        parts.append(
            "Certification details are not verified in the current Master KB."
        )

    if plan.intent == "career":
        parts.append(
            "The program information does not establish guaranteed employment, "
            "placement, salary, income, or a specific job outcome."
        )

    if duration_inconsistencies:
        parts.append(
            "A source used for this response contains a documented duration "
            "inconsistency; the figures should not be silently rebalanced."
        )

    if plan.human_handoff_required:
        parts.append(
            "Admissions/team can confirm the applicable details where the "
            "current Master KB does not define them."
        )

    answer = "\n\n".join(parts).strip()

    if not answer:
        answer = (
            "The current Master KB contains matching information, but not "
            "enough grounded detail to produce a reliable answer."
        )

    return GroundedAnswer(
        query=plan.query,
        answer=answer,
        response_status="READY",
        course_ids=list(plan.course_ids),
        source_ids=list(plan.source_ids),
        grounded=True,
        human_handoff_required=plan.human_handoff_required,
        safety=safety,
    )


def answer_query(
    kb: Any,
    query: str,
    top_k: int = 5,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> GroundedAnswer:
    plan = build_response_plan(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )

    inconsistencies = []
    if plan.response_status != "NO_MATCH":
        inconsistencies = _find_documented_duration_inconsistencies(
            kb, plan.course_ids
        )

    return generate_grounded_answer(
        plan,
        duration_inconsistencies=inconsistencies,
    )


def grounded_answer_to_dict(answer: GroundedAnswer) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "answer": answer.answer,
        "response_status": answer.response_status,
        "course_ids": list(answer.course_ids),
        "source_ids": list(answer.source_ids),
        "grounded": answer.grounded,
        "human_handoff_required": answer.human_handoff_required,
        "safety": copy.deepcopy(answer.safety),
    }


def validate_grounded_answer(answer: GroundedAnswer) -> Dict[str, Any]:
    errors = []

    if answer.response_status not in {"READY", "NO_MATCH"}:
        errors.append("Invalid response status.")

    if answer.response_status == "READY":
        if not answer.grounded:
            errors.append("READY answer must be grounded.")
        if not answer.answer.strip():
            errors.append("READY answer must not be empty.")
        if not answer.course_ids:
            errors.append("READY answer must preserve course IDs.")
        if not answer.source_ids:
            errors.append("READY answer must preserve source IDs.")

    if answer.response_status == "NO_MATCH" and answer.grounded:
        errors.append("NO_MATCH answer cannot be marked grounded.")

    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if answer.safety.get(key) is not False:
            errors.append(f"Safety invariant violated: {key} must be False.")

    if answer.safety.get("no_invention") is not True:
        errors.append("No-invention safety must be True.")

    return {"valid": not errors, "errors": errors}


def build_master_kb_with_answer_generator() -> Any:
    return build_master_kb_with_response_policy()


generate_answer = generate_grounded_answer
serialize_grounded_answer = grounded_answer_to_dict


if __name__ == "__main__":
    kb = build_master_kb_with_answer_generator()
    answer = answer_query(kb, "Python programming", top_k=3)
    print("Batch 20 validation:", validate_grounded_answer(answer))
    print(answer.answer)
