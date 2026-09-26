"""
Sayyed EdVantage AI Agent — Master KB Batch 18
Unified Answer Context Builder

Purpose:
- Transform Batch 17 retrieval results into a structured, answer-ready context.
- Preserve retrieved wording, course isolation, provenance, and source IDs.
- Keep unknown/missing information explicit.
- Never invent facts, fees, certifications, outcomes, or course details.
- Execution, messaging, external actions, and CRM writes remain disabled.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH17 import (
    MasterKnowledgeBase,
    build_master_kb_with_all_course_retrieval,
    retrieve,
)


@dataclass
class ContextItem:
    course_id: str
    official_name: str
    category: str
    path: str
    text: str
    score: float
    source_ids: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnswerContext:
    query: str
    matched: bool
    items: List[ContextItem] = field(default_factory=list)
    course_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    safety: Dict[str, Any] = field(default_factory=dict)
    policies: Dict[str, Any] = field(default_factory=dict)
    no_match_reason: Optional[str] = None


def _unique(values: List[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _validate_retrieval_result(result: Dict[str, Any]) -> bool:
    required = {
        "course_id",
        "official_name",
        "category",
        "path",
        "text",
        "score",
        "source_ids",
        "provenance",
    }
    return required.issubset(result.keys())


def build_answer_context(
    kb: MasterKnowledgeBase,
    query: str,
    top_k: int = 5,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> AnswerContext:
    """
    Retrieve and convert results into an answer-ready, source-grounded context.

    Important:
    - This function does not generate an answer.
    - It only packages retrieved evidence.
    - Empty retrieval produces an explicit safe no-match state.
    """
    results = retrieve(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )

    valid_results = [r for r in results if _validate_retrieval_result(r)]

    safety = {
        "execution_enabled": kb.get_common_knowledge("execution_enabled", False),
        "messaging_enabled": kb.get_common_knowledge("messaging_enabled", False),
        "external_actions_enabled": kb.get_common_knowledge(
            "external_actions_enabled", False
        ),
        "crm_writes_enabled": kb.get_common_knowledge("crm_writes_enabled", False),
        "no_invention": kb.get_common_knowledge("no_invention", True),
        "provenance_required": kb.get_common_knowledge(
            "provenance_required", True
        ),
    }

    policies = {
        "india_pricing": kb.get_common_knowledge("india_pricing"),
        "international_pricing": kb.get_common_knowledge("international_pricing"),
    }

    if not valid_results:
        return AnswerContext(
            query=query,
            matched=False,
            items=[],
            course_ids=[],
            source_ids=[],
            safety=safety,
            policies=policies,
            no_match_reason=(
                "No sufficiently grounded Master KB retrieval result matched "
                "the supplied query and filters."
            ),
        )

    items = []
    for result in valid_results:
        # Defensive copy: the answer context must not expose mutable references
        # back into the retrieval result structure.
        provenance = copy.deepcopy(result["provenance"])
        source_ids = list(result.get("source_ids", []))

        items.append(
            ContextItem(
                course_id=result["course_id"],
                official_name=result["official_name"],
                category=result["category"],
                path=result["path"],
                text=result["text"],
                score=float(result["score"]),
                source_ids=source_ids,
                provenance=provenance,
            )
        )

    course_ids = _unique([item.course_id for item in items])
    source_ids = _unique(
        [source_id for item in items for source_id in item.source_ids]
    )

    return AnswerContext(
        query=query,
        matched=True,
        items=items,
        course_ids=course_ids,
        source_ids=source_ids,
        safety=safety,
        policies=policies,
    )


def context_to_dict(context: AnswerContext) -> Dict[str, Any]:
    """Serialize AnswerContext without changing its meaning."""
    return {
        "query": context.query,
        "matched": context.matched,
        "items": [
            {
                "course_id": item.course_id,
                "official_name": item.official_name,
                "category": item.category,
                "path": item.path,
                "text": item.text,
                "score": item.score,
                "source_ids": list(item.source_ids),
                "provenance": copy.deepcopy(item.provenance),
            }
            for item in context.items
        ],
        "course_ids": list(context.course_ids),
        "source_ids": list(context.source_ids),
        "safety": copy.deepcopy(context.safety),
        "policies": copy.deepcopy(context.policies),
        "no_match_reason": context.no_match_reason,
    }


def get_context_text(context: AnswerContext) -> str:
    """
    Produce a compact evidence block for a downstream answer generator.

    This is intentionally evidence-only. It does not add explanations,
    recommendations, guarantees, or unsupported facts.
    """
    if not context.matched:
        return ""

    lines = []
    for index, item in enumerate(context.items, start=1):
        lines.append(
            f"[Evidence {index}] "
            f"{item.official_name} | course_id={item.course_id} | "
            f"path={item.path} | score={item.score:g}"
        )
        lines.append(f"Source IDs: {', '.join(item.source_ids) or 'NONE'}")
        lines.append(f"Content: {item.text}")
    return "\n".join(lines)


def validate_answer_context(context: AnswerContext) -> Dict[str, Any]:
    """
    Validate that an AnswerContext remains safe and internally consistent.
    """
    errors = []

    if context.matched and not context.items:
        errors.append("matched=True requires at least one context item.")

    if not context.matched and context.items:
        errors.append("matched=False must not contain context items.")

    if context.matched and context.no_match_reason is not None:
        errors.append("Matched context must not contain no_match_reason.")

    expected_courses = _unique([item.course_id for item in context.items])
    if expected_courses != context.course_ids:
        errors.append("course_ids do not match context items.")

    expected_sources = _unique(
        [sid for item in context.items for sid in item.source_ids]
    )
    if expected_sources != context.source_ids:
        errors.append("source_ids do not match context items.")

    for item in context.items:
        if not item.course_id:
            errors.append("Context item has empty course_id.")
        if not item.official_name:
            errors.append("Context item has empty official_name.")
        if not item.text:
            errors.append("Context item has empty text.")
        if not isinstance(item.provenance, dict):
            errors.append("Context item provenance must be a dictionary.")

        if item.provenance.get("course_id") != item.course_id:
            errors.append(
                f"Provenance course mismatch for {item.course_id}."
            )

    # Hard safety invariant.
    for key in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if context.safety.get(key) is not False:
            errors.append(f"Safety invariant violated: {key} must be False.")

    if context.safety.get("no_invention") is not True:
        errors.append("No-invention policy must be True.")

    if context.safety.get("provenance_required") is not True:
        errors.append("Provenance-required policy must be True.")

    return {"valid": not errors, "errors": errors}


def build_master_kb_with_answer_context() -> MasterKnowledgeBase:
    """Batch 18 integration builder."""
    kb = build_master_kb_with_all_course_retrieval()

    validation = kb.validate()
    if not validation["valid"]:
        raise ValueError(validation["errors"])

    return kb


# Backward/explicit aliases for downstream integration.
build_unified_answer_context = build_answer_context
serialize_answer_context = context_to_dict


if __name__ == "__main__":
    kb = build_master_kb_with_answer_context()
    context = build_answer_context(kb, "Python programming", top_k=3)
    print("Batch 18 context validation:", validate_answer_context(context))
    print("Matched:", context.matched)
    print("Courses:", context.course_ids)
    print(get_context_text(context))
