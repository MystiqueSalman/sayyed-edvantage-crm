"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 9
Objection-response intelligence + adaptive questions + intent/conversion refinement
+ counsellor talking points + safe human-handoff recommendation.

Standalone, deterministic, READ-ONLY against data/leads.json.
"""

from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "leads.json"


def load_leads() -> Dict[str, Dict[str, Any]]:
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Expected leads.json to contain an object keyed by lead ID.")
    return data


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def history(lead: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("conversation_history", "history", "activities",
                "activity_history", "interactions"):
        value = lead.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def objections(lead: Dict[str, Any]) -> List[str]:
    value = lead.get("previous_objections", lead.get("objections", []))
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [text(x) for x in value] if isinstance(value, list) else []


def analysis(lead: Dict[str, Any]) -> Dict[str, Any]:
    value = lead.get("analysis", {})
    return value if isinstance(value, dict) else {}


def detect_objection(lead: Dict[str, Any]) -> Dict[str, Any]:
    a = analysis(lead)
    previous = objections(lead)
    blocker = text(
        a.get("conversion_blocker")
        or a.get("blocker")
        or lead.get("conversion_blocker")
    )

    if blocker:
        category = "Admission / Conversion Blocker"
        severity = "High" if any(
            word in blocker.lower()
            for word in ("fee", "budget", "eligibility", "deadline", "document")
        ) else "Medium"
        return {
            "detected": True,
            "category": category,
            "severity": severity,
            "objection": blocker,
            "source": "current blocker",
        }

    if previous:
        return {
            "detected": True,
            "category": "Previous Objection",
            "severity": "Medium",
            "objection": previous[-1],
            "source": "lead memory",
        }

    return {
        "detected": False,
        "category": "None",
        "severity": "Low",
        "objection": "",
        "source": "none",
    }


def objection_response(lead: Dict[str, Any], objection: Dict[str, Any]) -> Dict[str, str]:
    obj = text(objection.get("objection"))
    low = obj.lower()

    if not objection.get("detected"):
        return {
            "approach": "Discover",
            "response": "Ask what is preventing the student from moving forward and listen before proposing a solution.",
        }

    if any(x in low for x in ("fee", "fees", "budget", "cost", "price")):
        approach = "Clarify value and payment feasibility"
        response = "Acknowledge the fee concern, clarify the student's budget constraint, explain relevant value, and discuss available payment options without making unsupported promises."
    elif any(x in low for x in ("eligibility", "qualification", "criteria")):
        approach = "Clarify eligibility"
        response = "Confirm the student's academic details and explain the applicable eligibility requirement before recommending the next step."
    elif any(x in low for x in ("parent", "family", "decision maker")):
        approach = "Support the decision-maker"
        response = "Identify the decision-maker's concern, prepare concise evidence and invite the appropriate decision-maker into the counselling conversation."
    elif any(x in low for x in ("time", "timing", "busy", "schedule")):
        approach = "Reduce timing friction"
        response = "Understand the student's schedule, identify a realistic next step, and offer a follow-up time that matches their availability."
    else:
        approach = "Clarify and resolve"
        response = "Ask one focused question to understand the concern, address the specific issue, and confirm whether the concern is resolved."

    return {"approach": approach, "response": response}


def adaptive_questions(lead: Dict[str, Any], objection: Dict[str, Any]) -> List[str]:
    a = analysis(lead)
    stage = text(lead.get("stage", lead.get("status", "Unknown"))).lower()
    questions: List[str] = []

    if objection.get("detected"):
        questions.append(f"What specifically is holding you back regarding {objection['objection']}?")
    elif "new" in stage:
        questions.append("What course or admission outcome are you looking for?")
        questions.append("What is your preferred timeline for starting?")
    else:
        questions.append("What is the most important factor in your admission decision?")

    if not text(a.get("decision_maker")):
        questions.append("Who else will be involved in the final admission decision?")

    if not text(a.get("readiness")):
        questions.append("How ready are you to take the next admission step?")

    return questions[:3]


def refined_intent(lead: Dict[str, Any]) -> Dict[str, Any]:
    a = analysis(lead)
    raw = text(a.get("intent") or lead.get("intent"))
    signals = a.get("buying_signals", lead.get("buying_signals", []))
    if not isinstance(signals, list):
        signals = [signals] if signals else []

    if any("admission" in text(s).lower() for s in signals):
        confidence = "High"
        intent = "Admission Intent"
    elif raw:
        confidence = "High" if len(signals) >= 2 else "Medium"
        intent = raw
    else:
        confidence = "Low"
        intent = "Early Exploration"

    return {"intent": intent, "confidence": confidence, "signals": deepcopy(signals)}


def refined_conversion(lead: Dict[str, Any], objection: Dict[str, Any]) -> Dict[str, Any]:
    a = analysis(lead)
    score = a.get("score", lead.get("score", 0))
    try:
        base = float(score)
    except (TypeError, ValueError):
        base = 0.0

    if objection.get("severity") == "High":
        adjustment = -15
    elif objection.get("severity") == "Medium":
        adjustment = -5
    else:
        adjustment = 0

    refined = max(0, min(100, round(base + adjustment)))
    band = "High" if refined >= 70 else "Medium" if refined >= 40 else "Low"
    return {
        "base_score": round(base),
        "adjustment": adjustment,
        "refined_score": refined,
        "conversion_band": band,
    }


def counsellor_talking_points(
    lead: Dict[str, Any],
    objection: Dict[str, Any],
    intent: Dict[str, Any],
) -> List[str]:
    name = text(lead.get("name") or lead.get("student_name")) or "the student"
    points = [
        f"Address {name} using the known lead context rather than repeating already answered questions.",
        f"Confirm the student's {intent['intent'].lower()} and the immediate admission objective.",
    ]
    if objection.get("detected"):
        points.append(f"Resolve the stated concern first: {objection['objection']}.")
    else:
        points.append("Discover the main concern before presenting a solution.")
    points.append("End with one clear, mutually agreed next step.")
    return points


def handoff_recommendation(
    lead: Dict[str, Any],
    objection: Dict[str, Any],
    conversion: Dict[str, Any],
) -> Dict[str, Any]:
    a = analysis(lead)
    risk = text(a.get("risk", a.get("risk_level"))).lower()
    priority = text(a.get("priority", lead.get("priority"))).lower()

    reasons: List[str] = []
    if objection.get("severity") == "High":
        reasons.append("high-severity conversion blocker")
    if risk in {"high", "critical"}:
        reasons.append("high-risk lead")
    if priority == "high" and conversion["conversion_band"] == "High":
        reasons.append("high-value/high-intent lead")

    if risk in {"high", "critical"} or objection.get("severity") == "High":
        level = "Immediate"
        required = True
    elif reasons:
        level = "Priority"
        required = False
    else:
        level = "Standard"
        required = False

    return {
        "handoff_required": required,
        "level": level,
        "reasons": reasons,
        "owner": "Senior counsellor" if required else "Assigned counsellor",
    }


def analyze_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    lead_id = text(lead.get("lead_id") or lead.get("id"))
    name = text(lead.get("name") or lead.get("student_name"))
    objection = detect_objection(lead)
    response = objection_response(lead, objection)
    questions = adaptive_questions(lead, objection)
    intent = refined_intent(lead)
    conversion = refined_conversion(lead, objection)
    talking_points = counsellor_talking_points(lead, objection, intent)
    handoff = handoff_recommendation(lead, objection, conversion)

    return {
        "lead_id": lead_id,
        "name": name,
        "objection_intelligence": objection,
        "objection_response": response,
        "adaptive_questions": questions,
        "refined_intent": intent,
        "refined_conversion": conversion,
        "counsellor_talking_points": talking_points,
        "handoff": handoff,
    }


def analyze_all() -> List[Dict[str, Any]]:
    return [analyze_lead(lead) for lead in load_leads().values()]


if __name__ == "__main__":
    results = analyze_all()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 9")
    print("=" * 78)
    print(f"Data file: {DATA_FILE}")
    print(f"Leads loaded: {len(results)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 78)
    for r in results:
        o = r["objection_intelligence"]
        c = r["refined_conversion"]
        h = r["handoff"]
        print(
            f'{r["lead_id"]:<10} {r["name"]:<24} '
            f'Intent={r["refined_intent"]["intent"]:<20} '
            f'Conversion={c["refined_score"]:>3} '
            f'Objection={o["severity"]:<6} '
            f'Handoff={h["level"]}'
        )
    print("=" * 78)
