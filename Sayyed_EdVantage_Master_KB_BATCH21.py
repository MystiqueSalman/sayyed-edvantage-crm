"""
Sayyed EdVantage AI Agent — Master KB Batch 21
Multi-Course Answer Composition & Evidence Selection

Purpose:
- Safely compose answers when a query matches more than one course/evidence group.
- Prefer the most relevant course while preserving distinct course boundaries.
- Prevent unrelated course facts from being merged.
- Preserve source IDs and provenance.
- Keep all execution/action/message/CRM-write capabilities disabled.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_Master_KB_BATCH20 import (
    GroundedAnswer,
    answer_query,
    build_master_kb_with_answer_generator,
    generate_grounded_answer,
    validate_grounded_answer,
)
from Sayyed_EdVantage_Master_KB_BATCH19 import (
    ResponsePlan,
    build_response_plan,
    validate_response_plan,
)


@dataclass
class CourseEvidenceGroup:
    course_id: str
    official_name: str
    category: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    best_score: float = 0.0


@dataclass
class MultiCourseAnswer:
    query: str
    response_status: str
    answer: str
    primary_course_id: Optional[str]
    course_ids: List[str]
    source_ids: List[str]
    evidence_groups: List[CourseEvidenceGroup]
    grounded: bool
    human_handoff_required: bool
    safety: Dict[str, Any]


def _unique(values: List[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def group_response_plan_by_course(plan: ResponsePlan) -> List[CourseEvidenceGroup]:
    """
    Group evidence by course without merging the underlying evidence text.
    """
    groups: Dict[str, CourseEvidenceGroup] = {}

    for evidence in plan.evidence:
        cid = evidence.course_id

        if cid not in groups:
            groups[cid] = CourseEvidenceGroup(
                course_id=cid,
                official_name=evidence.official_name,
                category=evidence.category,
            )

        group = groups[cid]
        group.evidence.append({
            "path": evidence.path,
            "text": evidence.text,
            "score": evidence.score,
            "source_ids": list(evidence.source_ids),
            "provenance": copy.deepcopy(evidence.provenance),
        })
        group.source_ids.extend(evidence.source_ids)
        group.best_score = max(group.best_score, float(evidence.score))

    output = list(groups.values())

    for group in output:
        group.source_ids = _unique(group.source_ids)

    output.sort(key=lambda g: (-g.best_score, g.course_id))
    return output


def select_primary_course(
    groups: List[CourseEvidenceGroup],
) -> Optional[str]:
    """
    Select the strongest course group deterministically.

    Ties are resolved by course_id so behavior remains reproducible.
    """
    if not groups:
        return None

    ranked = sorted(groups, key=lambda g: (-g.best_score, g.course_id))
    return ranked[0].course_id


def validate_course_groups(
    groups: List[CourseEvidenceGroup],
) -> Dict[str, Any]:
    errors = []

    seen = set()

    for group in groups:
        if group.course_id in seen:
            errors.append(f"Duplicate course group: {group.course_id}")
        seen.add(group.course_id)

        if not group.official_name:
            errors.append(f"{group.course_id}: missing official_name")

        if not group.evidence:
            errors.append(f"{group.course_id}: empty evidence group")

        for item in group.evidence:
            provenance = item.get("provenance", {})
            if provenance.get("course_id") != group.course_id:
                errors.append(
                    f"{group.course_id}: evidence provenance mismatch"
                )

    return {"valid": not errors, "errors": errors}


def compose_multi_course_answer(
    plan: ResponsePlan,
) -> MultiCourseAnswer:
    """
    Produce an answer that keeps course-specific evidence visibly separated.

    For a single course, this remains a normal grounded answer.
    For multiple courses, each course gets its own evidence section.
    """
    response_validation = validate_response_plan(plan)
    if not response_validation["valid"]:
        raise ValueError(response_validation["errors"])

    if plan.response_status == "NO_MATCH":
        return MultiCourseAnswer(
            query=plan.query,
            response_status="NO_MATCH",
            answer=(
                "I couldn't find sufficiently grounded information for that "
                "request in the current Sayyed EdVantage Master Knowledge Base. "
                "I don't want to guess or merge unrelated course information."
            ),
            primary_course_id=None,
            course_ids=[],
            source_ids=[],
            evidence_groups=[],
            grounded=False,
            human_handoff_required=True,
            safety=copy.deepcopy(plan.safety_policy),
        )

    groups = group_response_plan_by_course(plan)
    group_validation = validate_course_groups(groups)
    if not group_validation["valid"]:
        raise ValueError(group_validation["errors"])

    primary = select_primary_course(groups)

    parts = [
        "Based on the Sayyed EdVantage Master Knowledge Base:"
    ]

    for group in groups:
        parts.append(f"### {group.official_name}")
        for item in group.evidence:
            text = " ".join(str(item["text"]).split()).strip()
            if text:
                parts.append(f"• {text}")

    # Preserve policy-required safeguards from Batch 19/20.
    if plan.intent == "career":
        parts.append(
            "The program information does not establish guaranteed employment, "
            "placement, salary, income, or a specific job outcome."
        )

    if plan.human_handoff_required:
        parts.append(
            "Admissions/team can confirm details that are not defined in the "
            "current Master KB."
        )

    answer = "\n\n".join(parts)

    course_ids = [g.course_id for g in groups]
    source_ids = _unique(
        sid for group in groups for sid in group.source_ids
    )

    return MultiCourseAnswer(
        query=plan.query,
        response_status="READY",
        answer=answer,
        primary_course_id=primary,
        course_ids=course_ids,
        source_ids=source_ids,
        evidence_groups=groups,
        grounded=True,
        human_handoff_required=plan.human_handoff_required,
        safety=copy.deepcopy(plan.safety_policy),
    )


def answer_multi_course_query(
    kb: Any,
    query: str,
    top_k: int = 10,
    course_id: Optional[str] = None,
    category: Optional[str] = None,
) -> MultiCourseAnswer:
    plan = build_response_plan(
        kb,
        query,
        top_k=top_k,
        course_id=course_id,
        category=category,
    )
    return compose_multi_course_answer(plan)


def multi_course_answer_to_dict(
    answer: MultiCourseAnswer,
) -> Dict[str, Any]:
    return {
        "query": answer.query,
        "response_status": answer.response_status,
        "answer": answer.answer,
        "primary_course_id": answer.primary_course_id,
        "course_ids": list(answer.course_ids),
        "source_ids": list(answer.source_ids),
        "evidence_groups": [
            {
                "course_id": group.course_id,
                "official_name": group.official_name,
                "category": group.category,
                "evidence": copy.deepcopy(group.evidence),
                "source_ids": list(group.source_ids),
                "best_score": group.best_score,
            }
            for group in answer.evidence_groups
        ],
        "grounded": answer.grounded,
        "human_handoff_required": answer.human_handoff_required,
        "safety": copy.deepcopy(answer.safety),
    }


def validate_multi_course_answer(
    answer: MultiCourseAnswer,
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

    if answer.response_status == "NO_MATCH":
        if answer.grounded:
            errors.append("NO_MATCH answer cannot be grounded.")
        if answer.evidence_groups:
            errors.append("NO_MATCH answer cannot contain evidence groups.")
        if answer.primary_course_id is not None:
            errors.append("NO_MATCH cannot have a primary course.")

    expected_courses = [g.course_id for g in answer.evidence_groups]
    if expected_courses != answer.course_ids:
        errors.append("course_ids do not match evidence groups.")

    expected_sources = _unique(
        sid
        for group in answer.evidence_groups
        for sid in group.source_ids
    )
    if expected_sources != answer.source_ids:
        errors.append("source_ids do not match evidence groups.")

    if answer.response_status == "READY":
        if answer.primary_course_id not in answer.course_ids:
            errors.append("Primary course must belong to course_ids.")

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


def build_master_kb_with_multi_course_answers() -> Any:
    return build_master_kb_with_answer_generator()


# Explicit downstream aliases.
group_evidence_by_course = group_response_plan_by_course
build_multi_course_answer = compose_multi_course_answer


if __name__ == "__main__":
    kb = build_master_kb_with_multi_course_answers()
    answer = answer_multi_course_query(kb, "Python programming", top_k=5)
    print("Batch 21 validation:", validate_multi_course_answer(answer))
    print(answer.answer)
