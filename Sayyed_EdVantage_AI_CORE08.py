"""
Sayyed EdVantage AI Agent — AI Core 08
Recommendation Scoring & Decision Contract

Purpose:
- Convert Core 04 recommendation evidence + Core 07 student-need evidence
  into a deterministic recommendation decision.
- Preserve upstream candidate scores/ranking rather than inventing new
  course-fit facts.
- Select a primary course only when upstream evidence supports it.
- Require clarification for ambiguous/multi-course recommendations.
- Preserve provenance and explicit evidence.
- No CRM writes, messaging, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy

from Sayyed_EdVantage_AI_CORE04 import RecommendationResult
from Sayyed_EdVantage_AI_CORE07 import (
    StudentNeedProfile,
    validate_need_profile,
    NEED_READY,
)


DECISION_RECOMMEND = "DECISION_RECOMMEND"
DECISION_CLARIFICATION = "DECISION_CLARIFICATION"
DECISION_UNKNOWN = "DECISION_UNKNOWN"
DECISION_REVIEW = "DECISION_REVIEW"


@dataclass
class RecommendationScore:
    course_id: str
    rank: int
    upstream_score: Optional[float] = None
    confidence: str = "UNKNOWN"
    evidence: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class RecommendationDecision:
    session_id: str
    status: str
    primary_course_id: Optional[str] = None
    candidate_course_ids: List[str] = field(default_factory=list)
    scores: List[RecommendationScore] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


def _unique(values):
    return list(dict.fromkeys(values))


def _safe_float(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_score(candidate):
    for name in ("score", "match_score", "ranking_score"):
        value = _safe_float(getattr(candidate, name, None))
        if value is not None:
            return value
    return None


def _candidate_reasons(candidate):
    for name in ("reasons", "reason", "match_reasons"):
        value = getattr(candidate, name, None)
        if value is None:
            continue
        if isinstance(value, str):
            return [value] if value.strip() else []
        try:
            return [str(v) for v in value if str(v).strip()]
        except TypeError:
            return [str(value)]
    return []


def _candidate_evidence(candidate):
    for name in ("evidence", "evidence_ids", "source_ids"):
        value = getattr(candidate, name, None)
        if value is None:
            continue
        if isinstance(value, str):
            return [value] if value.strip() else []
        try:
            return [str(v) for v in value if str(v).strip()]
        except TypeError:
            return [str(value)]
    return []


def _recommendation_source_ids(recommendation):
    for name in ("source_ids", "provenance_source_ids"):
        value = getattr(recommendation, name, None)
        if value is not None:
            if isinstance(value, str):
                return [value] if value.strip() else []
            try:
                return _unique([str(v) for v in value if str(v).strip()])
            except TypeError:
                return [str(value)]
    result = []
    for candidate in getattr(recommendation, "candidates", []) or []:
        result.extend(_candidate_evidence(candidate))
    return _unique(result)


def _candidate_ids(recommendation):
    result = []
    for candidate in getattr(recommendation, "candidates", []) or []:
        course_id = getattr(candidate, "course_id", None)
        if course_id:
            result.append(str(course_id))
    return _unique(result)


def score_recommendation(
    need: StudentNeedProfile,
    recommendation: RecommendationResult,
) -> List[RecommendationScore]:
    """
    Preserve Core 04 ranking/score evidence. Core 08 does not manufacture
    semantic fit scores from missing facts.
    """
    rows = []
    candidates = list(getattr(recommendation, "candidates", []) or [])
    for index, candidate in enumerate(candidates, start=1):
        course_id = getattr(candidate, "course_id", None)
        if not course_id:
            continue

        evidence = _candidate_evidence(candidate)
        reasons = _candidate_reasons(candidate)

        confidence = "UNKNOWN"
        if index == 1 and len(candidates) == 1:
            confidence = "HIGH" if getattr(
                recommendation, "clarification_needed", False
            ) is False else "MEDIUM"
        elif index == 1:
            confidence = "MEDIUM"

        if not evidence and need.stated_goal:
            evidence.append("Student goal is explicit in the need profile.")

        rows.append(
            RecommendationScore(
                course_id=str(course_id),
                rank=index,
                upstream_score=_candidate_score(candidate),
                confidence=confidence,
                evidence=_unique(evidence),
                reasons=_unique(reasons),
            )
        )
    return rows


def decide_recommendation(
    need: StudentNeedProfile,
    recommendation: RecommendationResult,
) -> RecommendationDecision:
    validation = validate_need_profile(need)

    # Core 08 can receive a need profile whose status is already
    # NEED_CLARIFICATION but whose questions have not yet been populated.
    # That is a valid intermediate handoff into recommendation decisioning;
    # the recommendation layer itself can supply the clarification question.
    # Do not weaken any other Core 07 validation rule.
    validation_errors = list(validation.get("errors", []))
    allowed_intermediate_error = "Clarification status requires questions."
    if (
        not validation["valid"]
        and not (
            need.status == "NEED_CLARIFICATION"
            and validation_errors
            and all(
                error == allowed_intermediate_error
                for error in validation_errors
            )
        )
    ):
        return RecommendationDecision(
            session_id=need.session_id,
            status=DECISION_REVIEW,
            rationale=["Need profile validation failed; human review is required."],
            clarification_questions=[
                "Please confirm the student information before selecting a course."
            ],
        )

    candidate_ids = _candidate_ids(recommendation)
    scores = score_recommendation(need, recommendation)
    clarification_needed = bool(
        getattr(recommendation, "clarification_needed", False)
    )
    upstream_primary = getattr(recommendation, "primary_course_id", None)

    rationale = []
    questions = []

    if not candidate_ids:
        return RecommendationDecision(
            session_id=need.session_id,
            status=DECISION_UNKNOWN,
            candidate_course_ids=[],
            scores=scores,
            rationale=["No supported recommendation candidate was returned."],
            clarification_questions=[
                "Which course are you interested in, or what is your main goal?"
            ],
            source_ids=_recommendation_source_ids(recommendation),
        )

    # Hard safety rule: multiple supported candidates are always ambiguous.
    # Never silently collapse multiple courses into one.
    if len(candidate_ids) > 1:
        rationale.append(
            "Multiple supported course candidates were returned; "
            "do not silently select a course."
        )
        questions.append("Which course or course area are you most interested in?")
        return RecommendationDecision(
            session_id=need.session_id,
            status=DECISION_CLARIFICATION,
            primary_course_id=None,
            candidate_course_ids=candidate_ids,
            scores=scores,
            rationale=rationale,
            clarification_questions=_unique(questions),
            source_ids=_recommendation_source_ids(recommendation),
        )

    if clarification_needed:
        rationale.append(
            "The upstream recommendation layer requested clarification; "
            "do not silently select a course."
        )
        return RecommendationDecision(
            session_id=need.session_id,
            status=DECISION_CLARIFICATION,
            primary_course_id=None,
            candidate_course_ids=candidate_ids,
            scores=scores,
            rationale=rationale,
            clarification_questions=[
                "Which course or course area are you most interested in?"
            ],
            source_ids=_recommendation_source_ids(recommendation),
        )

    primary = str(upstream_primary) if upstream_primary else candidate_ids[0]
    if primary not in candidate_ids:
        return RecommendationDecision(
            session_id=need.session_id,
            status=DECISION_REVIEW,
            candidate_course_ids=candidate_ids,
            scores=scores,
            rationale=[
                "Upstream primary course is not present in the candidate set."
            ],
            clarification_questions=[
                "Please confirm which course should be considered."
            ],
            source_ids=_recommendation_source_ids(recommendation),
        )

    rationale.append("A single supported recommendation candidate is available.")
    if upstream_primary:
        rationale.append("The primary course was supplied by the upstream recommendation layer.")
    else:
        rationale.append("The single candidate is used without inventing additional fit evidence.")

    return RecommendationDecision(
        session_id=need.session_id,
        status=DECISION_RECOMMEND,
        primary_course_id=primary,
        candidate_course_ids=candidate_ids,
        scores=scores,
        rationale=rationale,
        clarification_questions=[],
        source_ids=_recommendation_source_ids(recommendation),
    )


def build_recommendation_decision(
    need: StudentNeedProfile,
    recommendation: RecommendationResult,
) -> RecommendationDecision:
    return decide_recommendation(need, recommendation)


def recommendation_decision_to_dict(
    decision: RecommendationDecision,
) -> Dict[str, Any]:
    return {
        "session_id": decision.session_id,
        "status": decision.status,
        "primary_course_id": decision.primary_course_id,
        "candidate_course_ids": list(decision.candidate_course_ids),
        "scores": [
            {
                "course_id": s.course_id,
                "rank": s.rank,
                "upstream_score": s.upstream_score,
                "confidence": s.confidence,
                "evidence": list(s.evidence),
                "reasons": list(s.reasons),
            }
            for s in decision.scores
        ],
        "rationale": list(decision.rationale),
        "clarification_questions": list(decision.clarification_questions),
        "source_ids": list(decision.source_ids),
        "no_invention": decision.no_invention,
        "execution_enabled": decision.execution_enabled,
        "messaging_enabled": decision.messaging_enabled,
        "external_actions_enabled": decision.external_actions_enabled,
        "crm_writes_enabled": decision.crm_writes_enabled,
    }


def validate_recommendation_decision(
    decision: RecommendationDecision,
) -> Dict[str, Any]:
    errors = []

    if not decision.session_id.strip():
        errors.append("Decision session ID cannot be empty.")

    if decision.status not in {
        DECISION_RECOMMEND,
        DECISION_CLARIFICATION,
        DECISION_UNKNOWN,
        DECISION_REVIEW,
    }:
        errors.append("Invalid recommendation decision status.")

    if decision.no_invention is not True:
        errors.append("Decision no_invention must be True.")

    for flag in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if getattr(decision, flag) is not False:
            errors.append(f"{flag} must remain False.")

    if len(decision.candidate_course_ids) != len(
        set(decision.candidate_course_ids)
    ):
        errors.append("Duplicate candidate course IDs are not allowed.")

    score_ids = [s.course_id for s in decision.scores]
    if len(score_ids) != len(set(score_ids)):
        errors.append("Duplicate recommendation score course IDs are not allowed.")

    if decision.primary_course_id and (
        decision.primary_course_id not in decision.candidate_course_ids
    ):
        errors.append("Primary course must exist in candidate course IDs.")

    if decision.status == DECISION_RECOMMEND:
        if not decision.primary_course_id:
            errors.append("Recommend status requires a primary course.")
        if len(decision.candidate_course_ids) != 1:
            errors.append("Recommend status requires exactly one candidate.")

    if decision.status == DECISION_CLARIFICATION:
        if not decision.clarification_questions:
            errors.append("Clarification status requires questions.")
        if decision.primary_course_id is not None:
            errors.append("Clarification decision must not silently select a primary course.")

    if decision.status == DECISION_UNKNOWN:
        if decision.primary_course_id is not None:
            errors.append("Unknown decision must not select a primary course.")

    if decision.status == DECISION_REVIEW:
        if not decision.clarification_questions:
            errors.append("Review decision requires a review question.")

    for score in decision.scores:
        if score.rank < 1:
            errors.append("Recommendation score rank must be >= 1.")
        if score.confidence not in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
            errors.append("Invalid recommendation confidence.")
        if score.course_id not in decision.candidate_course_ids:
            errors.append("Score course must be a candidate course.")

    return {"valid": not errors, "errors": _unique(errors)}


def run_recommendation_decision(
    need: StudentNeedProfile,
    recommendation: RecommendationResult,
) -> RecommendationDecision:
    return decide_recommendation(need, recommendation)
