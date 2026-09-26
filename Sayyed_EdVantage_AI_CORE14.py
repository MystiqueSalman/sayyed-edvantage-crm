
"""
Sayyed EdVantage AI Agent — AI Core 14
Follow-Up Intelligence Contract

Read-only intelligence layer for deciding whether a prospect conversation
warrants follow-up, why, what remains pending, and what the next conversation
should focus on.

This layer does NOT schedule, send, edit CRM, or perform external actions.
It produces controlled follow-up guidance only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

FOLLOWUP_NONE = "FOLLOWUP_NONE"
FOLLOWUP_GENERAL = "FOLLOWUP_GENERAL"
FOLLOWUP_COUNSELLING = "FOLLOWUP_COUNSELLING"
FOLLOWUP_OBJECTION = "FOLLOWUP_OBJECTION"
FOLLOWUP_FEE = "FOLLOWUP_FEE"
FOLLOWUP_APPLICATION = "FOLLOWUP_APPLICATION"
FOLLOWUP_PAYMENT = "FOLLOWUP_PAYMENT"
FOLLOWUP_ENROLLMENT = "FOLLOWUP_ENROLLMENT"
FOLLOWUP_MISSING_INFORMATION = "FOLLOWUP_MISSING_INFORMATION"
FOLLOWUP_HUMAN_HANDOFF = "FOLLOWUP_HUMAN_HANDOFF"
FOLLOWUP_UNKNOWN = "FOLLOWUP_UNKNOWN"

FOLLOWUP_RECOMMEND = "FOLLOWUP_RECOMMEND"
FOLLOWUP_CLARIFICATION = "FOLLOWUP_CLARIFICATION"
FOLLOWUP_NOT_NEEDED = "FOLLOWUP_NOT_NEEDED"
FOLLOWUP_HANDOFF = "FOLLOWUP_HANDOFF"
FOLLOWUP_UNKNOWN_STATUS = "FOLLOWUP_UNKNOWN_STATUS"

PRIORITY_LOW = "LOW"
PRIORITY_NORMAL = "NORMAL"
PRIORITY_HIGH = "HIGH"


@dataclass
class FollowUpSignal:
    reason: str
    confidence: str
    matched_terms: List[str] = field(default_factory=list)
    explicit_text: Optional[str] = None


@dataclass
class FollowUpPlan:
    session_id: str
    status: str
    priority: str
    signal: FollowUpSignal
    pending_items: List[str] = field(default_factory=list)
    next_conversation_topics: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)
    safe_next_steps: List[str] = field(default_factory=list)
    prohibited_claims: List[str] = field(default_factory=list)
    avoid_repetition: bool = True
    human_handoff_required: bool = False
    handoff_reason: Optional[str] = None
    no_invention: bool = True
    execution_enabled: bool = False
    messaging_enabled: bool = False
    external_actions_enabled: bool = False
    crm_writes_enabled: bool = False


_RULES = [
    (FOLLOWUP_HUMAN_HANDOFF, ("admissions team", "human", "representative", "call me", "contact me")),
    (FOLLOWUP_ENROLLMENT, ("enrollment", "enroll", "join", "admission")),
    (FOLLOWUP_PAYMENT, ("payment", "pay", "paid", "fee payment", "payment pending")),
    (FOLLOWUP_APPLICATION, ("application", "apply", "applied", "documents", "application pending")),
    (FOLLOWUP_FEE, ("fee", "fees", "price", "pricing", "cost", "discount", "emi", "installment")),
    (FOLLOWUP_OBJECTION, ("concern", "objection", "expensive", "too costly", "not sure", "hesitant")),
    (FOLLOWUP_COUNSELLING, ("counselling", "counseling", "counselling call", "discussed")),
    (FOLLOWUP_MISSING_INFORMATION, ("missing", "need details", "need information", "clarify", "clarification")),
]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().strip().split())


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def detect_followup_signal(message: str) -> FollowUpSignal:
    q = _norm(message)
    if not q:
        return FollowUpSignal(FOLLOWUP_UNKNOWN, "none", [], message)

    matches = []
    for reason, terms in _RULES:
        hit = [t for t in terms if t in q]
        if hit:
            matches.append((reason, hit))

    if not matches:
        return FollowUpSignal(
            FOLLOWUP_NONE,
            "low",
            [],
            message,
        )

    ranked = sorted(enumerate(matches), key=lambda x: (-len(x[1][1]), x[0]))
    reason, terms = ranked[0][1]
    all_terms = _unique([t for _, ts in matches for t in ts])
    confidence = "high" if len(terms) >= 2 else "medium"
    if len(matches) > 1:
        confidence = "medium"

    return FollowUpSignal(
        reason=reason,
        confidence=confidence,
        matched_terms=all_terms,
        explicit_text=message,
    )


def _base_rationale() -> List[str]:
    return [
        "Follow-up guidance is based only on explicit conversation evidence supplied to this layer.",
        "Do not invent a deadline, urgency, availability, discount, or prospect commitment.",
    ]


def build_followup_plan(
    message: str,
    session_id: str = "FOLLOWUP-SESSION",
    prior_topics: Optional[List[str]] = None,
    pending_items: Optional[List[str]] = None,
    human_review_required: bool = False,
    human_review_reason: Optional[str] = None,
) -> FollowUpPlan:
    signal = detect_followup_signal(message)
    prior_topics = list(prior_topics or [])
    pending_items = list(pending_items or [])
    rationale = _base_rationale()
    prohibited = [
        "Do not invent urgency or a deadline.",
        "Do not send a follow-up message automatically.",
        "Do not invent discounts, fees, payment plans, or admissions status.",
        "Do not repeatedly ask for information already provided.",
        "Do not claim application, payment, or enrollment has occurred.",
    ]

    if human_review_required:
        return FollowUpPlan(
            session_id=session_id,
            status=FOLLOWUP_HANDOFF,
            priority=PRIORITY_HIGH,
            signal=FollowUpSignal(FOLLOWUP_HUMAN_HANDOFF, "high", ["human_review"], message),
            pending_items=pending_items,
            next_conversation_topics=["Resolve the existing human-review item."],
            rationale=rationale + ["An existing human-review requirement takes priority over automated follow-up guidance."],
            safe_next_steps=["Route the matter to the authorized human representative."],
            human_handoff_required=True,
            handoff_reason=human_review_reason or "Existing human review is required.",
        )

    if signal.reason == FOLLOWUP_UNKNOWN:
        return FollowUpPlan(
            session_id=session_id,
            status=FOLLOWUP_CLARIFICATION,
            priority=PRIORITY_LOW,
            signal=signal,
            pending_items=pending_items,
            next_conversation_topics=[],
            clarification_questions=["What outcome or pending item should the follow-up address?"],
            rationale=rationale,
            safe_next_steps=["Clarify the intended follow-up context before recommending a topic."],
        )

    if signal.reason == FOLLOWUP_NONE:
        return FollowUpPlan(
            session_id=session_id,
            status=FOLLOWUP_NOT_NEEDED,
            priority=PRIORITY_LOW,
            signal=signal,
            pending_items=pending_items,
            next_conversation_topics=[],
            rationale=rationale + ["No explicit follow-up signal was detected."],
            safe_next_steps=["Continue the normal conversation flow rather than forcing a follow-up."],
        )

    topic_map = {
        FOLLOWUP_ENROLLMENT: ("Enrollment/admission status and the next authorized process step.", PRIORITY_HIGH),
        FOLLOWUP_PAYMENT: ("Verified payment details and authorized payment status verification.", PRIORITY_HIGH),
        FOLLOWUP_APPLICATION: ("Application requirements, submitted information, or authorized application status.", PRIORITY_HIGH),
        FOLLOWUP_FEE: ("Verified course fee, applicable region, and unresolved commercial questions.", PRIORITY_NORMAL),
        FOLLOWUP_OBJECTION: ("The specific unresolved objection or concern.", PRIORITY_NORMAL),
        FOLLOWUP_COUNSELLING: ("The student's stated counselling need and any unresolved decision point.", PRIORITY_NORMAL),
        FOLLOWUP_MISSING_INFORMATION: ("The specific information still required to make a grounded decision.", PRIORITY_NORMAL),
        FOLLOWUP_HUMAN_HANDOFF: ("The unresolved matter requiring an authorized representative.", PRIORITY_HIGH),
    }

    topic, priority = topic_map.get(
        signal.reason,
        ("The explicit pending topic in the student's message.", PRIORITY_NORMAL),
    )

    # Do not recommend a topic that is already represented in prior topics.
    prior_norm = {_norm(x) for x in prior_topics}
    if _norm(topic) in prior_norm:
        return FollowUpPlan(
            session_id=session_id,
            status=FOLLOWUP_NOT_NEEDED,
            priority=PRIORITY_LOW,
            signal=signal,
            pending_items=pending_items,
            rationale=rationale + ["The detected topic already appears in prior conversation topics; avoid repetitive follow-up."],
            safe_next_steps=["Wait for a new explicit development or pending item rather than repeating the same topic."],
        )

    questions = []
    if signal.reason == FOLLOWUP_MISSING_INFORMATION:
        questions = ["What specific information is still missing?"]
    elif signal.reason == FOLLOWUP_FEE:
        questions = ["Which course and pricing region should the commercial follow-up address?"]
    elif signal.reason == FOLLOWUP_OBJECTION:
        questions = ["What specific concern remains unresolved?"]

    rationale.append(f"Explicit follow-up signal detected: {signal.reason}.")
    if pending_items:
        rationale.append("Existing pending items were preserved rather than replaced.")

    return FollowUpPlan(
        session_id=session_id,
        status=FOLLOWUP_RECOMMEND,
        priority=priority,
        signal=signal,
        pending_items=pending_items,
        next_conversation_topics=[topic],
        clarification_questions=questions,
        rationale=rationale,
        safe_next_steps=[
            "Use the suggested topic only when it remains relevant to the prospect's current context.",
            "Avoid repeating questions or information already resolved.",
        ],
        prohibited_claims=prohibited,
    )


# Retained as an explicit field on the plan through this helper for callers that
# want a stable API name.
def validate_followup_plan(plan: FollowUpPlan) -> Dict[str, Any]:
    errors = []
    valid_statuses = {
        FOLLOWUP_RECOMMEND, FOLLOWUP_CLARIFICATION, FOLLOWUP_NOT_NEEDED,
        FOLLOWUP_HANDOFF, FOLLOWUP_UNKNOWN_STATUS,
    }
    valid_priorities = {PRIORITY_LOW, PRIORITY_NORMAL, PRIORITY_HIGH}
    valid_reasons = {
        FOLLOWUP_NONE, FOLLOWUP_GENERAL, FOLLOWUP_COUNSELLING, FOLLOWUP_OBJECTION,
        FOLLOWUP_FEE, FOLLOWUP_APPLICATION, FOLLOWUP_PAYMENT, FOLLOWUP_ENROLLMENT,
        FOLLOWUP_MISSING_INFORMATION, FOLLOWUP_HUMAN_HANDOFF, FOLLOWUP_UNKNOWN,
    }

    if not plan.session_id:
        errors.append("session_id is required.")
    if plan.status not in valid_statuses:
        errors.append("Invalid follow-up status.")
    if plan.priority not in valid_priorities:
        errors.append("Invalid follow-up priority.")
    if plan.signal.reason not in valid_reasons:
        errors.append("Invalid follow-up reason.")
    if plan.no_invention is not True:
        errors.append("no_invention must remain True.")
    if plan.avoid_repetition is not True:
        errors.append("avoid_repetition must remain True.")
    if plan.execution_enabled is not False:
        errors.append("execution_enabled must remain False.")
    if plan.messaging_enabled is not False:
        errors.append("messaging_enabled must remain False.")
    if plan.external_actions_enabled is not False:
        errors.append("external_actions_enabled must remain False.")
    if plan.crm_writes_enabled is not False:
        errors.append("crm_writes_enabled must remain False.")

    if plan.status == FOLLOWUP_RECOMMEND and not plan.next_conversation_topics:
        errors.append("Recommendation requires a next conversation topic.")
    if plan.status == FOLLOWUP_CLARIFICATION and not plan.clarification_questions:
        errors.append("Clarification requires a question.")
    if plan.status == FOLLOWUP_HANDOFF:
        if not plan.human_handoff_required:
            errors.append("Handoff requires human_handoff_required=True.")
        if not plan.handoff_reason:
            errors.append("Handoff requires handoff_reason.")
    if plan.status == FOLLOWUP_NOT_NEEDED and plan.next_conversation_topics:
        errors.append("Not-needed status should not contain recommended topics.")

    return {"valid": not errors, "errors": errors}


def run_followup_intelligence(
    message: str,
    session_id: str = "FOLLOWUP-SESSION",
    **kwargs,
) -> FollowUpPlan:
    plan = build_followup_plan(message, session_id=session_id, **kwargs)
    if not validate_followup_plan(plan)["valid"]:
        return FollowUpPlan(
            session_id=session_id,
            status=FOLLOWUP_HANDOFF,
            priority=PRIORITY_HIGH,
            signal=detect_followup_signal(message),
            rationale=["Follow-up plan validation failed; fail closed."],
            safe_next_steps=["Route the matter to an authorized human representative."],
            human_handoff_required=True,
            handoff_reason="Follow-up intelligence plan validation failed.",
            prohibited_claims=[
                "Do not invent urgency, deadlines, fees, discounts, or prospect commitments.",
                "Do not send messages automatically.",
            ],
        )
    return plan


def followup_plan_to_dict(plan: FollowUpPlan) -> Dict[str, Any]:
    return {
        "session_id": plan.session_id,
        "status": plan.status,
        "priority": plan.priority,
        "signal": {
            "reason": plan.signal.reason,
            "confidence": plan.signal.confidence,
            "matched_terms": list(plan.signal.matched_terms),
            "explicit_text": plan.signal.explicit_text,
        },
        "pending_items": list(plan.pending_items),
        "next_conversation_topics": list(plan.next_conversation_topics),
        "clarification_questions": list(plan.clarification_questions),
        "rationale": list(plan.rationale),
        "safe_next_steps": list(plan.safe_next_steps),
        "avoid_repetition": plan.avoid_repetition,
        "human_handoff_required": plan.human_handoff_required,
        "handoff_reason": plan.handoff_reason,
        "no_invention": plan.no_invention,
        "execution_enabled": plan.execution_enabled,
        "messaging_enabled": plan.messaging_enabled,
        "external_actions_enabled": plan.external_actions_enabled,
        "crm_writes_enabled": plan.crm_writes_enabled,
    }
