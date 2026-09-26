from __future__ import annotations
"""
Sayyed EdVantage AI Agent — Phase 1 / Batch 4
READ-ONLY decision intelligence layer.

Builds on Batch 3 and adds:
1. Refined lead scoring
2. Priority engine
3. Next-best-action engine
4. Objection detection + handling preparation
5. Buying-signal analysis
6. Unified AI action plan

No CRM UI modification and no leads.json modification.
"""

import importlib.util
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
BATCH3_FILE = PROJECT_ROOT / "Sayyed_EdVantage_AI_Agent_BATCH3.py"


def _load_batch3():
    if not BATCH3_FILE.exists():
        raise FileNotFoundError(
            f"Batch 3 file not found: {BATCH3_FILE}. "
            "Paste Sayyed_EdVantage_AI_Agent_BATCH3.py into the agent folder first."
        )
    spec = importlib.util.spec_from_file_location("sayyed_ai_batch3", BATCH3_FILE)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load Batch 3 intelligence layer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B3 = _load_batch3()


def _str(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _combined_text(lead: dict[str, Any], workflow: dict[str, Any]) -> str:
    parts = [
        _str(lead.get("name")),
        _str(lead.get("course_interest")),
        _str(lead.get("status")),
        _str(lead.get("source")),
        _str(lead.get("notes")),
        _str(lead.get("remarks")),
        _str(lead.get("last_outcome")),
        _str(lead.get("next_action")),
    ]
    memory = workflow.get("conversation_memory", {})
    parts.extend(memory.get("recent_interactions", []))
    return " ".join(parts).lower()


def _field_first(lead: dict[str, Any], *names: str) -> Any:
    for name in names:
        if lead.get(name) not in (None, "", []):
            return lead.get(name)
    return None


def refined_scoring(
    lead: dict[str, Any], workflow: dict[str, Any]
) -> dict[str, Any]:
    """
    Deterministic scoring model. It supplements any existing CRM score rather
    than overwriting it. Range: 0–100.
    """
    stage = workflow["stage_intelligence"]["inferred_stage"]
    timing = workflow["follow_up_timing"]
    memory = workflow["conversation_memory"]
    escalation = workflow["escalation"]

    score = 0.0
    reasons: list[str] = []

    stage_points = {
        "New": 15,
        "Contacted": 25,
        "Counselling": 40,
        "Interested": 60,
        "Application": 75,
        "Payment Pending": 90,
        "Enrolled": 100,
        "Lost": 0,
    }
    score += stage_points.get(stage, 20)
    reasons.append(f"stage={stage}")

    buy_signal = buying_signals(lead, workflow)
    score += buy_signal["score_adjustment"]
    reasons.extend(buy_signal["positive_signals"])

    urgency_bonus = {
        "Immediate": 10,
        "High": 7,
        "Medium": 3,
        "Low": 1,
        "None": 0,
    }.get(timing["urgency"], 0)
    score += urgency_bonus
    if urgency_bonus:
        reasons.append(f"follow_up_urgency={timing['urgency']}")

    if memory["interaction_count"] >= 2:
        score += min(8, memory["interaction_count"])
        reasons.append("repeat_interaction")

    if memory["counselling_count"] >= 1:
        score += 5
        reasons.append("counselling_activity")

    if escalation["escalation_level"] == "High":
        score += 5
        reasons.append("high_escalation_signal")
    elif escalation["escalation_level"] == "Medium":
        score += 3
        reasons.append("medium_escalation_signal")

    score = max(0, min(100, round(score)))

    if score >= 80:
        band = "Very High"
    elif score >= 60:
        band = "High"
    elif score >= 40:
        band = "Medium"
    elif score >= 20:
        band = "Low"
    else:
        band = "Very Low"

    return {
        "score": score,
        "band": band,
        "reasons": reasons,
        "model": "Phase1-Batch4-deterministic-v1",
        "base_crm_score": _field_first(lead, "score", "lead_score", "priority_score"),
    }


def priority_engine(
    lead: dict[str, Any], workflow: dict[str, Any], scoring: dict[str, Any]
) -> dict[str, Any]:
    stage = workflow["stage_intelligence"]["inferred_stage"]
    urgency = workflow["follow_up_timing"]["urgency"]
    escalation = workflow["escalation"]["escalation_level"]

    if stage == "Payment Pending" or escalation == "High":
        priority = "Critical"
    elif scoring["score"] >= 75 or urgency == "Immediate":
        priority = "High"
    elif scoring["score"] >= 45 or urgency == "High":
        priority = "Medium"
    else:
        priority = "Low"

    reasons = [
        f"AI score={scoring['score']}",
        f"stage={stage}",
        f"follow-up={urgency}",
        f"escalation={escalation}",
    ]

    return {
        "priority": priority,
        "reasons": reasons,
        "owner_recommendation": (
            "Senior Counsellor" if priority == "Critical"
            else "Assigned Counsellor"
        ),
    }


def next_best_action(
    lead: dict[str, Any], workflow: dict[str, Any]
) -> dict[str, Any]:
    stage = workflow["stage_intelligence"]["inferred_stage"]
    timing = workflow["follow_up_timing"]
    channel = workflow["communication_channel"]["recommended_channel"]
    objections = objection_detection(lead, workflow)
    signals = buying_signals(lead, workflow)

    if stage == "Payment Pending":
        action = "Resolve payment blockers and guide the student to payment completion."
        objective = "Complete payment"
    elif stage == "Application":
        action = "Confirm application/document completion and remove remaining blockers."
        objective = "Advance application"
    elif stage == "Interested":
        if objections["primary_objection"] != "None":
            action = "Address the primary objection, then ask for a specific next commitment."
            objective = "Overcome objection and secure next step"
        else:
            action = "Run a focused counselling conversation and secure a concrete admission next step."
            objective = "Convert interest into action"
    elif stage == "Counselling":
        action = "Qualify the student's goal, fit and decision factors, then schedule the next step."
        objective = "Complete qualification"
    elif stage == "Contacted":
        action = "Re-engage, identify the student's main goal and move the lead into counselling."
        objective = "Progress to counselling"
    elif stage == "New":
        action = "Make the first personalized contact and identify admission intent."
        objective = "Establish contact"
    elif stage == "Enrolled":
        action = "No sales action; maintain a clean handoff/onboarding record."
        objective = "Onboarding"
    else:
        action = "Review the lead and determine whether reactivation is appropriate."
        objective = "Manual review"

    if signals["strong_buying_signal"] and stage not in {"Enrolled", "Lost"}:
        action += " Strong buying signals are present, so avoid a generic follow-up."
    if timing["urgency"] == "Immediate":
        action += " Treat this as time-sensitive."

    return {
        "action": action,
        "objective": objective,
        "channel": channel,
        "timing": timing["recommended_window"],
    }


def objection_detection(
    lead: dict[str, Any], workflow: dict[str, Any]
) -> dict[str, Any]:
    text = _combined_text(lead, workflow)

    patterns = {
        "Fees / Budget": (
            "fee", "fees", "cost", "price", "expensive", "budget",
            "afford", "discount", "emi", "installment"
        ),
        "Timing / Schedule": (
            "timing", "schedule", "batch", "time", "weekend", "weekday",
            "start date", "busy"
        ),
        "Course Fit": (
            "course", "syllabus", "curriculum", "duration", "eligibility",
            "fit", "suitable"
        ),
        "Career / Outcome": (
            "job", "career", "placement", "salary", "outcome", "scope"
        ),
        "Parent / Family Decision": (
            "parent", "parents", "family", "father", "mother", "guardian",
            "discuss with"
        ),
        "Trust / Information": (
            "genuine", "trust", "review", "proof", "certificate",
            "accreditation", "details"
        ),
    }

    hits: list[tuple[str, int]] = []
    for label, words in patterns.items():
        count = sum(1 for word in words if word in text)
        if count:
            hits.append((label, count))

    hits.sort(key=lambda x: (-x[1], x[0]))

    if not hits:
        return {
            "primary_objection": "None",
            "detected_objections": [],
            "confidence": 55,
            "handling_guidance": "No clear objection detected. Ask an open question before assuming a blocker.",
        }

    primary = hits[0][0]
    guidance = {
        "Fees / Budget": "Clarify total value, fee structure and payment options before discussing discounts.",
        "Timing / Schedule": "Offer suitable batch or scheduling alternatives and confirm the student's preferred timing.",
        "Course Fit": "Clarify goals, syllabus fit, duration and eligibility using the student's stated objective.",
        "Career / Outcome": "Connect the course to realistic skills, outcomes and the student's career goal.",
        "Parent / Family Decision": "Understand the family decision process and provide concise information the decision-maker needs.",
        "Trust / Information": "Provide transparent programme, process and credential information and avoid unsupported promises.",
    }[primary]

    return {
        "primary_objection": primary,
        "detected_objections": [x[0] for x in hits],
        "confidence": min(95, 60 + len(hits) * 8),
        "handling_guidance": guidance,
    }


def buying_signals(
    lead: dict[str, Any], workflow: dict[str, Any]
) -> dict[str, Any]:
    text = _combined_text(lead, workflow)

    strong = {
        "payment": ("payment", "pay", "payment link", "installment"),
        "application": ("apply", "application", "form", "documents", "document"),
        "admission": ("admission", "enroll", "enrol", "register", "join"),
        "specific_timing": ("when can i start", "start date", "next batch", "batch"),
        "decision": ("ready", "finalize", "confirm", "book", "reserve"),
    }
    weak = {
        "information": ("details", "information", "syllabus", "brochure"),
        "comparison": ("compare", "other institute", "alternative"),
    }

    strong_hits: list[str] = []
    weak_hits: list[str] = []

    for label, words in strong.items():
        if any(word in text for word in words):
            strong_hits.append(label)

    for label, words in weak.items():
        if any(word in text for word in words):
            weak_hits.append(label)

    score_adjustment = min(20, len(strong_hits) * 5) + min(5, len(weak_hits) * 2)

    # Existing stage is also evidence, but we avoid double-counting too heavily.
    stage = workflow["stage_intelligence"]["inferred_stage"]
    if stage in {"Interested", "Application", "Payment Pending"}:
        score_adjustment = min(25, score_adjustment + 5)

    if len(strong_hits) >= 2:
        strength = "Strong"
    elif strong_hits:
        strength = "Moderate"
    elif weak_hits:
        strength = "Early"
    else:
        strength = "None"

    return {
        "strong_buying_signal": len(strong_hits) >= 2 or stage in {"Application", "Payment Pending"},
        "strength": strength,
        "strong_signals": strong_hits,
        "weak_signals": weak_hits,
        "positive_signals": [f"buying:{x}" for x in strong_hits],
        "score_adjustment": score_adjustment,
    }


def ai_action_plan(
    lead: dict[str, Any],
    workflow: dict[str, Any],
    scoring: dict[str, Any],
    priority: dict[str, Any],
    action: dict[str, Any],
    objections: dict[str, Any],
    signals: dict[str, Any],
) -> dict[str, Any]:
    name = _str(lead.get("name")) or "Student"
    course = _str(lead.get("course_interest")) or "course not specified"

    steps = [
        f"1. Contact {name} via {action['channel']} {action['timing'].lower()}.",
        f"2. Objective: {action['objective']}.",
    ]

    if objections["primary_objection"] != "None":
        steps.append(
            f"3. Address {objections['primary_objection']} using: "
            f"{objections['handling_guidance']}"
        )
    else:
        steps.append("3. Ask one diagnostic question before presenting the next offer.")

    if signals["strong_buying_signal"]:
        steps.append("4. Ask for a specific commitment or next admission step.")
    else:
        steps.append("4. Establish the student's decision criteria and next follow-up.")

    if priority["priority"] == "Critical":
        steps.append("5. Escalate to a senior counsellor if the blocker cannot be resolved promptly.")

    return {
        "lead": name,
        "course": course,
        "priority": priority["priority"],
        "ai_score": scoring["score"],
        "headline": (
            f"{priority['priority']} priority: {name} — "
            f"{action['objective']}."
        ),
        "steps": steps,
        "success_condition": (
            "A concrete next admission commitment is recorded."
            if workflow["stage_intelligence"]["inferred_stage"] != "Enrolled"
            else "Clean onboarding handoff is completed."
        ),
    }


def analyze_lead(lead: dict[str, Any]) -> dict[str, Any]:
    workflow = B3.workflow_intelligence(lead)
    scoring = refined_scoring(lead, workflow)
    priority = priority_engine(lead, workflow, scoring)
    action = next_best_action(lead, workflow)
    objections = objection_detection(lead, workflow)
    signals = buying_signals(lead, workflow)
    plan = ai_action_plan(
        lead, workflow, scoring, priority, action, objections, signals
    )

    return {
        "lead_id": _str(lead.get("lead_id")),
        "name": _str(lead.get("name")),
        "workflow_intelligence": workflow,
        "refined_scoring": scoring,
        "priority": priority,
        "next_best_action": action,
        "objection_detection": objections,
        "buying_signals": signals,
        "ai_action_plan": plan,
    }


def all_analysis() -> list[dict[str, Any]]:
    return [analyze_lead(lead) for lead in B3.all_leads()]


if __name__ == "__main__":
    leads = B3.all_leads()
    print("=" * 82)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 1 / BATCH 4")
    print("=" * 82)
    print(f"Data file: {B3.LEADS_FILE}")
    print(f"Leads loaded: {len(leads)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 82)

    for item in all_analysis():
        print(
            f'{item["lead_id"]:<10} {item["name"][:20]:<20} '
            f'Score={item["refined_scoring"]["score"]:<3} '
            f'Priority={item["priority"]["priority"]:<8} '
            f'Action={item["next_best_action"]["objective"]}'
        )

    print("=" * 82)
