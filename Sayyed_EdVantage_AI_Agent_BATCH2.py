from __future__ import annotations
"""
Sayyed EdVantage AI Agent — Phase 1 / Batch 2
READ-ONLY decision-support layer.

This module reads leads.json and produces:
1. Intent detection
2. Objection detection
3. Admission/buying signals
4. Counselling strategy
5. Personalized call/message script
6. Risk + conversion insight

It does NOT modify the CRM or leads.json.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LEADS_FILE = PROJECT_ROOT / "data" / "leads.json"

HIGH_INTENT = {
    "admission", "admit", "enroll", "enrollment", "join", "joining",
    "apply", "application", "payment", "pay", "fees", "fee",
    "start", "batch", "seat", "seats", "register", "registration",
    "confirm", "confirmation", "when can", "how can i join",
}
INFO_INTENT = {
    "information", "info", "details", "brochure", "syllabus",
    "course", "courses", "duration", "eligibility", "certificate",
    "career", "job", "placement", "curriculum", "schedule",
}
PRICE_OBJECTIONS = {
    "expensive", "costly", "too much", "high fee", "high fees",
    "can't afford", "cannot afford", "budget", "price", "fees",
}
TIMING_OBJECTIONS = {
    "busy", "time", "timing", "schedule", "later", "next month",
    "next batch", "not now", "after", "weekend",
}
TRUST_OBJECTIONS = {
    "doubt", "scam", "trust", "genuine", "real", "guarantee",
    "proof", "review", "reviews", "quality",
}
FAMILY_OBJECTIONS = {
    "parent", "parents", "family", "father", "mother", "husband",
    "wife", "permission", "discuss",
}
UNCERTAINTY_OBJECTIONS = {
    "think", "thinking", "not sure", "confused", "confusion",
    "decide", "decision", "maybe", "will see", "let me see",
}
URGENT_SIGNALS = {
    "urgent", "today", "now", "immediately", "asap", "last seat",
    "last seats", "deadline", "closing", "starts today", "starts tomorrow",
}
POSITIVE_SIGNALS = {
    "interested", "yes", "ready", "want to join", "want admission",
    "send details", "send fees", "send payment", "how to pay",
    "register", "book", "reserve", "confirm",
}

def load_leads() -> dict[str, dict[str, Any]]:
    if not LEADS_FILE.exists():
        return {}
    try:
        data = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}

def get_lead(lead_id: str):
    return load_leads().get(str(lead_id))

def all_leads():
    return list(load_leads().values())

def text_of(lead) -> str:
    fields = [
        lead.get("message"),
        lead.get("notes"),
        lead.get("follow_up_notes"),
        lead.get("counselling_notes"),
        lead.get("course_interest"),
        lead.get("status"),
    ]
    history_fields = [
        "counselling_history", "follow_up_history", "status_history"
    ]
    parts = [str(x or "") for x in fields]
    for key in history_fields:
        value = lead.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item or "") for item in value)
    return " ".join(parts).lower()

def hits(text: str, words: set[str]) -> list[str]:
    found = []
    for word in words:
        if word in text:
            found.append(word)
    return sorted(set(found), key=lambda x: (-len(x), x))

def detect_intent(lead) -> dict[str, Any]:
    text = text_of(lead)
    high = hits(text, HIGH_INTENT)
    info = hits(text, INFO_INTENT)

    status = str(lead.get("status", "New") or "New").strip()
    if status in {"Interested", "Application", "Payment Pending"}:
        high.append("crm_status_signal")
    if status == "Enrolled":
        return {
            "primary": "Enrolled",
            "confidence": 100,
            "signals": ["enrolled_status"],
            "secondary": [],
        }

    if len(high) >= 2 or status in {"Interested", "Application", "Payment Pending"}:
        primary = "Admission Intent"
        confidence = min(98, 65 + len(high) * 7)
    elif high:
        primary = "Admission Intent"
        confidence = min(90, 55 + len(high) * 8)
    elif info:
        primary = "Information Seeking"
        confidence = min(85, 50 + len(info) * 5)
    else:
        primary = "Early Exploration"
        confidence = 35

    secondary = []
    if info:
        secondary.append("Course Information")
    if "fees" in text or "fee" in text or "payment" in text:
        secondary.append("Pricing / Payment")
    if "career" in text or "job" in text or "placement" in text:
        secondary.append("Career Outcome")

    return {
        "primary": primary,
        "confidence": confidence,
        "signals": sorted(set(high + info)),
        "secondary": secondary,
    }

def detect_objections(lead) -> dict[str, Any]:
    text = text_of(lead)
    categories = {
        "Price": hits(text, PRICE_OBJECTIONS),
        "Timing": hits(text, TIMING_OBJECTIONS),
        "Trust": hits(text, TRUST_OBJECTIONS),
        "Family": hits(text, FAMILY_OBJECTIONS),
        "Uncertainty": hits(text, UNCERTAINTY_OBJECTIONS),
    }
    detected = {k: v for k, v in categories.items() if v}

    # Treat very early leads as "no explicit objection", not as an objection.
    if not detected:
        return {"primary": None, "detected": {}, "count": 0}

    priority = ["Price", "Timing", "Trust", "Family", "Uncertainty"]
    primary = next(k for k in priority if k in detected)
    return {"primary": primary, "detected": detected, "count": len(detected)}

def detect_buying_signals(lead) -> dict[str, Any]:
    text = text_of(lead)
    positive = hits(text, POSITIVE_SIGNALS)
    urgent = hits(text, URGENT_SIGNALS)
    status = str(lead.get("status", "New") or "New").strip()

    signals = []
    if status in {"Interested", "Application", "Payment Pending"}:
        signals.append("advanced_crm_status")
    if positive:
        signals.append("positive_language")
    if urgent:
        signals.append("urgency_language")
    if lead.get("course_interest"):
        signals.append("course_selected")
    if lead.get("phone"):
        signals.append("contactable")
    if lead.get("email"):
        signals.append("email_available")

    strength = 25
    strength += min(35, len(positive) * 8)
    strength += min(20, len(urgent) * 10)
    if status == "Interested":
        strength += 15
    elif status in {"Application", "Payment Pending"}:
        strength += 25
    if lead.get("course_interest"):
        strength += 5
    strength = min(100, strength)

    return {
        "strength": strength,
        "level": "Strong" if strength >= 70 else "Moderate" if strength >= 45 else "Weak",
        "signals": sorted(set(signals)),
        "positive_terms": positive,
        "urgency_terms": urgent,
    }

def counselling_strategy(lead, intent, objections, buying) -> dict[str, Any]:
    status = str(lead.get("status", "New") or "New").strip()
    objection = objections["primary"]
    intent_name = intent["primary"]

    if status == "Enrolled":
        objective = "Complete onboarding and admission documentation."
        approach = "Confirm next steps, documents, schedule and onboarding support."
    elif objection == "Price":
        objective = "Protect value perception and clarify the payment path."
        approach = "Understand the budget concern first, then explain value, outcomes and available payment structure without pressure."
    elif objection == "Timing":
        objective = "Remove scheduling friction."
        approach = "Identify the student's realistic start date and offer the most suitable schedule or next batch."
    elif objection == "Trust":
        objective = "Build confidence before asking for commitment."
        approach = "Answer verification questions clearly and provide factual course, faculty, process and outcome information."
    elif objection == "Family":
        objective = "Help the student make an informed family decision."
        approach = "Clarify the exact concern and prepare a concise explanation the student can discuss with family."
    elif objection == "Uncertainty":
        objective = "Convert uncertainty into a specific decision point."
        approach = "Ask what information is missing, resolve it, and agree on a clear follow-up date."
    elif intent_name == "Admission Intent" or buying["strength"] >= 70:
        objective = "Move the lead toward the next admission step."
        approach = "Confirm course fit, answer the final question, and propose a concrete next step."
    elif intent_name == "Information Seeking":
        objective = "Turn information interest into qualified counselling."
        approach = "Give concise course information and ask one qualifying question about goal, background or timeline."
    else:
        objective = "Qualify the lead."
        approach = "Start with the student's goal, course interest and expected timeline before pitching."

    return {
        "objective": objective,
        "approach": approach,
        "tone": "Professional, helpful, consultative and non-pushy",
        "recommended_question": recommended_question(lead, objection, intent_name),
    }

def recommended_question(lead, objection, intent_name) -> str:
    if objection == "Price":
        return "Is the main concern the total fee, the payment schedule, or the value you expect from the course?"
    if objection == "Timing":
        return "What start date and weekly schedule would realistically work for you?"
    if objection == "Trust":
        return "What specific information would you like us to clarify so you can make a confident decision?"
    if objection == "Family":
        return "What is the main point you need to discuss with your family before deciding?"
    if objection == "Uncertainty":
        return "What is the one question still preventing you from making a decision?"
    if intent_name == "Admission Intent":
        return "Would you like to proceed with the next admission step, or is there anything you want me to clarify first?"
    if intent_name == "Information Seeking":
        return "What is your main goal from this course, and when are you planning to start?"
    return "What are you mainly looking for, and what would you like to achieve from the course?"

def generate_script(lead, strategy, intent, objections, buying) -> dict[str, str]:
    name = str(lead.get("name", "") or "").strip()
    first_name = name.split()[0] if name else "there"
    course = str(lead.get("course_interest", "") or "").strip()
    course_phrase = f" regarding {course}" if course else ""

    opening = f"Hello {first_name}, thank you for your interest{course_phrase}."
    body = strategy["approach"]
    question = strategy["recommended_question"]

    if objections["primary"]:
        close = "Once we clarify this, we can decide the most suitable next step for you."
    elif buying["strength"] >= 70:
        close = "If everything is clear, we can take the next admission step together."
    else:
        close = "I can guide you based on your goal and preferred timeline."

    full = f"{opening} {body} {question} {close}"
    return {
        "opening": opening,
        "core_message": body,
        "question": question,
        "closing": close,
        "full_script": full,
    }

def risk_and_conversion(lead, intent, objections, buying) -> dict[str, Any]:
    status = str(lead.get("status", "New") or "New").strip()
    risk = 20
    reasons = []

    if objections["count"]:
        risk += objections["count"] * 10
        reasons.append("explicit_objection")
    if intent["primary"] == "Early Exploration":
        risk += 15
        reasons.append("low_intent")
    if buying["strength"] >= 70:
        risk -= 25
        reasons.append("strong_buying_signal")
    if status in {"Interested", "Application", "Payment Pending"}:
        risk -= 15
        reasons.append("advanced_status")
    if status == "Lost":
        risk = 100
        reasons.append("lost_status")
    if status == "Enrolled":
        risk = 0
        reasons.append("enrolled_status")

    follow_date = str(lead.get("follow_up_date", "") or "")[:10]
    try:
        due = datetime.strptime(follow_date, "%Y-%m-%d").date() if follow_date else None
    except ValueError:
        due = None
    if due and due < date.today() and status not in {"Enrolled", "Lost"}:
        risk += 20
        reasons.append("overdue_follow_up")

    risk = max(0, min(100, risk))
    conversion = max(0, min(100, 100 - risk))

    if conversion >= 75:
        outlook = "High"
    elif conversion >= 50:
        outlook = "Moderate"
    else:
        outlook = "Low"

    return {
        "risk_score": risk,
        "conversion_score": conversion,
        "conversion_outlook": outlook,
        "risk_reasons": sorted(set(reasons)),
    }

def lead_decision(lead) -> dict[str, Any]:
    intent = detect_intent(lead)
    objections = detect_objections(lead)
    buying = detect_buying_signals(lead)
    strategy = counselling_strategy(lead, intent, objections, buying)
    script = generate_script(lead, strategy, intent, objections, buying)
    risk = risk_and_conversion(lead, intent, objections, buying)

    return {
        "lead_id": str(lead.get("lead_id", "")),
        "name": str(lead.get("name", "")),
        "intent": intent,
        "objections": objections,
        "buying_signals": buying,
        "counselling_strategy": strategy,
        "personalized_script": script,
        "risk_and_conversion": risk,
    }

def rank_decisions(leads=None):
    if leads is None:
        leads = all_leads()
    results = [lead_decision(lead) for lead in leads]
    results.sort(
        key=lambda x: (
            -int(x["buying_signals"]["strength"]),
            -int(x["risk_and_conversion"]["conversion_score"]),
            str(x["name"]).lower(),
        )
    )
    return results

if __name__ == "__main__":
    print("=" * 76)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 1 / BATCH 2")
    print("=" * 76)
    print(f"Data file: {LEADS_FILE}")
    print(f"Leads loaded: {len(all_leads())}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 76)
    for item in rank_decisions():
        print(
            f'{item["lead_id"]:<10} {item["name"][:20]:<20} '
            f'Intent={item["intent"]["primary"]:<20} '
            f'Buy={item["buying_signals"]["strength"]:>3} '
            f'Risk={item["risk_and_conversion"]["risk_score"]:>3} '
            f'Outlook={item["risk_and_conversion"]["conversion_outlook"]}'
        )
    print("=" * 76)
