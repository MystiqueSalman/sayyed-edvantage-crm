
"""
Sayyed EdVantage AI Agent — AI Core 11
Conversation Objection Handling Intelligence Contract

Purpose:
- Detect and classify explicit student/prospect objections.
- Produce controlled response guidance grounded in known admissions/course policy.
- Distinguish objection handling from persuasion, messaging, enrollment, or action.
- Preserve uncertainty and require clarification/human handoff where appropriate.
- Never invent discounts, outcomes, placement, salary, certification, or admissions facts.
- No CRM writes, messaging, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

OBJECTION_NONE = "OBJECTION_NONE"
OBJECTION_FEE = "OBJECTION_FEE"
OBJECTION_TIME = "OBJECTION_TIME"
OBJECTION_PREREQUISITE = "OBJECTION_PREREQUISITE"
OBJECTION_CAREER_OUTCOME = "OBJECTION_CAREER_OUTCOME"
OBJECTION_PARENTAL_APPROVAL = "OBJECTION_PARENTAL_APPROVAL"
OBJECTION_TRUST = "OBJECTION_TRUST"
OBJECTION_COMPARISON = "OBJECTION_COMPARISON"
OBJECTION_COURSE_FIT = "OBJECTION_COURSE_FIT"
OBJECTION_DIFFICULTY = "OBJECTION_DIFFICULTY"
OBJECTION_FORMAT = "OBJECTION_FORMAT"
OBJECTION_UNKNOWN = "OBJECTION_UNKNOWN"

HANDLING_READY = "OBJECTION_HANDLING_READY"
HANDLING_CLARIFICATION = "OBJECTION_HANDLING_CLARIFICATION"
HANDLING_HANDOFF = "OBJECTION_HANDLING_HANDOFF"
HANDLING_UNKNOWN = "OBJECTION_HANDLING_UNKNOWN"


@dataclass
class ObjectionSignal:
    objection_type: str
    confidence: str
    matched_terms: List[str] = field(default_factory=list)
    explicit_text: Optional[str] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class ObjectionResponsePlan:
    session_id: str
    status: str
    objection: ObjectionSignal
    acknowledgement: str = ""
    response_points: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    safe_next_steps: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    human_handoff_required: bool = False
    handoff_reason: Optional[str] = None
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


_RULES = [
    (OBJECTION_FEE, (
        "fee", "fees", "price", "pricing", "cost", "expensive", "afford",
        "discount", "emi", "installment", "payment"
    )),
    (OBJECTION_TIME, (
        "time", "busy", "schedule", "timing", "hours", "working",
        "weekend", "weekday", "can't attend", "cannot attend"
    )),
    (OBJECTION_PREREQUISITE, (
        "prerequisite", "pre requisite", "eligibility", "qualification",
        "background", "beginner", "experience", "non technical", "non-technical"
    )),
    (OBJECTION_CAREER_OUTCOME, (
        "job", "placement", "salary", "career", "guarantee", "guaranteed",
        "income", "employment", "hire", "hired"
    )),
    (OBJECTION_PARENTAL_APPROVAL, (
        "parents", "parent", "father", "mother", "family", "spouse",
        "husband", "wife", "discuss with"
    )),
    (OBJECTION_TRUST, (
        "trust", "genuine", "legitimate", "scam", "reviews", "review",
        "certificate", "certification", "recognition", "accredited"
    )),
    (OBJECTION_COMPARISON, (
        "compare", "comparison", "competitor", "other institute", "another institute",
        "other course", "cheaper", "better than", "versus", "vs "
    )),
    (OBJECTION_COURSE_FIT, (
        "right course", "suitable", "suit me", "fit for me", "which course",
        "confused", "not sure which", "best course"
    )),
    (OBJECTION_DIFFICULTY, (
        "difficult", "hard", "too advanced", "can i learn", "will i understand",
        "math", "mathematics", "coding"
    )),
    (OBJECTION_FORMAT, (
        "online", "offline", "classroom", "live class", "recorded", "remote",
        "location", "travel", "timing"
    )),
]


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def detect_objection(message: str) -> ObjectionSignal:
    text = _normalize(message)
    if not text:
        return ObjectionSignal(
            objection_type=OBJECTION_UNKNOWN,
            confidence="none",
            explicit_text=message,
        )

    matches = []
    for objection_type, terms in _RULES:
        matched = [term for term in terms if term in text]
        if matched:
            matches.append((objection_type, matched))

    if not matches:
        return ObjectionSignal(
            objection_type=OBJECTION_NONE,
            confidence="low",
            explicit_text=message,
            evidence=["No supported objection signal was explicitly detected."],
        )

    # Preserve multiple explicit objections rather than silently choosing one.
    # The primary type is deterministic: first rule with the strongest lexical
    # match count, with rule order as the tie-breaker.
    ranked = sorted(
        enumerate(matches),
        key=lambda item: (-len(item[1][1]), item[0]),
    )
    primary_type, primary_terms = ranked[0][1]
    all_terms = _unique([term for _, terms in matches for term in terms])

    confidence = "high" if len(primary_terms) >= 2 else "medium"
    if len(matches) > 1:
        confidence = "medium"

    evidence = [
        f"Explicit objection signal matched: {primary_type}.",
    ]
    if len(matches) > 1:
        evidence.append(
            "Multiple objection categories were detected; response should not assume a single concern."
        )

    return ObjectionSignal(
        objection_type=primary_type,
        confidence=confidence,
        matched_terms=all_terms,
        explicit_text=message,
        evidence=evidence,
    )


def _base_prohibited_claims() -> List[str]:
    return [
        "Do not promise employment, placement, salary, income, or a guaranteed job.",
        "Do not invent discounts, payment plans, scholarships, or special offers.",
        "Do not invent certification, accreditation, recognition, or outcome claims.",
        "Do not claim admission, payment, application, or enrollment from an objection response.",
    ]


def _plan_for_type(objection_type: str):
    plans = {
        OBJECTION_FEE: (
            "Acknowledge the fee concern without pressure.",
            [
                "Quote only the verified region-specific fee when the student's region is known.",
                "For Indian students, the verified course fee may be explained with the required final-fee/admissions confirmation.",
                "For international students, do not substitute Indian pricing; route fee details to admissions.",
            ],
            ["Which course and region are you asking about?"],
            ["Provide the verified fee information applicable to the student's region.", "If a discount or payment plan is requested, route that question to authorized admissions."],
        ),
        OBJECTION_TIME: (
            "Acknowledge the scheduling concern and understand the student's availability.",
            [
                "Use only documented course delivery and duration information.",
                "Do not promise a custom schedule unless it is explicitly documented.",
                "If the student's availability is unclear, ask for the preferred days/times.",
            ],
            ["What days and time windows are realistically available to you?"],
            ["Compare the student's availability with documented program information.", "Escalate schedule exceptions to admissions/faculty rather than inventing flexibility."],
        ),
        OBJECTION_PREREQUISITE: (
            "Acknowledge the concern about eligibility or prior background.",
            [
                "Use only the eligibility/prerequisite information documented for the selected course.",
                "Do not invent academic requirements or waive requirements.",
                "If a requirement is unspecified, mark it unknown and route it for confirmation.",
            ],
            ["What is your current education or technical background?"],
            ["Check the documented eligibility requirements for the selected course.", "Ask admissions/faculty to confirm any requirement that the knowledge base marks as unspecified."],
        ),
        OBJECTION_CAREER_OUTCOME: (
            "Acknowledge the career-outcome question without making an outcome promise.",
            [
                "Explain documented skills, learning outcomes, projects, and career preparation only.",
                "Do not guarantee placement, employment, salary, or income.",
                "If the prospect requests a guarantee, state the limitation clearly and offer a human admissions/career discussion where appropriate.",
            ],
            ["Are you asking about the skills and career preparation, or specifically about guaranteed placement or salary?"],
            ["Explain documented career preparation.", "Route guarantee-specific questions to an authorized human representative."],
        ),
        OBJECTION_PARENTAL_APPROVAL: (
            "Acknowledge that the prospect wants to discuss the decision with family.",
            [
                "Respect the prospect's decision-making process.",
                "Provide factual course, fee, and process information that is already verified.",
                "Do not create urgency, pressure, or fabricated deadlines.",
            ],
            ["What information would you like to have available for that discussion?"],
            ["Prepare a factual summary of the selected course and verified commercial information.", "Let the prospect decide when to proceed."],
        ),
        OBJECTION_TRUST: (
            "Acknowledge the request for confidence or verification.",
            [
                "Provide only verifiable program, curriculum, fee, and process information available in the knowledge base.",
                "Certification or accreditation details must remain unknown when not documented.",
                "Do not manufacture reviews, rankings, partnerships, approvals, or recognition.",
            ],
            ["Which specific point would you like verified?"],
            ["Provide the relevant verified source-backed information.", "Hand unresolved verification questions to an authorized representative."],
        ),
        OBJECTION_COMPARISON: (
            "Acknowledge the comparison request and compare only supported facts.",
            [
                "Describe Sayyed EdVantage offerings using documented curriculum, duration, tools, projects, and verified commercial information.",
                "Do not invent competitor facts or claim superiority without evidence.",
                "If the comparison depends on unsupported competitor information, state that limitation.",
            ],
            ["Which specific factors matter most to you: curriculum, duration, tools, projects, fee, or delivery format?"],
            ["Compare documented Sayyed EdVantage facts against only information the prospect explicitly provides or that is independently verified.", "Avoid unsupported superiority claims."],
        ),
        OBJECTION_COURSE_FIT: (
            "Acknowledge uncertainty about course fit and return to the student's stated needs.",
            [
                "Use explicit education, experience, technical background, learning goals, career goals, and region only.",
                "Do not silently select a course when multiple supported candidates remain.",
                "Ask a targeted clarification question when the student's need is still ambiguous.",
            ],
            ["What is your main learning or career goal?", "What is your current education or technical background?"],
            ["Use the recommendation layer to evaluate supported course candidates.", "Clarify before recommending when multiple courses remain plausible."],
        ),
        OBJECTION_DIFFICULTY: (
            "Acknowledge the concern about learning difficulty without promising guaranteed success.",
            [
                "Explain documented prerequisite level and learning progression for the selected course.",
                "Do not guarantee that a student will find the course easy or succeed.",
                "If prerequisite information is unspecified, keep it unknown.",
            ],
            ["What part of the course feels most difficult or unfamiliar to you?"],
            ["Explain documented prerequisites and learning structure.", "Use faculty/admissions review for concerns that require individualized academic judgment."],
        ),
        OBJECTION_FORMAT: (
            "Acknowledge the delivery-format or location concern.",
            [
                "Use only documented delivery-format information.",
                "Do not invent classroom locations, recording availability, or custom attendance options.",
                "If a format detail is not documented, route it for confirmation.",
            ],
            ["Are you asking about online/offline delivery, location, or class timing?"],
            ["Provide the documented delivery information.", "Route unsupported format details to admissions."],
        ),
    }
    return plans.get(objection_type)


def build_objection_response_plan(
    message: str,
    session_id: str = "OBJECTION-SESSION",
    admission_readiness: Optional[Any] = None,
) -> ObjectionResponsePlan:
    signal = detect_objection(message)
    prohibited = _base_prohibited_claims()

    if signal.objection_type == OBJECTION_UNKNOWN:
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_CLARIFICATION,
            objection=signal,
            clarification_questions=["What concern would you like help with regarding the course or admission process?"],
            safe_next_steps=["Clarify the student's concern before selecting an objection-handling response."],
            prohibited_claims=prohibited,
        )

    if signal.objection_type == OBJECTION_NONE:
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_UNKNOWN,
            objection=signal,
            safe_next_steps=["Continue normal conversation understanding; do not force an objection category."],
            prohibited_claims=prohibited,
        )

    plan = _plan_for_type(signal.objection_type)
    if plan is None:
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_HANDOFF,
            objection=signal,
            human_handoff_required=True,
            handoff_reason="No controlled response policy is available for the detected objection.",
            safe_next_steps=["Route the concern to an authorized human representative."],
            prohibited_claims=prohibited,
        )

    acknowledgement, response_points, questions, next_steps = plan

    # If a readiness layer is supplied and already requires human review,
    # preserve that higher-level control rather than attempting to overcome it.
    if admission_readiness is not None and admission_readiness.human_handoff_required:
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_HANDOFF,
            objection=signal,
            acknowledgement=acknowledgement,
            response_points=response_points,
            clarification_questions=questions,
            safe_next_steps=next_steps + ["Follow the existing admission-readiness human-review path."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason=admission_readiness.handoff_reason or "Admission-readiness review is required.",
        )

    # Multiple signals require clarification rather than a persuasive single-track answer.
    text = _normalize(message)
    detected_categories = [
        objection_type for objection_type, terms in _RULES
        if any(term in text for term in terms)
    ]
    if len(detected_categories) > 1:
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_CLARIFICATION,
            objection=signal,
            acknowledgement="I understand there may be more than one concern here.",
            response_points=response_points,
            clarification_questions=questions + ["Which concern would you like to address first?"],
            safe_next_steps=["Resolve the primary concern before moving to a different objection category."],
            prohibited_claims=prohibited,
        )

    return ObjectionResponsePlan(
        session_id=session_id,
        status=HANDLING_READY,
        objection=signal,
        acknowledgement=acknowledgement,
        response_points=response_points,
        clarification_questions=questions,
        safe_next_steps=next_steps,
        prohibited_claims=prohibited,
    )


def objection_response_to_dict(plan: ObjectionResponsePlan) -> Dict[str, Any]:
    return {
        "session_id": plan.session_id,
        "status": plan.status,
        "objection": {
            "objection_type": plan.objection.objection_type,
            "confidence": plan.objection.confidence,
            "matched_terms": list(plan.objection.matched_terms),
            "explicit_text": plan.objection.explicit_text,
            "evidence": list(plan.objection.evidence),
        },
        "acknowledgement": plan.acknowledgement,
        "response_points": list(plan.response_points),
        "clarification_questions": list(plan.clarification_questions),
        "safe_next_steps": list(plan.safe_next_steps),
        "prohibited_claims": list(plan.prohibited_claims),
        "human_handoff_required": plan.human_handoff_required,
        "handoff_reason": plan.handoff_reason,
        "no_invention": plan.no_invention,
        "execution_enabled": plan.execution_enabled,
        "messaging_enabled": plan.messaging_enabled,
        "external_actions_enabled": plan.external_actions_enabled,
        "crm_writes_enabled": plan.crm_writes_enabled,
    }


def validate_objection_response_plan(plan: ObjectionResponsePlan) -> Dict[str, Any]:
    errors = []

    valid_types = {
        OBJECTION_NONE, OBJECTION_FEE, OBJECTION_TIME, OBJECTION_PREREQUISITE,
        OBJECTION_CAREER_OUTCOME, OBJECTION_PARENTAL_APPROVAL, OBJECTION_TRUST,
        OBJECTION_COMPARISON, OBJECTION_COURSE_FIT, OBJECTION_DIFFICULTY,
        OBJECTION_FORMAT, OBJECTION_UNKNOWN,
    }
    valid_statuses = {
        HANDLING_READY, HANDLING_CLARIFICATION, HANDLING_HANDOFF, HANDLING_UNKNOWN,
    }

    if not plan.session_id:
        errors.append("session_id is required.")
    if plan.objection.objection_type not in valid_types:
        errors.append("Invalid objection type.")
    if plan.status not in valid_statuses:
        errors.append("Invalid handling status.")
    if plan.no_invention is not True:
        errors.append("no_invention must remain True.")
    if plan.execution_enabled is not False:
        errors.append("execution_enabled must remain False.")
    if plan.messaging_enabled is not False:
        errors.append("messaging_enabled must remain False.")
    if plan.external_actions_enabled is not False:
        errors.append("external_actions_enabled must remain False.")
    if plan.crm_writes_enabled is not False:
        errors.append("crm_writes_enabled must remain False.")
    if not plan.prohibited_claims:
        errors.append("prohibited_claims must not be empty.")

    if plan.status == HANDLING_CLARIFICATION and not plan.clarification_questions:
        errors.append("Clarification handling requires at least one question.")

    if plan.status == HANDLING_HANDOFF:
        if not plan.human_handoff_required:
            errors.append("Handoff status requires human_handoff_required=True.")
        if not plan.handoff_reason:
            errors.append("Handoff status requires a handoff_reason.")

    if plan.status == HANDLING_READY and plan.human_handoff_required:
        errors.append("Ready status cannot require human handoff.")

    return {"valid": not errors, "errors": errors}


def run_objection_intelligence(
    message: str,
    session_id: str = "OBJECTION-SESSION",
    admission_readiness: Optional[Any] = None,
) -> ObjectionResponsePlan:
    plan = build_objection_response_plan(
        message=message,
        session_id=session_id,
        admission_readiness=admission_readiness,
    )
    validation = validate_objection_response_plan(plan)
    if not validation["valid"]:
        # Fail closed: return a handoff plan rather than emitting an invalid response plan.
        signal = detect_objection(message)
        return ObjectionResponsePlan(
            session_id=session_id,
            status=HANDLING_HANDOFF,
            objection=signal,
            safe_next_steps=["Route the objection to an authorized human representative."],
            prohibited_claims=_base_prohibited_claims(),
            human_handoff_required=True,
            handoff_reason="Objection-response plan validation failed.",
        )
    return plan


def objection_intelligence_query(
    message: str,
    session_id: str = "OBJECTION-SESSION",
) -> ObjectionResponsePlan:
    return run_objection_intelligence(message, session_id=session_id)
