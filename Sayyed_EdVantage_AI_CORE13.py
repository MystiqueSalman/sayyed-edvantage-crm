
"""
Sayyed EdVantage AI Agent — AI Core 13
Application & Enrollment Readiness Intelligence Contract

Read-only decision layer:
Interested -> Application Readiness -> Payment Readiness -> Enrollment Readiness

It never claims an application, payment, or enrollment occurred.
Unknown/unsupported facts remain unknown and are routed safely.
No CRM writes, messaging, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

READINESS_INTERESTED = "INTERESTED"
READINESS_APPLICATION = "APPLICATION_READY"
READINESS_PAYMENT = "PAYMENT_READY"
READINESS_ENROLLMENT = "ENROLLMENT_READY"

STATUS_READY = "ENROLLMENT_FLOW_READY"
STATUS_INSUFFICIENT = "ENROLLMENT_FLOW_INSUFFICIENT"
STATUS_CLARIFICATION = "ENROLLMENT_FLOW_CLARIFICATION"
STATUS_HANDOFF = "ENROLLMENT_FLOW_HANDOFF"
STATUS_UNKNOWN = "ENROLLMENT_FLOW_UNKNOWN"


@dataclass
class EnrollmentEvidence:
    field: str
    value: Any = None
    known: bool = False
    source: str = "explicit_user_input"
    note: str = ""


@dataclass
class EnrollmentReadiness:
    session_id: str
    status: str
    stage: str
    course_id: Optional[str] = None
    evidence: List[EnrollmentEvidence] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    safe_next_steps: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    handoff_reason: Optional[str] = None
    application_confirmed: bool = False
    payment_confirmed: bool = False
    enrollment_confirmed: bool = False
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


_ALLOWED_STAGES = {
    READINESS_INTERESTED,
    READINESS_APPLICATION,
    READINESS_PAYMENT,
    READINESS_ENROLLMENT,
}


def _norm(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def _safe_evidence(field: str, value: Any, known: bool = True, note: str = ""):
    return EnrollmentEvidence(field=field, value=value, known=known, note=note)


def infer_enrollment_stage(
    message: str,
    application_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    enrollment_status: Optional[str] = None,
) -> str:
    """
    Infer only a conversation/readiness stage from explicit statements.
    Status words never become confirmation flags.
    """
    q = _norm(message)

    # Explicit completed actions are deliberately represented as requests for
    # verification, not as confirmed facts.
    if any(x in q for x in (
        "already enrolled", "i am enrolled", "i'm enrolled",
        "payment done", "paid already", "already paid",
        "application submitted", "applied already",
    )):
        return READINESS_ENROLLMENT

    if payment_status is not None and _norm(payment_status) in {"ready", "pending", "requested"}:
        return READINESS_PAYMENT

    if application_status is not None and _norm(application_status) in {"ready", "pending", "requested"}:
        return READINESS_APPLICATION

    if any(x in q for x in (
        "how do i apply", "application process", "apply now", "want to apply",
        "i want to apply", "application",
    )):
        return READINESS_APPLICATION

    if any(x in q for x in (
        "how do i pay", "payment process", "pay now", "ready to pay",
        "want to pay", "payment",
    )):
        return READINESS_PAYMENT

    if any(x in q for x in (
        "enroll", "enrollment", "join", "admission",
    )):
        return READINESS_ENROLLMENT

    if any(x in q for x in (
        "interested", "sounds good", "i want this course", "i want to join",
        "i would like to join",
    )):
        return READINESS_INTERESTED

    return READINESS_INTERESTED


def assess_enrollment_readiness(
    message: str,
    session_id: str = "ENROLLMENT-SESSION",
    course_id: Optional[str] = None,
    region: Optional[str] = None,
    application_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    enrollment_status: Optional[str] = None,
    verified_fee_known: bool = False,
    required_application_details_known: bool = False,
) -> EnrollmentReadiness:

    stage = infer_enrollment_stage(
        message, application_status, payment_status, enrollment_status
    )
    q = _norm(message)
    evidence = []
    blockers = []
    questions = []
    next_steps = []

    if course_id:
        evidence.append(_safe_evidence("course_id", course_id))

    if region:
        evidence.append(_safe_evidence("region", region))

    if verified_fee_known:
        evidence.append(_safe_evidence("verified_fee_known", True))

    if required_application_details_known:
        evidence.append(_safe_evidence("required_application_details_known", True))

    # Critical invariant: conversation language cannot prove completed actions.
    completed_claim = any(x in q for x in (
        "already enrolled", "i am enrolled", "i'm enrolled",
        "payment done", "paid already", "already paid",
        "application submitted", "applied already",
    ))
    if completed_claim:
        blockers.append("Completed application/payment/enrollment status requires verification; the agent cannot treat the student's statement as system confirmation.")
        questions.append("Would you like the authorized admissions/team to verify the current application or enrollment status?")
        next_steps.append("Use the authorized CRM/admissions process for status verification.")
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_HANDOFF,
            stage=stage,
            course_id=course_id,
            evidence=evidence,
            blockers=blockers,
            clarification_questions=questions,
            safe_next_steps=next_steps,
            human_handoff_required=True,
            handoff_reason="A completed application, payment, or enrollment status requires system verification.",
        )

    if stage == READINESS_INTERESTED:
        if not course_id:
            return EnrollmentReadiness(
                session_id=session_id,
                status=STATUS_CLARIFICATION,
                stage=stage,
                evidence=evidence,
                blockers=["Selected course is not established."],
                clarification_questions=["Which course are you interested in?"],
                safe_next_steps=["Establish the selected course before discussing application or enrollment readiness."],
            )
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_READY,
            stage=stage,
            course_id=course_id,
            evidence=evidence,
            safe_next_steps=["Continue counselling and provide verified course/commercial information before starting an application process."],
        )

    if stage == READINESS_APPLICATION:
        if not course_id:
            blockers.append("Course selection is not established.")
            questions.append("Which course do you want to apply for?")
        if not required_application_details_known:
            blockers.append("Required application details are not established by this layer.")
            questions.append("Would you like the admissions team to confirm which application details/documents are required?")
        if blockers:
            return EnrollmentReadiness(
                session_id=session_id,
                status=STATUS_CLARIFICATION if questions else STATUS_INSUFFICIENT,
                stage=stage,
                course_id=course_id,
                evidence=evidence,
                blockers=blockers,
                clarification_questions=questions,
                safe_next_steps=["Do not claim that an application has been submitted.", "Use authorized admissions guidance for the actual application process."],
            )
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_READY,
            stage=stage,
            course_id=course_id,
            evidence=evidence,
            safe_next_steps=["Provide the documented application process through authorized admissions.", "Application submission itself requires the authorized application workflow."],
        )

    if stage == READINESS_PAYMENT:
        if not course_id:
            blockers.append("Course selection is not established.")
            questions.append("Which course are you ready to pay for?")
        if not verified_fee_known:
            blockers.append("A verified region-specific fee is not established in this readiness layer.")
            questions.append("Should the authorized admissions team confirm the applicable final fee and payment details?")
        if not region:
            blockers.append("Pricing region is not established.")
            questions.append("Are you applying from India or from outside India?")
        if blockers:
            return EnrollmentReadiness(
                session_id=session_id,
                status=STATUS_CLARIFICATION,
                stage=stage,
                course_id=course_id,
                evidence=evidence,
                blockers=blockers,
                clarification_questions=list(dict.fromkeys(questions)),
                safe_next_steps=["Do not claim payment has occurred.", "Use authorized admissions/payment workflow for final payment details."],
            )
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_READY,
            stage=stage,
            course_id=course_id,
            evidence=evidence,
            safe_next_steps=["Provide only the verified fee information already established.", "Actual payment must occur through the authorized payment workflow."],
        )

    if stage == READINESS_ENROLLMENT:
        if not course_id:
            blockers.append("Course selection is not established.")
            questions.append("Which course do you want to enroll in?")
        blockers.append("Enrollment completion cannot be established by conversation alone.")
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_HANDOFF if course_id else STATUS_CLARIFICATION,
            stage=stage,
            course_id=course_id,
            evidence=evidence,
            blockers=blockers,
            clarification_questions=questions,
            safe_next_steps=["Do not claim enrollment is complete.", "Use the authorized admissions/CRM workflow to verify application, payment, and enrollment status."],
            human_handoff_required=True if course_id else False,
            handoff_reason="Enrollment requires authorized system verification." if course_id else None,
        )

    return EnrollmentReadiness(
        session_id=session_id,
        status=STATUS_UNKNOWN,
        stage=stage,
        course_id=course_id,
        evidence=evidence,
        blockers=["Enrollment readiness state is unknown."],
        safe_next_steps=["Clarify the student's intended next step."],
    )


def validate_enrollment_readiness(result: EnrollmentReadiness) -> Dict[str, Any]:
    errors = []
    if not result.session_id:
        errors.append("session_id is required.")
    if result.status not in {
        STATUS_READY, STATUS_INSUFFICIENT, STATUS_CLARIFICATION,
        STATUS_HANDOFF, STATUS_UNKNOWN,
    }:
        errors.append("Invalid enrollment readiness status.")
    if result.stage not in _ALLOWED_STAGES:
        errors.append("Invalid enrollment stage.")
    if result.no_invention is not True:
        errors.append("no_invention must remain True.")
    if result.execution_enabled is not False:
        errors.append("execution_enabled must remain False.")
    if result.messaging_enabled is not False:
        errors.append("messaging_enabled must remain False.")
    if result.external_actions_enabled is not False:
        errors.append("external_actions_enabled must remain False.")
    if result.crm_writes_enabled is not False:
        errors.append("crm_writes_enabled must remain False.")

    if result.application_confirmed is not False:
        errors.append("application_confirmed must remain False in read-only readiness.")
    if result.payment_confirmed is not False:
        errors.append("payment_confirmed must remain False in read-only readiness.")
    if result.enrollment_confirmed is not False:
        errors.append("enrollment_confirmed must remain False in read-only readiness.")

    if result.status == STATUS_CLARIFICATION and not result.clarification_questions:
        errors.append("Clarification requires at least one question.")
    if result.status == STATUS_HANDOFF:
        if not result.human_handoff_required:
            errors.append("Handoff requires human_handoff_required=True.")
        if not result.handoff_reason:
            errors.append("Handoff requires handoff_reason.")
    if result.status == STATUS_READY and result.human_handoff_required:
        errors.append("Ready cannot require human handoff.")

    return {"valid": not errors, "errors": errors}


def run_enrollment_readiness(
    message: str,
    session_id: str = "ENROLLMENT-SESSION",
    **kwargs,
) -> EnrollmentReadiness:
    result = assess_enrollment_readiness(message, session_id=session_id, **kwargs)
    if not validate_enrollment_readiness(result)["valid"]:
        return EnrollmentReadiness(
            session_id=session_id,
            status=STATUS_HANDOFF,
            stage=result.stage,
            course_id=result.course_id,
            evidence=result.evidence,
            blockers=["Enrollment-readiness validation failed."],
            safe_next_steps=["Route the enrollment question to authorized admissions."],
            human_handoff_required=True,
            handoff_reason="Enrollment readiness plan validation failed.",
        )
    return result


def enrollment_readiness_to_dict(result: EnrollmentReadiness) -> Dict[str, Any]:
    return {
        "session_id": result.session_id,
        "status": result.status,
        "stage": result.stage,
        "course_id": result.course_id,
        "evidence": [
            {
                "field": x.field,
                "value": x.value,
                "known": x.known,
                "source": x.source,
                "note": x.note,
            }
            for x in result.evidence
        ],
        "blockers": list(result.blockers),
        "clarification_questions": list(result.clarification_questions),
        "safe_next_steps": list(result.safe_next_steps),
        "human_handoff_required": result.human_handoff_required,
        "handoff_reason": result.handoff_reason,
        "application_confirmed": result.application_confirmed,
        "payment_confirmed": result.payment_confirmed,
        "enrollment_confirmed": result.enrollment_confirmed,
        "no_invention": result.no_invention,
        "execution_enabled": result.execution_enabled,
        "messaging_enabled": result.messaging_enabled,
        "external_actions_enabled": result.external_actions_enabled,
        "crm_writes_enabled": result.crm_writes_enabled,
    }
