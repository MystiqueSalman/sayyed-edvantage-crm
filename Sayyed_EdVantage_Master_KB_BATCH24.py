"""
Sayyed EdVantage AI Agent — Master KB Batch 24
Commercial-Aware Multi-Course Answer Orchestrator

Purpose:
- Combine Batch 21 multi-course composition with Batch 23 commercial-aware
  answering.
- Keep course evidence and commercial evidence separate.
- Support course-specific and combo commercial offerings.
- Select verified Indian fees only when the pricing region is Indian.
- Preserve international/unknown-region safety.
- Preserve provenance and no-invention policies.
- Never send messages, execute actions, call external systems, or write CRM data.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH21 import (
    CourseEvidenceGroup,
    group_response_plan_by_course,
    select_primary_course,
    validate_course_groups,
)
from Sayyed_EdVantage_Master_KB_BATCH22 import (
    COMMERCIAL_SOURCE_ID,
    get_commercial_answer,
    validate_commercial_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH23 import (
    CommercialAwareAnswer,
    generate_commercial_aware_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import (
    ResponsePlan,
    build_response_plan,
    validate_response_plan,
)


@dataclass
class OrchestratedAnswer:
    query: str
    response_status: str
    answer: str
    intent: str
    primary_course_id: Optional[str]
    course_ids: List[str]
    source_ids: List[str]
    evidence_groups: List[CourseEvidenceGroup] = field(default_factory=list)
    commercial_status: Optional[str] = None
    fee: Optional[int] = None
    currency: Optional[str] = None
    human_handoff_required: bool = False
    grounded: bool = False
    safety: Dict[str, Any] = field(default_factory=dict)


def _unique(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _is_commercial(plan: ResponsePlan) -> bool:
    return plan.intent == "commercial"


def _append_commercial_note(
    answer: str,
    commercial: Dict[str, Any],
) -> str:
    """
    Add only the commercial information returned by Batch 22.
    """
    if commercial["status"] == "VERIFIED_INDIA_FEE":
        note = (
            f'Verified Indian commercial information: '
            f'{commercial["offering"]["name"]}: '
            f'₹{commercial["fee"]:,} + GST.'
        )
        return f"{answer}\n\n{note}" if answer else note

    if commercial["status"] == "INTERNATIONAL_UNDEFINED":
        note = commercial["message"]
        return f"{answer}\n\n{note}" if answer else note

    if commercial["status"] == "REGION_REQUIRED":
        note = commercial["message"]
        return f"{answer}\n\n{note}" if answer else note

    if commercial["status"] == "OFFERING_NOT_FOUND":
        note = commercial["message"]
        return f"{answer}\n\n{note}" if answer else note

    return answer


def _course_answer_section(plan: ResponsePlan) -> str:
    """
    Build course evidence text without merging different course records.
    """
    groups = group_response_plan_by_course(plan)
    if not groups:
        return ""

    sections = ["Based on the Sayyed EdVantage Master Knowledge Base:"]

    for group in groups:
        sections.append(f"### {group.official_name}")
        seen = set()

        for item in group.evidence:
            text = " ".join(str(item["text"]).split()).strip()
            if not text:
                continue
            key = (item["path"], text)
            if key in seen:
                continue
            seen.add(key)
            sections.append(f"• {text}")

    return "\n\n".join(sections)


def orchestrate_response(
    kb: Any,
    plan: ResponsePlan,
) -> OrchestratedAnswer:
    """
    Orchestrate course evidence and commercial information.

    The course layer and commercial layer are intentionally separate:
    commercial lookup never rewrites course evidence.
    """
    validation = validate_response_plan(plan)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    safety = copy.deepcopy(plan.safety_policy)

    if plan.response_status == "NO_MATCH":
        return OrchestratedAnswer(
            query=plan.query,
            response_status="NO_MATCH",
            answer=(
                "I couldn't find sufficiently grounded information for that "
                "request in the current Sayyed EdVantage Master Knowledge Base. "
                "I don't want to guess or merge unrelated information."
            ),
            intent=plan.intent,
            primary_course_id=None,
            course_ids=[],
            source_ids=[],
            evidence_groups=[],
            human_handoff_required=True,
            grounded=False,
            safety=safety,
        )

    groups = group_response_plan_by_course(plan)
    group_validation = validate_course_groups(groups)
    if not group_validation["valid"]:
        raise ValueError(group_validation["errors"])

    primary = select_primary_course(groups)
    course_answer = _course_answer_section(plan)

    commercial_status = None
    fee = None
    currency = None
    commercial_source = None
    handoff = plan.human_handoff_required
    answer = course_answer

    if _is_commercial(plan):
        commercial = get_commercial_answer(kb, plan.query)
        commercial_validation = validate_commercial_answer(commercial)
        if not commercial_validation["valid"]:
            raise ValueError(commercial_validation["errors"])

        commercial_status = commercial["status"]
        fee = commercial["fee"]
        currency = commercial["currency"]
        commercial_source = commercial["source_id"]
        handoff = handoff or commercial["human_handoff_required"]
        answer = _append_commercial_note(answer, commercial)

    if plan.intent == "career":
        answer += (
            "\n\nThe program information does not establish guaranteed "
            "employment, placement, salary, income, or a specific job outcome."
        )

    return OrchestratedAnswer(
        query=plan.query,
        response_status="READY",
        answer=answer,
        intent=plan.intent,
        primary_course_id=primary,
        course_ids=[g.course_id for g in groups],
        source_ids=_unique(
            [sid for g in groups for sid in g.source_ids]
            + ([commercial_source] if commercial_source else [])
        ),
        evidence_groups=groups,
        commercial_status=commercial_status,
        fee=fee,
        currency=currency,
        human_handoff_required=handoff,
        grounded=True,
        safety=safety,
    )


def orchestrate_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> OrchestratedAnswer:
    plan = build_response_plan(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return orchestrate_response(kb, plan)


def orchestrated_answer_to_dict(
    answer: OrchestratedAnswer,
) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "response_status": answer.response_status,
        "answer": answer.answer,
        "intent": answer.intent,
        "primary_course_id": answer.primary_course_id,
        "course_ids": list(answer.course_ids),
        "source_ids": list(answer.source_ids),
        "evidence_groups": [
            {
                "course_id": g.course_id,
                "official_name": g.official_name,
                "category": g.category,
                "evidence": copy.deepcopy(g.evidence),
                "source_ids": list(g.source_ids),
                "best_score": g.best_score,
            }
            for g in answer.evidence_groups
        ],
        "commercial_status": answer.commercial_status,
        "fee": answer.fee,
        "currency": answer.currency,
        "human_handoff_required": answer.human_handoff_required,
        "grounded": answer.grounded,
        "safety": copy.deepcopy(answer.safety),
    }


def validate_orchestrated_answer(
    answer: OrchestratedAnswer,
) -> Dict[str, Any]:
    errors = []

    if answer.response_status not in {"READY", "NO_MATCH"}:
        errors.append("Invalid response_status.")

    if answer.response_status == "READY":
        if not answer.grounded:
            errors.append("READY answer must be grounded.")
        if not answer.answer.strip():
            errors.append("READY answer cannot be empty.")
        if not answer.evidence_groups:
            errors.append("READY answer requires evidence groups.")
        if answer.primary_course_id not in answer.course_ids:
            errors.append("Primary course must belong to course_ids.")

    if answer.response_status == "NO_MATCH":
        if answer.grounded:
            errors.append("NO_MATCH answer cannot be grounded.")
        if answer.evidence_groups:
            errors.append("NO_MATCH answer cannot contain evidence groups.")
        if answer.fee is not None:
            errors.append("NO_MATCH answer cannot contain a fee.")

    expected_courses = [g.course_id for g in answer.evidence_groups]
    if expected_courses != answer.course_ids:
        errors.append("Course IDs do not match evidence groups.")

    expected_sources = _unique(
        sid for g in answer.evidence_groups for sid in g.source_ids
    )
    if answer.commercial_status is not None and COMMERCIAL_SOURCE_ID in answer.source_ids:
        expected_sources.append(COMMERCIAL_SOURCE_ID)
        expected_sources = _unique(expected_sources)

    if expected_sources != answer.source_ids:
        errors.append("Source IDs do not match evidence/commercial provenance.")

    if answer.commercial_status == "VERIFIED_INDIA_FEE":
        if answer.fee is None:
            errors.append("Verified Indian answer must contain fee.")
        if answer.currency != "INR":
            errors.append("Verified Indian answer must use INR.")
        if COMMERCIAL_SOURCE_ID not in answer.source_ids:
            errors.append("Commercial source ID missing.")

    if answer.commercial_status == "INTERNATIONAL_UNDEFINED":
        if answer.fee is not None:
            errors.append("International fee must remain undefined.")
        if answer.currency is not None:
            errors.append("International currency must remain undefined.")
        if "Indian pricing must not be substituted" not in answer.answer:
            errors.append("International no-India-fallback missing.")

    if answer.commercial_status == "REGION_REQUIRED":
        if answer.fee is not None:
            errors.append("Unknown region must not receive a fee.")

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


def build_master_kb_with_orchestrator() -> Any:
    # Imported lazily to keep this module's dependency boundary explicit.
    from Sayyed_EdVantage_Master_KB_BATCH22 import (
        build_master_kb_with_commercial_knowledge,
    )
    return build_master_kb_with_commercial_knowledge()


# Downstream aliases.
build_orchestrated_answer = orchestrate_response
answer_query_orchestrated = orchestrate_query


if __name__ == "__main__":
    kb = build_master_kb_with_orchestrator()
    result = orchestrate_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 24 validation:", validate_orchestrated_answer(result))
    print(result.answer)
