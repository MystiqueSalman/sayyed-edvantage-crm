"""
Sayyed EdVantage AI Agent — AI Core 09
Counselling & Admission Conversation Intelligence Contract
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from Sayyed_EdVantage_AI_CORE07 import StudentNeedProfile, validate_need_profile
from Sayyed_EdVantage_AI_CORE08 import (
    RecommendationDecision,
    validate_recommendation_decision,
    DECISION_RECOMMEND,
    DECISION_CLARIFICATION,
    DECISION_UNKNOWN,
    DECISION_REVIEW,
)

COUNSELLING_DISCOVERY = "COUNSELLING_DISCOVERY"
COUNSELLING_QUALIFICATION = "COUNSELLING_QUALIFICATION"
COUNSELLING_RECOMMENDATION = "COUNSELLING_RECOMMENDATION"
COUNSELLING_CLARIFICATION = "COUNSELLING_CLARIFICATION"
COUNSELLING_HANDOFF = "COUNSELLING_HANDOFF"
COUNSELLING_COMPLETE = "COUNSELLING_COMPLETE"
COUNSELLING_REVIEW = "COUNSELLING_REVIEW"


@dataclass
class CounsellingQuestion:
    field: str
    question: str
    reason: str
    required: bool = True


@dataclass
class CounsellingPlan:
    session_id: str
    stage: str
    primary_course_id: Optional[str] = None
    candidate_course_ids: List[str] = field(default_factory=list)
    confirmed_need_fields: List[str] = field(default_factory=list)
    unknown_need_fields: List[str] = field(default_factory=list)
    questions: List[CounsellingQuestion] = field(default_factory=list)
    recommendation_rationale: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    handoff_required: bool = False
    handoff_reason: Optional[str] = None
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


FIELD_LABELS = {
    "learning_goal": "learning goal",
    "experience": "experience",
    "technical_background": "technical background",
    "current_role": "current role",
    "education": "education",
    "region": "region",
    "budget": "budget",
}


def _unique(values):
    return list(dict.fromkeys(values))


def _confirmed_fields(need):
    mapping = {
        "learning_goal": need.stated_goal,
        "experience": need.experience_level,
        "technical_background": need.technical_background,
        "current_role": need.current_role,
        "education": need.education,
        "region": need.region,
        "budget": need.budget,
    }
    return [name for name, value in mapping.items() if value is not None]


def _unknown_fields(need):
    confirmed = set(_confirmed_fields(need))
    return [name for name in FIELD_LABELS if name not in confirmed]


def _question_for(field_name):
    data = {
        "learning_goal": (
            "What is your main learning or career goal?",
            "The student's goal is not explicitly established.",
        ),
        "experience": (
            "Are you a fresher, student, or working professional, and what experience do you have?",
            "Experience level is not explicitly established.",
        ),
        "technical_background": (
            "What programming, tools, or technical skills do you already know?",
            "Technical background is not explicitly established.",
        ),
        "current_role": (
            "What are you currently studying or working as?",
            "Current role is not explicitly established.",
        ),
        "education": (
            "What is your highest or current educational qualification?",
            "Education is not explicitly established.",
        ),
        "region": (
            "Are you an Indian student or an international student?",
            "Region is needed before applying region-specific commercial information.",
        ),
        "budget": (
            "Do you have a budget range you would like us to consider?",
            "Budget has not been explicitly stated.",
        ),
    }
    question, reason = data[field_name]
    return CounsellingQuestion(
        field=field_name, question=question, reason=reason, required=False
    )


def build_counselling_plan(need, decision):
    nv = validate_need_profile(need)
    dv = validate_recommendation_decision(decision)

    # Permit Core 07's intentional intermediate clarification state to enter
    # Core 09; all other upstream validation failures remain controlled review.
    nerrors = list(nv.get("errors", []))
    only_intermediate = (
        need.status == "NEED_CLARIFICATION"
        and nerrors
        and all(e == "Clarification status requires questions." for e in nerrors)
    )
    if (not nv["valid"] and not only_intermediate) or not dv["valid"]:
        return CounsellingPlan(
            session_id=need.session_id,
            stage=COUNSELLING_REVIEW,
            questions=[CounsellingQuestion(
                "review",
                "Please confirm the student information before continuing counselling.",
                "Upstream validation failed.",
            )],
            handoff_required=True,
            handoff_reason="Upstream need or recommendation data failed validation.",
        )

    confirmed = _confirmed_fields(need)
    unknown = _unknown_fields(need)

    if decision.status == DECISION_REVIEW:
        return CounsellingPlan(
            session_id=need.session_id,
            stage=COUNSELLING_REVIEW,
            candidate_course_ids=list(decision.candidate_course_ids),
            confirmed_need_fields=confirmed,
            unknown_need_fields=unknown,
            questions=[CounsellingQuestion(
                "review",
                "Please confirm which course information should be considered.",
                "Recommendation decision requires human review.",
            )],
            recommendation_rationale=list(decision.rationale),
            next_steps=["Resolve the recommendation review before proceeding."],
            handoff_required=True,
            handoff_reason="Recommendation decision requires human review.",
        )

    if decision.status == DECISION_UNKNOWN:
        question = (
            _question_for("learning_goal")
            if "learning_goal" in unknown
            else CounsellingQuestion(
                "course_interest",
                "Which course or course area are you most interested in?",
                "No supported recommendation candidate is available.",
            )
        )
        return CounsellingPlan(
            session_id=need.session_id,
            stage=COUNSELLING_DISCOVERY,
            confirmed_need_fields=confirmed,
            unknown_need_fields=unknown,
            questions=[question],
            next_steps=["Collect enough explicit information for a supported recommendation."],
        )

    if decision.status == DECISION_CLARIFICATION:
        question = (
            decision.clarification_questions[0]
            if decision.clarification_questions
            else "Which course or course area are you most interested in?"
        )
        return CounsellingPlan(
            session_id=need.session_id,
            stage=COUNSELLING_CLARIFICATION,
            candidate_course_ids=list(decision.candidate_course_ids),
            confirmed_need_fields=confirmed,
            unknown_need_fields=unknown,
            questions=[CounsellingQuestion(
                "course_interest",
                question,
                "Multiple or ambiguous course candidates must not be silently selected.",
            )],
            recommendation_rationale=list(decision.rationale),
            next_steps=["Confirm the student's preferred course before recommending one."],
        )

    primary = decision.primary_course_id
    if not primary:
        return CounsellingPlan(
            session_id=need.session_id,
            stage=COUNSELLING_REVIEW,
            candidate_course_ids=list(decision.candidate_course_ids),
            confirmed_need_fields=confirmed,
            unknown_need_fields=unknown,
            questions=[CounsellingQuestion(
                "review",
                "Please confirm the recommended course before continuing.",
                "Recommendation state is internally incomplete.",
            )],
            handoff_required=True,
            handoff_reason="Recommend decision has no primary course.",
        )

    steps = [
        "Explain the supported course recommendation using the available evidence.",
        "Confirm whether the student wants to continue with this course.",
    ]
    if need.region is None:
        steps.append("Confirm student region before quoting region-specific commercial information.")

    return CounsellingPlan(
        session_id=need.session_id,
        stage=COUNSELLING_RECOMMENDATION,
        primary_course_id=primary,
        candidate_course_ids=list(decision.candidate_course_ids),
        confirmed_need_fields=confirmed,
        unknown_need_fields=unknown,
        recommendation_rationale=list(decision.rationale),
        next_steps=steps,
    )


def counselling_response_guidance(plan):
    if plan.stage == COUNSELLING_DISCOVERY:
        return [
            "Ask the listed discovery question(s).",
            "Do not assume the student's goal, experience, budget, or background.",
        ]
    if plan.stage == COUNSELLING_CLARIFICATION:
        return [
            "Present the candidate courses distinctly.",
            "Ask the student to choose rather than silently selecting one.",
        ]
    if plan.stage == COUNSELLING_RECOMMENDATION:
        return [
            "State the selected course and only the supported reasons.",
            "Do not promise jobs, salary, placement, certification, admission, or outcomes.",
            "If fee information is requested, use the region-aware commercial layer.",
        ]
    if plan.stage == COUNSELLING_REVIEW:
        return [
            "Do not proceed with an uncertain recommendation.",
            "Route the unresolved issue to controlled human review.",
        ]
    return ["Continue only with information supported by the knowledge and conversation evidence."]


def counselling_plan_to_dict(plan):
    return {
        "session_id": plan.session_id,
        "stage": plan.stage,
        "primary_course_id": plan.primary_course_id,
        "candidate_course_ids": list(plan.candidate_course_ids),
        "confirmed_need_fields": list(plan.confirmed_need_fields),
        "unknown_need_fields": list(plan.unknown_need_fields),
        "questions": [
            {"field": q.field, "question": q.question, "reason": q.reason, "required": q.required}
            for q in plan.questions
        ],
        "recommendation_rationale": list(plan.recommendation_rationale),
        "next_steps": list(plan.next_steps),
        "handoff_required": plan.handoff_required,
        "handoff_reason": plan.handoff_reason,
        "no_invention": plan.no_invention,
        "execution_enabled": plan.execution_enabled,
        "messaging_enabled": plan.messaging_enabled,
        "external_actions_enabled": plan.external_actions_enabled,
        "crm_writes_enabled": plan.crm_writes_enabled,
    }


def validate_counselling_plan(plan):
    errors = []
    valid_stages = {
        COUNSELLING_DISCOVERY, COUNSELLING_QUALIFICATION,
        COUNSELLING_RECOMMENDATION, COUNSELLING_CLARIFICATION,
        COUNSELLING_HANDOFF, COUNSELLING_COMPLETE, COUNSELLING_REVIEW,
    }
    if not plan.session_id.strip():
        errors.append("Counselling session ID cannot be empty.")
    if plan.stage not in valid_stages:
        errors.append("Invalid counselling stage.")
    if plan.no_invention is not True:
        errors.append("Counselling no_invention must be True.")
    for flag in ("execution_enabled", "messaging_enabled", "external_actions_enabled", "crm_writes_enabled"):
        if getattr(plan, flag) is not False:
            errors.append(f"{flag} must remain False.")
    if len(plan.candidate_course_ids) != len(set(plan.candidate_course_ids)):
        errors.append("Duplicate counselling candidate course IDs are not allowed.")
    if plan.primary_course_id and plan.primary_course_id not in plan.candidate_course_ids:
        errors.append("Primary course must exist in candidate course IDs.")
    if plan.stage == COUNSELLING_RECOMMENDATION and not plan.primary_course_id:
        errors.append("Recommendation stage requires a primary course.")
    if plan.stage == COUNSELLING_CLARIFICATION:
        if plan.primary_course_id is not None:
            errors.append("Clarification stage must not select a primary course.")
        if not plan.questions:
            errors.append("Clarification stage requires a question.")
    if plan.stage == COUNSELLING_REVIEW and not plan.handoff_required:
        errors.append("Review stage requires handoff.")
    if plan.handoff_required and not plan.handoff_reason:
        errors.append("Handoff requires a reason.")
    return {"valid": not errors, "errors": _unique(errors)}


def run_counselling_intelligence(need, decision):
    return build_counselling_plan(need, decision)
