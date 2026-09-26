
"""
Sayyed EdVantage AI Agent — AI Core 12
Fee & Commercial Conversation Intelligence Contract

This layer converts commercial questions into safe, grounded conversation guidance.
It uses the verified Master KB Batch 22 commercial layer.
No discounts, payment plans, taxes, international prices, or enrollment outcomes
are invented. No messages, CRM writes, external actions, or autonomous execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from Sayyed_EdVantage_Master_KB_BATCH22 import (
    COMMERCIAL_SOURCE_ID,
    build_master_kb_with_commercial_knowledge,
    get_commercial_answer,
    validate_commercial_answer,
)


COMMERCIAL_INTENT_FEE = "COMMERCIAL_FEE"
COMMERCIAL_INTENT_DISCOUNT = "COMMERCIAL_DISCOUNT"
COMMERCIAL_INTENT_PAYMENT = "COMMERCIAL_PAYMENT"
COMMERCIAL_INTENT_TAX = "COMMERCIAL_TAX"
COMMERCIAL_INTENT_INTERNATIONAL = "COMMERCIAL_INTERNATIONAL"
COMMERCIAL_INTENT_COMBO = "COMMERCIAL_COMBO"
COMMERCIAL_INTENT_GENERAL = "COMMERCIAL_GENERAL"
COMMERCIAL_INTENT_UNKNOWN = "COMMERCIAL_UNKNOWN"

COMMERCIAL_READY = "COMMERCIAL_READY"
COMMERCIAL_CLARIFICATION = "COMMERCIAL_CLARIFICATION"
COMMERCIAL_HANDOFF = "COMMERCIAL_HANDOFF"
COMMERCIAL_UNKNOWN = "COMMERCIAL_UNKNOWN"


@dataclass
class CommercialSignal:
    intent: str
    confidence: str
    matched_terms: List[str] = field(default_factory=list)
    explicit_text: Optional[str] = None


@dataclass
class CommercialConversationPlan:
    session_id: str
    status: str
    signal: CommercialSignal
    commercial_record: Dict[str, Any] = field(default_factory=dict)
    answer_points: List[str] = field(default_factory=list)
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
    (COMMERCIAL_INTENT_DISCOUNT, ("discount", "discounts", "offer", "concession", "scholarship", "special price")),
    (COMMERCIAL_INTENT_PAYMENT, ("emi", "installment", "installments", "payment plan", "pay in parts", "monthly payment", "advance")),
    (COMMERCIAL_INTENT_TAX, ("gst", "tax", "taxes", "including gst", "excluding gst")),
    (COMMERCIAL_INTENT_INTERNATIONAL, ("international", "outside india", "overseas", "abroad", "foreign student")),
    (COMMERCIAL_INTENT_COMBO, ("combo", "combination", "combined course", "bundle")),
    (COMMERCIAL_INTENT_FEE, ("fee", "fees", "price", "pricing", "cost", "how much", "rupees", "inr", "₹")),
]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().strip().split())


def _prohibited() -> List[str]:
    return [
        "Do not invent discounts, scholarships, concessions, offers, or payment plans.",
        "Do not quote Indian pricing to an international student.",
        "Do not invent taxes, tax rates, final payable amounts, or enrollment charges.",
        "Do not claim that a fee guarantees admission, placement, employment, salary, or income.",
        "Do not claim application, payment, or enrollment has occurred.",
    ]


def detect_commercial_intent(message: str) -> CommercialSignal:
    q = _norm(message)
    if not q:
        return CommercialSignal(COMMERCIAL_INTENT_UNKNOWN, "none", [], message)

    matches = []
    for intent, terms in _RULES:
        hit = [t for t in terms if t in q]
        if hit:
            matches.append((intent, hit))

    if not matches:
        return CommercialSignal(COMMERCIAL_INTENT_UNKNOWN, "low", [], message)

    ranked = sorted(enumerate(matches), key=lambda x: (-len(x[1][1]), x[0]))
    primary, terms = ranked[0][1]
    all_terms = list(dict.fromkeys(t for _, ts in matches for t in ts))
    confidence = "high" if len(terms) >= 2 else "medium"
    return CommercialSignal(primary, confidence, all_terms, message)


def _region_from_query(message: str, region: Optional[str]) -> Optional[str]:
    if region:
        return _norm(region)
    q = _norm(message)
    if any(x in q for x in ("international", "outside india", "overseas", "abroad", "foreign student")):
        return "international"
    if any(x in q for x in ("india", "indian", "inr", "₹", "rupees")):
        return "india"
    return None


def build_commercial_conversation_plan(
    message: str,
    session_id: str = "COMMERCIAL-SESSION",
    region: Optional[str] = None,
    kb: Any = None,
) -> CommercialConversationPlan:
    signal = detect_commercial_intent(message)
    kb = kb or build_master_kb_with_commercial_knowledge()
    prohibited = _prohibited()
    region_norm = _region_from_query(message, region)

    if signal.intent == COMMERCIAL_INTENT_UNKNOWN:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_UNKNOWN,
            signal=signal,
            clarification_questions=["Are you asking about the course fee, discount, payment options, tax/GST, or international pricing?"],
            safe_next_steps=["Clarify the commercial question before quoting or interpreting a fee."],
            prohibited_claims=prohibited,
        )

    record = get_commercial_answer(kb, message, region=region_norm)
    validation = validate_commercial_answer(record)

    if not validation["valid"]:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=signal,
            commercial_record=record,
            safe_next_steps=["Route the commercial question to authorized admissions for verification."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason="Commercial knowledge validation failed.",
        )

    # International pricing is intentionally undefined.
    if record["status"] == "INTERNATIONAL_UNDEFINED":
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=signal,
            commercial_record=record,
            answer_points=[
                "International pricing is not currently defined in the verified commercial knowledge.",
                "Indian pricing must not be substituted for international students.",
            ],
            safe_next_steps=["Admissions/team should provide the applicable international fee, taxes, discounts, payment options, and enrollment details."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason="International pricing requires authorized fee confirmation.",
        )

    # Region must be known before a fee is quoted.
    if record["status"] == "REGION_REQUIRED":
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_CLARIFICATION,
            signal=signal,
            commercial_record=record,
            clarification_questions=["Are you asking as a student in India or from outside India?"],
            safe_next_steps=["Confirm the pricing region before quoting a fee."],
            prohibited_claims=prohibited,
        )

    # Discount/payment/tax questions are not answered with invented specifics.
    if signal.intent == COMMERCIAL_INTENT_DISCOUNT:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=signal,
            commercial_record=record,
            answer_points=["The verified knowledge base provides the base fee, but does not define a specific discount, scholarship, or special offer."],
            safe_next_steps=["Admissions/team should confirm whether any currently authorized discount or offer applies."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason="Discount/offer details are not defined in the verified commercial source.",
        )

    if signal.intent == COMMERCIAL_INTENT_PAYMENT:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=signal,
            commercial_record=record,
            answer_points=["The verified commercial source does not define a specific EMI, installment schedule, or payment plan."],
            safe_next_steps=["Admissions/team should confirm currently authorized payment options."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason="Payment-plan details are not defined in the verified commercial source.",
        )

    if signal.intent == COMMERCIAL_INTENT_TAX:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF if record["status"] == "OFFERING_NOT_FOUND" else COMMERCIAL_READY,
            signal=signal,
            commercial_record=record,
            answer_points=[
                "The verified Indian commercial record states GST/tax applicable.",
                "A specific tax amount or final payable amount is not defined by this layer.",
            ],
            safe_next_steps=["Admissions/team confirms the final fee, applicable taxes, discounts, payment options, and enrollment details."],
            prohibited_claims=prohibited,
            human_handoff_required=(record["status"] == "OFFERING_NOT_FOUND"),
            handoff_reason=("Requested offering could not be identified." if record["status"] == "OFFERING_NOT_FOUND" else None),
        )

    if record["status"] == "OFFERING_NOT_FOUND":
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=signal,
            commercial_record=record,
            safe_next_steps=["Route the unidentified commercial offering to admissions for verification."],
            prohibited_claims=prohibited,
            human_handoff_required=True,
            handoff_reason="Requested offering is not identified in the verified commercial layer.",
        )

    if record["status"] == "VERIFIED_INDIA_FEE":
        offering = record["offering"]
        points = [
            f'Verified Indian base fee for {offering["name"]}: ₹{record["fee"]:,} + GST.',
            "Admissions/team confirms the final fee, taxes, discounts, payment options, and enrollment details.",
        ]
        if signal.intent == COMMERCIAL_INTENT_COMBO:
            points.append("The combo price is a verified commercial offering; do not infer or invent its curriculum composition beyond documented course information.")
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_READY,
            signal=signal,
            commercial_record=record,
            answer_points=points,
            safe_next_steps=["If the student wants to proceed, provide the verified information and route enrollment-specific details to authorized admissions."],
            prohibited_claims=prohibited,
        )

    return CommercialConversationPlan(
        session_id=session_id,
        status=COMMERCIAL_HANDOFF,
        signal=signal,
        commercial_record=record,
        safe_next_steps=["Route the commercial question to authorized admissions."],
        prohibited_claims=prohibited,
        human_handoff_required=True,
        handoff_reason="Unhandled commercial state.",
    )


def validate_commercial_conversation_plan(plan: CommercialConversationPlan) -> Dict[str, Any]:
    errors = []
    valid_statuses = {COMMERCIAL_READY, COMMERCIAL_CLARIFICATION, COMMERCIAL_HANDOFF, COMMERCIAL_UNKNOWN}
    valid_intents = {
        COMMERCIAL_INTENT_FEE, COMMERCIAL_INTENT_DISCOUNT, COMMERCIAL_INTENT_PAYMENT,
        COMMERCIAL_INTENT_TAX, COMMERCIAL_INTENT_INTERNATIONAL, COMMERCIAL_INTENT_COMBO,
        COMMERCIAL_INTENT_GENERAL, COMMERCIAL_INTENT_UNKNOWN,
    }
    if not plan.session_id:
        errors.append("session_id is required.")
    if plan.status not in valid_statuses:
        errors.append("Invalid commercial handling status.")
    if plan.signal.intent not in valid_intents:
        errors.append("Invalid commercial intent.")
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
    if plan.status == COMMERCIAL_CLARIFICATION and not plan.clarification_questions:
        errors.append("Clarification requires a question.")
    if plan.status == COMMERCIAL_HANDOFF:
        if not plan.human_handoff_required:
            errors.append("Handoff requires human_handoff_required=True.")
        if not plan.handoff_reason:
            errors.append("Handoff requires handoff_reason.")
    if plan.status == COMMERCIAL_READY and plan.human_handoff_required:
        errors.append("Ready cannot require human handoff.")
    if plan.commercial_record.get("status") == "INTERNATIONAL_UNDEFINED":
        if plan.commercial_record.get("fee") is not None:
            errors.append("International fee must remain undefined.")
    return {"valid": not errors, "errors": errors}


def commercial_conversation_query(
    message: str,
    session_id: str = "COMMERCIAL-SESSION",
    region: Optional[str] = None,
    kb: Any = None,
) -> CommercialConversationPlan:
    plan = build_commercial_conversation_plan(message, session_id, region, kb)
    if not validate_commercial_conversation_plan(plan)["valid"]:
        return CommercialConversationPlan(
            session_id=session_id,
            status=COMMERCIAL_HANDOFF,
            signal=detect_commercial_intent(message),
            safe_next_steps=["Route the commercial question to authorized admissions."],
            prohibited_claims=_prohibited(),
            human_handoff_required=True,
            handoff_reason="Commercial conversation plan validation failed.",
        )
    return plan


def commercial_plan_to_dict(plan: CommercialConversationPlan) -> Dict[str, Any]:
    return {
        "session_id": plan.session_id,
        "status": plan.status,
        "signal": {
            "intent": plan.signal.intent,
            "confidence": plan.signal.confidence,
            "matched_terms": list(plan.signal.matched_terms),
            "explicit_text": plan.signal.explicit_text,
        },
        "commercial_record": dict(plan.commercial_record),
        "answer_points": list(plan.answer_points),
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
