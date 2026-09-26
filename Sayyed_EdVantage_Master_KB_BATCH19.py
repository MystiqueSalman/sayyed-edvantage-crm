"""
Sayyed EdVantage AI Agent — Master KB Batch 19
Answer Policy & Response Composition Layer

Purpose:
- Convert Batch 18 answer context into a deterministic response plan.
- Keep responses grounded in retrieved evidence.
- Apply no-invention, missing-information, commercial-region, and safety policies.
- Separate evidence from composition instructions.
- Do NOT send messages, execute actions, write CRM data, or perform external actions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH18 import (
    AnswerContext,
    build_master_kb_with_answer_context,
    build_answer_context,
    validate_answer_context,
)


@dataclass
class ResponseEvidence:
    course_id: str
    official_name: str
    category: str
    path: str
    text: str
    score: float
    source_ids: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponsePlan:
    query: str
    response_status: str
    intent: str
    evidence: List[ResponseEvidence] = field(default_factory=list)
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    commercial_policy: Dict[str, Any] = field(default_factory=dict)
    safety_policy: Dict[str, Any] = field(default_factory=dict)
    human_handoff_required: bool = False


def _unique(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def classify_intent(query: str) -> str:
    """
    Lightweight deterministic intent classification.

    This is a routing hint, not an answer. It deliberately avoids
    pretending to understand unsupported user intent.
    """
    q = (query or "").lower()

    if any(x in q for x in (
        "fee", "fees", "price", "pricing", "cost", "payment",
        "discount", "emi", "gst", "tax"
    )):
        return "commercial"
    if any(x in q for x in (
        "eligibility", "eligible", "qualification", "prerequisite",
        "prerequisites", "requirement", "requirements"
    )):
        return "eligibility"
    if any(x in q for x in (
        "duration", "hours", "how long", "modules", "curriculum",
        "syllabus", "topics"
    )):
        return "program_information"
    if any(x in q for x in (
        "certificate", "certification"
    )):
        return "certification"
    if any(x in q for x in (
        "job", "career", "placement", "salary", "income", "employment"
    )):
        return "career"
    if any(x in q for x in (
        "project", "capstone", "assessment", "exam", "evaluation"
    )):
        return "assessment_projects"
    if any(x in q for x in (
        "tool", "tools", "software", "technology", "technologies"
    )):
        return "tools"
    return "general_information"


def _commercial_instructions(query: str) -> List[str]:
    q = (query or "").lower()
    instructions = [
        "Use only verified region-specific commercial information.",
        "Do not invent discounts, payment plans, taxes, or final enrollment amounts.",
    ]

    # Region handling is deliberately conservative. The downstream agent
    # must know the student's region before quoting a regional price.
    if any(x in q for x in ("international", "outside india", "overseas", "abroad")):
        instructions.append(
            "Do not quote Indian pricing for an international student; "
            "international pricing is not currently defined."
        )
        instructions.append(
            "At fee/details stage, hand the matter to admissions/team."
        )
    elif any(x in q for x in ("india", "indian", "inr", "₹", "rs", "rupees")):
        instructions.append(
            "Indian pricing may be quoted only from the verified Indian fee source."
        )
    else:
        instructions.append(
            "Determine/confirm the student's pricing region before quoting a fee."
        )

    return instructions


def compose_response_plan(context: AnswerContext) -> ResponsePlan:
    """
    Build a response plan from grounded context.

    No prose answer is generated here. The plan tells a later response
    generator what evidence and policies it may use.
    """
    validation = validate_answer_context(context)
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    intent = classify_intent(context.query)

    if not context.matched:
        return ResponsePlan(
            query=context.query,
            response_status="NO_MATCH",
            intent=intent,
            evidence=[],
            course_ids=[],
            source_ids=[],
            instructions=[
                "State that the Master KB does not contain a sufficiently grounded match.",
                "Do not guess or fill the missing information from general knowledge.",
                "Offer admissions/faculty handoff when appropriate.",
            ],
            unknowns=["The requested information is not sufficiently grounded in the retrieved Master KB context."],
            commercial_policy=copy.deepcopy(context.policies),
            safety_policy=copy.deepcopy(context.safety),
            human_handoff_required=True,
        )

    evidence = [
        ResponseEvidence(
            course_id=item.course_id,
            official_name=item.official_name,
            category=item.category,
            path=item.path,
            text=item.text,
            score=item.score,
            source_ids=list(item.source_ids),
            provenance=copy.deepcopy(item.provenance),
        )
        for item in context.items
    ]

    instructions = [
        "Answer only from the supplied Master KB evidence and policies.",
        "Preserve official course terminology where applicable.",
        "Do not invent missing facts, guarantees, dates, outcomes, certifications, or commercial terms.",
        "If evidence is insufficient for a requested detail, state that it is unspecified/unknown.",
        "Keep course information isolated to the retrieved course records.",
        "Preserve source provenance for grounded claims.",
    ]

    unknowns = []

    if intent == "commercial":
        instructions.extend(_commercial_instructions(context.query))
        unknowns.append(
            "Final fee, taxes, discounts, payment plans, and enrollment terms "
            "must not be invented unless explicitly present in verified evidence."
        )

    if intent == "certification":
        instructions.append(
            "Certification status must be reported as unspecified/unknown where "
            "the Master KB does not provide a verified certification."
        )
        unknowns.append("Certification details are not verified in the current Master KB.")

    if intent == "career":
        instructions.append(
            "Do not promise employment, placement, salary, income, or a specific job outcome."
        )

    # Duration inconsistencies are preserved rather than silently reconciled.
    if any("documented_source_inconsistency" in item.text for item in evidence):
        instructions.append(
            "Preserve documented duration inconsistencies; do not rebalance or invent hours."
        )
        unknowns.append(
            "A retrieved source contains a documented duration inconsistency."
        )

    handoff = False
    if intent == "commercial" and any(
        x in context.query.lower()
        for x in ("international", "outside india", "overseas", "abroad")
    ):
        handoff = True

    return ResponsePlan(
        query=context.query,
        response_status="READY",
        intent=intent,
        evidence=evidence,
        course_ids=list(context.course_ids),
        source_ids=list(context.source_ids),
        instructions=_unique(instructions),
        unknowns=_unique(unknowns),
        commercial_policy=copy.deepcopy(context.policies),
        safety_policy=copy.deepcopy(context.safety),
        human_handoff_required=handoff,
    )


def response_plan_to_dict(plan: ResponsePlan) -> Dict[str, Any]:
    return {
        "query": plan.query,
        "response_status": plan.response_status,
        "intent": plan.intent,
        "evidence": [
            {
                "course_id": e.course_id,
                "official_name": e.official_name,
                "category": e.category,
                "path": e.path,
                "text": e.text,
                "score": e.score,
                "source_ids": list(e.source_ids),
                "provenance": copy.deepcopy(e.provenance),
            }
            for e in plan.evidence
        ],
        "course_ids": list(plan.course_ids),
        "source_ids": list(plan.source_ids),
        "instructions": list(plan.instructions),
        "unknowns": list(plan.unknowns),
        "commercial_policy": copy.deepcopy(plan.commercial_policy),
        "safety_policy": copy.deepcopy(plan.safety_policy),
        "human_handoff_required": plan.human_handoff_required,
    }


def validate_response_plan(plan: ResponsePlan) -> Dict[str, Any]:
    errors = []

    if plan.response_status not in {"READY", "NO_MATCH"}:
        errors.append("Invalid response_status.")

    if plan.response_status == "READY" and not plan.evidence:
        errors.append("READY response plan requires evidence.")

    if plan.response_status == "NO_MATCH" and plan.evidence:
        errors.append("NO_MATCH response plan must not contain evidence.")

    expected_courses = _unique([e.course_id for e in plan.evidence])
    if expected_courses != plan.course_ids:
        errors.append("course_ids do not match evidence.")

    expected_sources = _unique(
        [sid for e in plan.evidence for sid in e.source_ids]
    )
    if expected_sources != plan.source_ids:
        errors.append("source_ids do not match evidence.")

    for evidence in plan.evidence:
        if evidence.provenance.get("course_id") != evidence.course_id:
            errors.append(
                f"Evidence provenance mismatch for {evidence.course_id}."
            )

    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if plan.safety_policy.get(key) is not False:
            errors.append(f"Safety invariant violated: {key} must be False.")

    if plan.safety_policy.get("no_invention") is not True:
        errors.append("No-invention policy must be True.")

    return {"valid": not errors, "errors": errors}


def build_master_kb_with_response_policy() -> Any:
    return build_master_kb_with_answer_context()


def build_response_plan(
    kb: Any,
    query: str,
    top_k: int = 5,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> ResponsePlan:
    context = build_answer_context(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return compose_response_plan(context)


# Explicit downstream aliases.
build_answer_response_plan = compose_response_plan
serialize_response_plan = response_plan_to_dict


if __name__ == "__main__":
    kb = build_master_kb_with_response_policy()
    plan = build_response_plan(kb, "Python programming", top_k=3)
    print("Batch 19 validation:", validate_response_plan(plan))
    print("Status:", plan.response_status)
    print("Intent:", plan.intent)
    print("Courses:", plan.course_ids)
