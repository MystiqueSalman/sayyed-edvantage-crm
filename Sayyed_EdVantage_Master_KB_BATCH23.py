"""
Sayyed EdVantage AI Agent — Master KB Batch 23
Commercial-Aware Grounded Answer Integration

Purpose:
- Integrate Batch 22 verified commercial knowledge into the Batch 20 answer layer.
- Quote verified Indian base fees when the region is explicitly/clearly Indian.
- Never quote Indian pricing to international students.
- Never invent final fees, GST amounts, discounts, payment plans, or enrollment terms.
- Preserve course and commercial provenance.
- Keep execution, messaging, external actions, and CRM writes disabled.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH22 import (
    COMMERCIAL_SOURCE_ID,
    build_master_kb_with_commercial_knowledge,
    get_commercial_answer,
    validate_commercial_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH20 import (
    GroundedAnswer,
    generate_grounded_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import (
    ResponsePlan,
    build_response_plan,
    validate_response_plan,
)


@dataclass
class CommercialAwareAnswer:
    query: str
    answer: str
    response_status: str
    course_ids: List[str]
    source_ids: List[str]
    grounded: bool
    commercial_status: Optional[str]
    fee: Optional[int]
    currency: Optional[str]
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


def _is_commercial_query(plan: ResponsePlan) -> bool:
    return plan.intent == "commercial"


def _commercial_context_for_plan(
    kb: Any,
    plan: ResponsePlan,
) -> Dict[str, Any]:
    if not _is_commercial_query(plan):
        return {
            "status": None,
            "fee": None,
            "currency": None,
            "source_id": None,
            "message": None,
            "human_handoff_required": False,
        }

    result = get_commercial_answer(kb, plan.query)
    validation = validate_commercial_answer(result)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    return result


def generate_commercial_aware_answer(
    kb: Any,
    plan: ResponsePlan,
) -> CommercialAwareAnswer:
    """
    Generate a grounded answer with verified commercial information when
    applicable.

    Non-commercial queries are delegated to the existing Batch 20 grounded
    generator. Commercial queries receive a verified commercial layer result.
    """
    validation = validate_response_plan(plan)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    safety = copy.deepcopy(plan.safety_policy)

    if plan.response_status == "NO_MATCH":
        return CommercialAwareAnswer(
            query=plan.query,
            answer=(
                "I couldn't find sufficiently grounded information for that "
                "request in the current Sayyed EdVantage Master Knowledge Base. "
                "I don't want to guess or invent the missing details."
            ),
            response_status="NO_MATCH",
            course_ids=[],
            source_ids=[],
            grounded=False,
            commercial_status=None,
            fee=None,
            currency=None,
            human_handoff_required=True,
            safety=safety,
        )

    if not _is_commercial_query(plan):
        generic = generate_grounded_answer(plan)
        return CommercialAwareAnswer(
            query=generic.query,
            answer=generic.answer,
            response_status=generic.response_status,
            course_ids=list(generic.course_ids),
            source_ids=list(generic.source_ids),
            grounded=generic.grounded,
            commercial_status=None,
            fee=None,
            currency=None,
            human_handoff_required=generic.human_handoff_required,
            safety=copy.deepcopy(generic.safety),
        )

    commercial = _commercial_context_for_plan(kb, plan)

    if commercial["status"] == "VERIFIED_INDIA_FEE":
        # A verified commercial source must be added to provenance without
        # replacing the course evidence.
        source_ids = _unique(
            list(plan.source_ids) + [COMMERCIAL_SOURCE_ID]
        )

        answer = (
            f'Based on the verified Sayyed EdVantage commercial information: '
            f'{commercial["offering"]["name"]}: '
            f'₹{commercial["fee"]:,} + GST.\n\n'
            "Admissions/team confirms the final fee, applicable taxes, "
            "discounts, payment options, and enrollment details."
        )

        return CommercialAwareAnswer(
            query=plan.query,
            answer=answer,
            response_status="READY",
            course_ids=list(plan.course_ids),
            source_ids=source_ids,
            grounded=True,
            commercial_status=commercial["status"],
            fee=commercial["fee"],
            currency=commercial["currency"],
            human_handoff_required=False,
            safety=safety,
        )

    if commercial["status"] == "INTERNATIONAL_UNDEFINED":
        source_ids = _unique(
            list(plan.source_ids) + [COMMERCIAL_SOURCE_ID]
        )
        return CommercialAwareAnswer(
            query=plan.query,
            answer=(
                "International pricing is not currently defined in the "
                "Sayyed EdVantage Master Knowledge Base. Indian pricing must "
                "not be substituted. Admissions/team should provide the "
                "applicable fee and enrollment details."
            ),
            response_status="READY",
            course_ids=list(plan.course_ids),
            source_ids=source_ids,
            grounded=True,
            commercial_status=commercial["status"],
            fee=None,
            currency=None,
            human_handoff_required=True,
            safety=safety,
        )

    if commercial["status"] == "REGION_REQUIRED":
        return CommercialAwareAnswer(
            query=plan.query,
            answer=(
                "Please confirm the student's pricing region before quoting "
                "a course fee."
            ),
            response_status="READY",
            course_ids=list(plan.course_ids),
            source_ids=list(plan.source_ids),
            grounded=True,
            commercial_status=commercial["status"],
            fee=None,
            currency=None,
            human_handoff_required=False,
            safety=safety,
        )

    # OFFERING_NOT_FOUND
    source_ids = _unique(
        list(plan.source_ids) + [COMMERCIAL_SOURCE_ID]
    )
    return CommercialAwareAnswer(
        query=plan.query,
        answer=commercial["message"],
        response_status="READY",
        course_ids=list(plan.course_ids),
        source_ids=source_ids,
        grounded=True,
        commercial_status=commercial["status"],
        fee=None,
        currency=None,
        human_handoff_required=True,
        safety=safety,
    )


def answer_commercial_aware_query(
    kb: Any,
    query: str,
    top_k: int = 5,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> CommercialAwareAnswer:
    plan = build_response_plan(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return generate_commercial_aware_answer(kb, plan)


def validate_commercial_aware_answer(
    answer: CommercialAwareAnswer,
) -> Dict[str, Any]:
    errors = []

    if answer.response_status not in {"READY", "NO_MATCH"}:
        errors.append("Invalid response_status.")

    if answer.response_status == "READY":
        if not answer.grounded:
            errors.append("READY commercial-aware answer must be grounded.")
        if not answer.answer.strip():
            errors.append("READY answer cannot be empty.")

    if answer.response_status == "NO_MATCH":
        if answer.grounded:
            errors.append("NO_MATCH answer cannot be grounded.")
        if answer.fee is not None:
            errors.append("NO_MATCH cannot contain a fee.")

    if answer.commercial_status == "VERIFIED_INDIA_FEE":
        if answer.fee is None:
            errors.append("Verified Indian fee cannot be None.")
        if answer.currency != "INR":
            errors.append("Verified Indian fee must use INR.")
        if COMMERCIAL_SOURCE_ID not in answer.source_ids:
            errors.append("Commercial provenance missing.")

    if answer.commercial_status == "INTERNATIONAL_UNDEFINED":
        if answer.fee is not None:
            errors.append("International fee must remain undefined.")
        if answer.currency is not None:
            errors.append("International currency must remain undefined.")
        if answer.human_handoff_required is not True:
            errors.append("International fee must require handoff.")
        if "Indian pricing must not be substituted" not in answer.answer:
            errors.append("International no-India-fallback wording missing.")

    if answer.commercial_status == "REGION_REQUIRED":
        if answer.fee is not None:
            errors.append("Fee cannot be quoted before region is known.")

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


def commercial_aware_answer_to_dict(
    answer: CommercialAwareAnswer,
) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "answer": answer.answer,
        "response_status": answer.response_status,
        "course_ids": list(answer.course_ids),
        "source_ids": list(answer.source_ids),
        "grounded": answer.grounded,
        "commercial_status": answer.commercial_status,
        "fee": answer.fee,
        "currency": answer.currency,
        "human_handoff_required": answer.human_handoff_required,
        "safety": copy.deepcopy(answer.safety),
    }


def build_master_kb_with_commercial_answering() -> Any:
    return build_master_kb_with_commercial_knowledge()


# Explicit aliases for downstream AI Brain integration.
generate_commercial_answer = generate_commercial_aware_answer
answer_query_with_commercials = answer_commercial_aware_query


if __name__ == "__main__":
    kb = build_master_kb_with_commercial_answering()
    result = answer_commercial_aware_query(
        kb,
        "What is the fee for Data Science in India?",
    )
    print("Batch 23 validation:", validate_commercial_aware_answer(result))
    print(result.answer)
