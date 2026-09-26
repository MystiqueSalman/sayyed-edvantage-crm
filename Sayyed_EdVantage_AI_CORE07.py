"""
Sayyed EdVantage AI Agent — AI Core 07
Student Intent, Need & Recommendation Evidence Synthesis

Purpose:
- Synthesize verified prospect-profile and conversation evidence into a
  structured admissions-need summary.
- Separate explicit facts from unknowns.
- Identify stated goals, experience level, technical background, region,
  and current role without inventing missing information.
- Produce course-selection signals only from explicit course evidence or
  established context.
- Provide clarification questions when recommendation evidence is weak.
- No CRM writes, messaging, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_AI_CORE05 import (
    ProspectProfile,
    FIELD_NAMES,
    validate_prospect_profile,
)
from Sayyed_EdVantage_AI_CORE04 import (
    CourseCandidate,
    RecommendationResult,
    recommend_courses,
)


NEED_READY = "NEED_READY"
NEED_CLARIFICATION = "NEED_CLARIFICATION"
NEED_UNKNOWN = "NEED_UNKNOWN"


@dataclass
class NeedSignal:
    field: str
    value: Optional[str]
    status: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class StudentNeedProfile:
    session_id: str
    stated_goal: Optional[str] = None
    experience_level: Optional[str] = None
    technical_background: Optional[str] = None
    current_role: Optional[str] = None
    education: Optional[str] = None
    region: Optional[str] = None
    budget: Optional[str] = None
    course_ids: List[str] = field(default_factory=list)
    intent: str = ""
    signals: List[NeedSignal] = field(default_factory=list)
    unknown_fields: List[str] = field(default_factory=list)
    status: str = NEED_UNKNOWN
    clarification_questions: List[str] = field(default_factory=list)
    no_invention: bool = True


def _unique(values):
    return list(dict.fromkeys(values))


def _known(profile: ProspectProfile, name: str):
    value = getattr(profile, name)
    return value.value if value.status == "known" else None


def synthesize_student_need(
    profile: ProspectProfile,
    intent: str = "",
    course_ids: Optional[List[str]] = None,
) -> StudentNeedProfile:
    validation = validate_prospect_profile(profile)
    if not validation["valid"]:
        return StudentNeedProfile(
            session_id=profile.session_id,
            status=NEED_CLARIFICATION,
            clarification_questions=[
                "Please provide the missing or conflicting student information."
            ],
            no_invention=True,
        )

    ids = _unique(course_ids or [])

    # Treat either explicitly stated learning_goal or career_goal as the
    # student's stated goal. Prefer learning_goal when both are present;
    # never infer one from the other.
    learning_goal = _known(profile, "learning_goal")
    career_goal = _known(profile, "career_goal")
    stated_goal = learning_goal if learning_goal is not None else career_goal

    result = StudentNeedProfile(
        session_id=profile.session_id,
        stated_goal=stated_goal,
        experience_level=_known(profile, "experience"),
        technical_background=_known(profile, "technical_background"),
        current_role=_known(profile, "current_role"),
        education=_known(profile, "education"),
        region=_known(profile, "region"),
        budget=_known(profile, "budget"),
        course_ids=ids,
        intent=intent,
    )

    for name in FIELD_NAMES:
        f = getattr(profile, name)
        if f.status == "known":
            result.signals.append(
                NeedSignal(
                    field=name,
                    value=f.value,
                    status="explicit",
                    evidence=list(f.evidence),
                )
            )
        else:
            result.unknown_fields.append(name)

    if result.stated_goal or result.course_ids or result.experience_level:
        result.status = NEED_READY
    else:
        result.status = NEED_UNKNOWN

    questions = []
    if not result.stated_goal:
        questions.append(
            "What is your main learning or career goal?"
        )
    if not result.experience_level:
        questions.append(
            "Are you a fresher, student, or working professional, and "
            "what experience do you have?"
        )

    result.clarification_questions = questions
    if questions and result.status != NEED_UNKNOWN:
        result.status = NEED_CLARIFICATION

    return result


def synthesize_need_from_recommendation(
    profile: ProspectProfile,
    recommendation: RecommendationResult,
    intent: str = "",
) -> StudentNeedProfile:
    ids = [c.course_id for c in recommendation.candidates]

    # Preserve the explicit course order from the student's message when
    # multiple candidates are present. Core 04 may rank equal-score
    # candidates deterministically by course ID, but Core 07 must not turn
    # that ranking artifact into a different conversational order.
    message_lower = str(recommendation.user_message).lower()
    candidate_names = {
        c.course_id: str(c.official_name).lower()
        for c in recommendation.candidates
    }
    if len(ids) > 1:
        positions = {
            course_id: message_lower.find(name)
            for course_id, name in candidate_names.items()
        }
        if all(position >= 0 for position in positions.values()):
            ids = sorted(ids, key=lambda course_id: positions[course_id])

    # Only a primary course explicitly selected or safely carried by context
    # becomes a primary need signal. Candidate lists remain separate.
    if recommendation.primary_course_id:
        ids = _unique([recommendation.primary_course_id] + ids)

    need = synthesize_student_need(profile, intent=intent, course_ids=ids)

    if recommendation.clarification_needed:
        need.clarification_questions.append(
            "Which course or course area are you most interested in?"
        )
        need.clarification_questions = _unique(
            need.clarification_questions
        )
        if need.status == NEED_READY:
            need.status = NEED_CLARIFICATION

    return need


def build_need_profile(
    profile: ProspectProfile,
    message: str = "",
    context: Any = None,
    kb: Any = None,
) -> StudentNeedProfile:
    """
    Convenience API.

    If KB and a message are supplied, recommendation evidence is derived
    through the existing recommendation layer. Otherwise only profile facts
    are synthesized.
    """
    if kb is not None and message:
        recommendation = recommend_courses(kb, message, context)
        return synthesize_need_from_recommendation(
            profile,
            recommendation,
            intent="",
        )
    return synthesize_student_need(profile)


def validate_need_profile(
    need: StudentNeedProfile,
) -> Dict[str, Any]:
    errors = []

    if not need.session_id.strip():
        errors.append("Need profile session ID cannot be empty.")

    if need.status not in {
        NEED_READY,
        NEED_CLARIFICATION,
        NEED_UNKNOWN,
    }:
        errors.append("Invalid need profile status.")

    if need.no_invention is not True:
        errors.append("Need profile no_invention must be True.")

    if len(need.course_ids) != len(set(need.course_ids)):
        errors.append("Duplicate course IDs are not allowed.")

    signal_fields = [s.field for s in need.signals]
    if len(signal_fields) != len(set(signal_fields)):
        errors.append("Duplicate need signals are not allowed.")

    for signal in need.signals:
        if signal.field not in FIELD_NAMES:
            errors.append(f"Unsupported need signal field: {signal.field}.")
        if signal.status != "explicit":
            errors.append(
                f"Need signal {signal.field} must be explicitly sourced."
            )
        if signal.value is None:
            errors.append(
                f"Explicit need signal {signal.field} requires a value."
            )
        if not signal.evidence:
            errors.append(
                f"Explicit need signal {signal.field} requires evidence."
            )

    # A need field is "known" for validation only when that exact profile
    # field produced an explicit signal.  In particular, career_goal may be
    # used as the displayed stated_goal fallback, but that must NOT make an
    # otherwise-unknown learning_goal appear known.
    known_fields = {
        signal.field
        for signal in need.signals
        if signal.status == "explicit" and signal.value is not None
    }
    for name in FIELD_NAMES:
        if name in need.unknown_fields and name in known_fields:
            errors.append(f"Field {name} cannot be both known and unknown.")

    if need.status == NEED_CLARIFICATION and not need.clarification_questions:
        errors.append("Clarification status requires questions.")

    return {"valid": not errors, "errors": _unique(errors)}


def need_profile_to_dict(
    need: StudentNeedProfile,
) -> Dict[str, Any]:
    return {
        "session_id": need.session_id,
        "stated_goal": need.stated_goal,
        "experience_level": need.experience_level,
        "technical_background": need.technical_background,
        "current_role": need.current_role,
        "education": need.education,
        "region": need.region,
        "budget": need.budget,
        "course_ids": list(need.course_ids),
        "intent": need.intent,
        "signals": [
            {
                "field": s.field,
                "value": s.value,
                "status": s.status,
                "evidence": list(s.evidence),
            }
            for s in need.signals
        ],
        "unknown_fields": list(need.unknown_fields),
        "status": need.status,
        "clarification_questions": list(need.clarification_questions),
        "no_invention": need.no_invention,
    }


def build_need_synthesis_layer() -> Any:
    from Sayyed_EdVantage_AI_CORE06 import build_eligibility_layer
    return build_eligibility_layer()
