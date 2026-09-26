"""
Sayyed EdVantage AI Agent — AI Core 04
Course Recommendation & Candidate Selection Contract

Purpose:
- Convert an understood admissions query into deterministic course candidates.
- Use only Master KB course records and explicit/contextual evidence.
- Never invent student qualifications, goals, budget, or course facts.
- Preserve multiple candidates when the user has not supplied enough evidence
  to select one.
- Provide a primary candidate only when selection evidence is explicit.
- Keep recommendation separate from commercial quoting and action execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_AI_CORE03 import (
    UnderstandingResult,
    INTENT_RECOMMENDATION,
    INTENT_PROGRAM_INFORMATION,
    INTENT_COMMERCIAL,
    understand_message,
    validate_understanding,
)
from Sayyed_EdVantage_AI_CORE02 import (
    ConversationContext,
    create_conversation_context,
)
from Sayyed_EdVantage_AI_CORE01 import create_session


RECOMMENDATION_READY = "RECOMMENDATION_READY"
RECOMMENDATION_NEEDS_CLARIFICATION = "RECOMMENDATION_NEEDS_CLARIFICATION"
RECOMMENDATION_EXPLICIT = "RECOMMENDATION_EXPLICIT"


@dataclass
class CourseCandidate:
    course_id: str
    official_name: str
    score: int
    reasons: List[str] = field(default_factory=list)


@dataclass
class RecommendationResult:
    user_message: str
    intent: str
    status: str
    primary_course_id: Optional[str]
    candidates: List[CourseCandidate] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_reason: str = ""
    evidence: List[str] = field(default_factory=list)
    no_invention: bool = True


def _unique(values):
    return list(dict.fromkeys(values))


def _course_aliases(course_id):
    aliases = {
        "SE-DS-001": ["data science", "data scientist"],
        "SE-DA-001": ["data analytics", "data analyst"],
        "SE-AIGEN-001": ["ai", "generative ai", "gen ai", "genai"],
        "SE-PY-001": ["python", "python programming"],
        "SE-LINUX-001": ["linux", "linux administration", "linux admin"],
        "SE-DEVOPS-001": ["devops"],
        "SE-EHC-001": [
            "ethical hacking", "cybersecurity", "cyber security"
        ],
    }
    return aliases.get(course_id, [])


def _course_name(kb, course_id):
    course = kb.get_course(course_id)
    return course.official_name if course else course_id


def build_course_candidates(
    kb: Any,
    understanding: UnderstandingResult,
) -> List[CourseCandidate]:
    """
    Build candidates from explicit course evidence first, otherwise from the
    course catalog. No candidate receives a score from invented preferences.
    """
    if understanding.explicit_course_ids:
        ids = list(understanding.explicit_course_ids)
    elif understanding.context_course_ids:
        ids = list(understanding.context_course_ids)
    else:
        ids = [course.course_id for course in kb.list_courses()]

    candidates = []

    for course_id in ids:
        course = kb.get_course(course_id)
        if course is None:
            continue

        score = 100 if course_id in understanding.explicit_course_ids else 80
        reasons = []

        if course_id in understanding.explicit_course_ids:
            reasons.append("course explicitly referenced by the user")
        elif course_id in understanding.context_course_ids:
            reasons.append("course carried from established conversation context")
        else:
            reasons.append("available course in the Master KB")

        candidates.append(
            CourseCandidate(
                course_id=course_id,
                official_name=course.official_name,
                score=score,
                reasons=reasons,
            )
        )

    candidates.sort(key=lambda item: (-item.score, item.course_id))
    return candidates


def recommend_courses(
    kb: Any,
    message: str,
    context: Optional[ConversationContext] = None,
) -> RecommendationResult:
    context = context or create_conversation_context(
        create_session().session_id
    )

    understanding = understand_message(message, context)
    validation = validate_understanding(understanding)

    if not validation["valid"]:
        return RecommendationResult(
            user_message=str(message).strip(),
            intent=understanding.intent,
            status=RECOMMENDATION_NEEDS_CLARIFICATION,
            primary_course_id=None,
            clarification_needed=True,
            clarification_reason="Understanding validation failed.",
            evidence=[],
        )

    candidates = build_course_candidates(kb, understanding)

    # An explicitly named single course is an explicit selection, not a
    # model-invented recommendation.
    if len(understanding.explicit_course_ids) == 1:
        return RecommendationResult(
            user_message=str(message).strip(),
            intent=understanding.intent,
            status=RECOMMENDATION_EXPLICIT,
            primary_course_id=understanding.explicit_course_ids[0],
            candidates=candidates,
            clarification_needed=False,
            evidence=["single course explicitly identified by the user"],
        )

    # A single established context course can be used for a follow-up, but
    # it is still labeled as context-derived rather than newly recommended.
    if not understanding.explicit_course_ids and len(
        understanding.context_course_ids
    ) == 1:
        return RecommendationResult(
            user_message=str(message).strip(),
            intent=understanding.intent,
            status=RECOMMENDATION_READY,
            primary_course_id=understanding.context_course_ids[0],
            candidates=candidates,
            clarification_needed=False,
            evidence=["single course established in conversation context"],
        )

    # Multiple explicit courses are preserved as candidates. Never silently
    # choose one when the user asked about multiple courses.
    if len(understanding.explicit_course_ids) > 1:
        return RecommendationResult(
            user_message=str(message).strip(),
            intent=understanding.intent,
            status=RECOMMENDATION_NEEDS_CLARIFICATION,
            primary_course_id=None,
            candidates=candidates,
            clarification_needed=True,
            clarification_reason=(
                "Multiple courses were explicitly referenced; preserve them "
                "as separate candidates instead of silently selecting one."
            ),
            evidence=["multiple explicit course references"],
        )

    # No course evidence: a recommendation cannot be responsibly narrowed.
    return RecommendationResult(
        user_message=str(message).strip(),
        intent=understanding.intent,
        status=RECOMMENDATION_NEEDS_CLARIFICATION,
        primary_course_id=None,
        candidates=candidates,
        clarification_needed=True,
        clarification_reason=(
            "No course or established course context was provided. "
            "Additional student goals/background are needed before selecting "
            "a course."
        ),
        evidence=["course-selection evidence is insufficient"],
    )


def recommendation_to_dict(
    result: RecommendationResult,
) -> Dict[str, Any]:
    return {
        "user_message": result.user_message,
        "intent": result.intent,
        "status": result.status,
        "primary_course_id": result.primary_course_id,
        "candidates": [
            {
                "course_id": c.course_id,
                "official_name": c.official_name,
                "score": c.score,
                "reasons": list(c.reasons),
            }
            for c in result.candidates
        ],
        "clarification_needed": result.clarification_needed,
        "clarification_reason": result.clarification_reason,
        "evidence": list(result.evidence),
        "no_invention": result.no_invention,
    }


def validate_recommendation(
    result: RecommendationResult,
) -> Dict[str, Any]:
    errors = []

    if result.status not in {
        RECOMMENDATION_READY,
        RECOMMENDATION_NEEDS_CLARIFICATION,
        RECOMMENDATION_EXPLICIT,
    }:
        errors.append("Invalid recommendation status.")

    if result.no_invention is not True:
        errors.append("Recommendation no_invention must be True.")

    ids = [c.course_id for c in result.candidates]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate course candidates are not allowed.")

    if result.primary_course_id is not None:
        if result.primary_course_id not in ids:
            errors.append("Primary course must be one of the candidates.")

    if result.status == RECOMMENDATION_NEEDS_CLARIFICATION:
        if not result.clarification_needed:
            errors.append("Clarification status requires clarification_needed.")
        if not result.clarification_reason:
            errors.append("Clarification status requires a reason.")
        if result.primary_course_id is not None:
            errors.append(
                "Clarification state must not silently select a primary course."
            )

    if result.status in {
        RECOMMENDATION_READY,
        RECOMMENDATION_EXPLICIT,
    }:
        if result.primary_course_id is None:
            errors.append("Ready/explicit recommendation requires a primary.")
        if not result.candidates:
            errors.append("Ready/explicit recommendation requires candidates.")

    return {"valid": not errors, "errors": _unique(errors)}


def recommendation_query(
    kb: Any,
    message: str,
    context: Optional[ConversationContext] = None,
) -> RecommendationResult:
    return recommend_courses(kb, message, context)


def build_recommendation_layer() -> Any:
    from Sayyed_EdVantage_AI_CORE03 import build_understanding_layer
    return build_understanding_layer()
