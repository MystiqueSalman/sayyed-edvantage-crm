"""
Sayyed EdVantage AI Agent — AI Core 10
Lead Qualification & Admission Readiness Intelligence Contract

Purpose:
- Convert explicit prospect evidence, student need, eligibility, recommendation,
  and counselling state into a controlled admission-readiness assessment.
- Distinguish readiness from actual admission/enrollment.
- Preserve unknowns and identify the next missing evidence.
- Never infer payment, application, consent, admission, or enrollment.
- No CRM writes, messaging, external actions, or autonomous execution.
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
from Sayyed_EdVantage_AI_CORE09 import (
    CounsellingPlan,
    validate_counselling_plan,
    COUNSELLING_RECOMMENDATION,
    COUNSELLING_CLARIFICATION,
    COUNSELLING_DISCOVERY,
    COUNSELLING_REVIEW,
)


READINESS_READY = "ADMISSION_READY"
READINESS_INSUFFICIENT = "ADMISSION_INSUFFICIENT"
READINESS_CLARIFICATION = "ADMISSION_CLARIFICATION"
READINESS_REVIEW = "ADMISSION_REVIEW"


@dataclass
class ReadinessEvidence:
    field: str
    status: str
    value: Optional[str] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class AdmissionReadiness:
    session_id: str
    status: str
    course_id: Optional[str] = None
    evidence: List[ReadinessEvidence] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    handoff_reason: Optional[str] = None
    application_confirmed: bool = False
    payment_confirmed: bool = False
    admission_confirmed: bool = False
    enrollment_confirmed: bool = False
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


def _unique(values):
    return list(dict.fromkeys(values))


def _need_evidence(need):
    mapping = {
        "learning_goal": need.stated_goal,
        "experience": need.experience_level,
        "technical_background": need.technical_background,
        "current_role": need.current_role,
        "education": need.education,
        "region": need.region,
        "budget": need.budget,
    }
    return [
        ReadinessEvidence(
            field=k,
            status="explicit" if v is not None else "unknown",
            value=v,
        )
        for k, v in mapping.items()
    ]


def _supported_need_fields(need):
    return [e.field for e in _need_evidence(need) if e.value is not None]


def assess_admission_readiness(
    need: StudentNeedProfile,
    decision: RecommendationDecision,
    counselling: CounsellingPlan,
) -> AdmissionReadiness:
    nv = validate_need_profile(need)
    dv = validate_recommendation_decision(decision)
    cv = validate_counselling_plan(counselling)

    # Core 10 accepts two controlled intermediate states from upstream layers:
    # - NEED_CLARIFICATION may temporarily have no question yet;
    # - COUNSELLING_CLARIFICATION may temporarily have no question yet.
    # These are not validation failures for admission-readiness purposes when
    # the corresponding upstream recommendation state is also clarification.
    if (
        not nv["valid"]
        and need.status == "NEED_CLARIFICATION"
        and nv.get("errors") == ["Clarification status requires questions."]
    ):
        nv = {"valid": True, "errors": []}

    if (
        not dv["valid"]
        and decision.status == DECISION_CLARIFICATION
        and dv.get("errors") == ["Clarification status requires questions."]
    ):
        dv = {"valid": True, "errors": []}

    if (
        not cv["valid"]
        and counselling.stage == COUNSELLING_CLARIFICATION
        and cv.get("errors") == ["Clarification stage requires a question."]
    ):
        cv = {"valid": True, "errors": []}

    if not nv["valid"] or not dv["valid"] or not cv["valid"]:
        return AdmissionReadiness(
            session_id=need.session_id,
            status=READINESS_REVIEW,
            evidence=_need_evidence(need),
            blockers=["One or more upstream layers failed validation."],
            next_steps=["Resolve upstream validation issues before assessing admission readiness."],
            human_handoff_required=True,
            handoff_reason="Upstream validation failure.",
        )

    evidence = _need_evidence(need)
    supported = _supported_need_fields(need)
    missing = [e.field for e in evidence if e.value is None]

    if decision.status == DECISION_REVIEW or counselling.stage == COUNSELLING_REVIEW:
        return AdmissionReadiness(
            session_id=need.session_id,
            status=READINESS_REVIEW,
            course_id=decision.primary_course_id,
            evidence=evidence,
            missing_fields=missing,
            blockers=["Recommendation/counselling requires human review."],
            next_steps=["Resolve the human-review issue before admission readiness can be assessed."],
            human_handoff_required=True,
            handoff_reason="Upstream recommendation or counselling review is unresolved.",
        )

    if decision.status == DECISION_UNKNOWN:
        return AdmissionReadiness(
            session_id=need.session_id,
            status=READINESS_INSUFFICIENT,
            evidence=evidence,
            missing_fields=missing,
            blockers=["No supported course recommendation is available."],
            next_steps=["Collect explicit student need information and establish a supported course recommendation."],
        )

    if decision.status == DECISION_CLARIFICATION or counselling.stage == COUNSELLING_CLARIFICATION:
        return AdmissionReadiness(
            session_id=need.session_id,
            status=READINESS_CLARIFICATION,
            course_id=None,
            evidence=evidence,
            missing_fields=missing,
            blockers=["Course selection is not yet confirmed."],
            next_steps=["Confirm the student's preferred course before assessing admission readiness."],
        )

    if decision.status != DECISION_RECOMMEND or counselling.stage != COUNSELLING_RECOMMENDATION:
        return AdmissionReadiness(
            session_id=need.session_id,
            status=READINESS_INSUFFICIENT,
            course_id=decision.primary_course_id,
            evidence=evidence,
            missing_fields=missing,
            blockers=["The recommendation and counselling stages are not both ready."],
            next_steps=["Complete the recommendation and counselling stages first."],
        )

    # A course recommendation is not itself an admission. Core 10 deliberately
    # requires explicit admission-process evidence before calling a lead ready.
    # The current upstream layers do not contain application/payment/consent
    # confirmations, so the safe default is insufficient.
    blockers = [
        "Application has not been explicitly confirmed.",
        "Payment has not been explicitly confirmed.",
        "Admission has not been explicitly confirmed.",
        "Enrollment has not been explicitly confirmed.",
    ]
    next_steps = [
        "Confirm the student's decision to proceed with the recommended course.",
        "Provide the applicable application/enrollment process through the authorized admissions workflow.",
        "Confirm application status before treating the lead as admission-ready.",
    ]

    return AdmissionReadiness(
        session_id=need.session_id,
        status=READINESS_INSUFFICIENT,
        course_id=decision.primary_course_id,
        evidence=evidence,
        missing_fields=missing,
        blockers=blockers,
        next_steps=next_steps,
    )


def build_admission_readiness(
    need: StudentNeedProfile,
    decision: RecommendationDecision,
    counselling: CounsellingPlan,
) -> AdmissionReadiness:
    return assess_admission_readiness(need, decision, counselling)


def admission_readiness_to_dict(
    readiness: AdmissionReadiness,
) -> Dict[str, Any]:
    return {
        "session_id": readiness.session_id,
        "status": readiness.status,
        "course_id": readiness.course_id,
        "evidence": [
            {
                "field": e.field,
                "status": e.status,
                "value": e.value,
                "evidence": list(e.evidence),
            }
            for e in readiness.evidence
        ],
        "missing_fields": list(readiness.missing_fields),
        "blockers": list(readiness.blockers),
        "next_steps": list(readiness.next_steps),
        "human_handoff_required": readiness.human_handoff_required,
        "handoff_reason": readiness.handoff_reason,
        "application_confirmed": readiness.application_confirmed,
        "payment_confirmed": readiness.payment_confirmed,
        "admission_confirmed": readiness.admission_confirmed,
        "enrollment_confirmed": readiness.enrollment_confirmed,
        "no_invention": readiness.no_invention,
        "execution_enabled": readiness.execution_enabled,
        "messaging_enabled": readiness.messaging_enabled,
        "external_actions_enabled": readiness.external_actions_enabled,
        "crm_writes_enabled": readiness.crm_writes_enabled,
    }


def validate_admission_readiness(
    readiness: AdmissionReadiness,
) -> Dict[str, Any]:
    errors = []

    if not readiness.session_id.strip():
        errors.append("Readiness session ID cannot be empty.")

    if readiness.status not in {
        READINESS_READY,
        READINESS_INSUFFICIENT,
        READINESS_CLARIFICATION,
        READINESS_REVIEW,
    }:
        errors.append("Invalid admission readiness status.")

    if readiness.no_invention is not True:
        errors.append("Readiness no_invention must be True.")

    for flag in (
        "execution_enabled",
        "messaging_enabled",
        "external_actions_enabled",
        "crm_writes_enabled",
    ):
        if getattr(readiness, flag) is not False:
            errors.append(f"{flag} must remain False.")

    for confirmed in (
        "application_confirmed",
        "payment_confirmed",
        "admission_confirmed",
        "enrollment_confirmed",
    ):
        if getattr(readiness, confirmed) is not False:
            errors.append(
                f"{confirmed} cannot be asserted by the read-only readiness layer."
            )

    if len(readiness.missing_fields) != len(set(readiness.missing_fields)):
        errors.append("Duplicate missing fields are not allowed.")

    if readiness.status == READINESS_READY:
        if not readiness.course_id:
            errors.append("Admission-ready status requires a course.")
        if readiness.blockers:
            errors.append("Admission-ready status cannot have blockers.")

    if readiness.status in {
        READINESS_INSUFFICIENT,
        READINESS_CLARIFICATION,
        READINESS_REVIEW,
    }:
        if not readiness.blockers and not readiness.next_steps:
            errors.append("Non-ready status requires blockers or next steps.")

    if readiness.human_handoff_required and not readiness.handoff_reason:
        errors.append("Human handoff requires a reason.")

    return {"valid": not errors, "errors": _unique(errors)}


def run_admission_readiness(
    need: StudentNeedProfile,
    decision: RecommendationDecision,
    counselling: CounsellingPlan,
) -> AdmissionReadiness:
    return assess_admission_readiness(need, decision, counselling)
