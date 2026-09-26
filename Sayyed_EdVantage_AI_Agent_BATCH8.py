"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 8
Memory Retrieval + Context Builder + Personalized Response + Follow-up + Channel Strategy
READ-ONLY against data/leads.json.

This batch is intentionally standalone. It does not modify the CRM or leads.json.
"""

from __future__ import annotations
import json
from copy import deepcopy
from datetime import datetime, timedelta
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


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _history_items(lead: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = (
        lead.get("conversation_history"),
        lead.get("history"),
        lead.get("activities"),
        lead.get("activity_history"),
        lead.get("interactions"),
    )
    for item in candidates:
        if isinstance(item, list):
            return [x for x in item if isinstance(x, dict)]
    return []


def retrieve_memory(lead: Dict[str, Any], limit: int = 8) -> Dict[str, Any]:
    """Return only memory relevant to the supplied lead."""
    history = _history_items(lead)
    history = history[-max(1, limit):]

    objections = lead.get("previous_objections", lead.get("objections", []))
    if isinstance(objections, str):
        objections = [objections]
    if not isinstance(objections, list):
        objections = []

    outcomes = lead.get("counselling_outcomes", lead.get("outcomes", []))
    if isinstance(outcomes, str):
        outcomes = [outcomes]
    if not isinstance(outcomes, list):
        outcomes = []

    memory = {
        "lead_id": _text(lead.get("lead_id") or lead.get("id")),
        "name": _text(lead.get("name") or lead.get("student_name")),
        "history": deepcopy(history),
        "previous_objections": deepcopy(objections),
        "counselling_outcomes": deepcopy(outcomes),
        "last_interaction": deepcopy(history[-1]) if history else None,
    }
    return memory


def build_context(lead: Dict[str, Any], memory: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a counselling context from one lead only."""
    if memory is None:
        memory = retrieve_memory(lead)

    analysis = lead.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}

    context = {
        "lead_id": memory["lead_id"],
        "name": memory["name"],
        "current_state": {
            "stage": lead.get("stage", lead.get("status", "Unknown")),
            "score": lead.get("score", analysis.get("score")),
            "priority": lead.get("priority", analysis.get("priority")),
            "intent": analysis.get("intent", lead.get("intent")),
            "buying_signals": analysis.get("buying_signals", lead.get("buying_signals", [])),
            "risk": analysis.get("risk", analysis.get("risk_level")),
            "conversion_blocker": analysis.get(
                "conversion_blocker",
                analysis.get("blocker", lead.get("conversion_blocker")),
            ),
            "next_best_action": analysis.get("next_best_action", lead.get("next_best_action")),
        },
        "memory": memory,
        "profile": {
            "persona": analysis.get("persona", lead.get("persona")),
            "decision_maker": analysis.get("decision_maker", lead.get("decision_maker")),
            "readiness": analysis.get("readiness", lead.get("readiness")),
        },
    }
    return context


def _contains_any(text: str, words: List[str]) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in words)


def personalized_response(context: Dict[str, Any]) -> str:
    """Create a deterministic, memory-aware counselling response."""
    name = context.get("name") or "the student"
    state = context.get("current_state", {})
    memory = context.get("memory", {})
    blocker = _text(state.get("conversion_blocker"))
    intent = _text(state.get("intent"))
    stage = _text(state.get("stage"))
    objections = memory.get("previous_objections", [])

    if blocker:
        focus = f"address the current blocker ({blocker})"
    elif objections:
        focus = f"revisit the previous concern ({_text(objections[-1])})"
    elif intent:
        focus = f"understand and strengthen the {intent.lower()}"
    else:
        focus = "understand the student's current admission requirement"

    return (
        f"Counselling focus for {name}: {focus}. "
        f"Current stage: {stage or 'Unknown'}. "
        "Use the student's prior context before asking questions they have already answered."
    )


def follow_up_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    """Recommend timing and action without writing to the data store."""
    state = context.get("current_state", {})
    score = state.get("score")
    priority = _text(state.get("priority")).lower()
    blocker = _text(state.get("conversion_blocker"))
    action = _text(state.get("next_best_action"))

    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0

    if priority == "high" or numeric_score >= 80:
        timing = "Immediate"
    elif numeric_score >= 50:
        timing = "Within 24 hours"
    else:
        timing = "Within 48–72 hours"

    if blocker:
        reason = f"Resolve blocker: {blocker}"
    elif action:
        reason = action
    else:
        reason = "Continue qualification and counselling"

    return {
        "timing": timing,
        "reason": reason,
        "recommended_action": action or "Counselling follow-up",
    }


def channel_strategy(context: Dict[str, Any]) -> Dict[str, Any]:
    """Select a primary channel and explain why."""
    state = context.get("current_state", {})
    stage = _text(state.get("stage")).lower()
    score = state.get("score")
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0

    if "interested" in stage or numeric_score >= 80:
        primary = "Call"
        secondary = "WhatsApp"
        reason = "Higher-intent leads benefit from direct counselling and rapid objection handling."
    elif "new" in stage:
        primary = "WhatsApp"
        secondary = "Call"
        reason = "A low-friction first contact is appropriate before a deeper counselling call."
    else:
        primary = "WhatsApp"
        secondary = "Call"
        reason = "Use a low-friction follow-up, escalating to a call when engagement increases."

    return {"primary": primary, "secondary": secondary, "reason": reason}


def analyze_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    memory = retrieve_memory(lead)
    context = build_context(lead, memory)
    return {
        "lead_id": context["lead_id"],
        "name": context["name"],
        "memory": memory,
        "context": context,
        "personalized_response": personalized_response(context),
        "follow_up": follow_up_recommendation(context),
        "channel_strategy": channel_strategy(context),
    }


def analyze_all() -> List[Dict[str, Any]]:
    leads = load_leads()
    return [analyze_lead(lead) for lead in leads.values()]


if __name__ == "__main__":
    results = analyze_all()
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 8")
    print("=" * 78)
    print(f"Data file: {DATA_FILE}")
    print(f"Leads loaded: {len(results)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 78)
    for r in results:
        fu = r["follow_up"]
        ch = r["channel_strategy"]
        print(
            f'{r["lead_id"]:<10} {r["name"]:<24} '
            f'Follow-up={fu["timing"]:<18} Primary={ch["primary"]}'
        )
    print("=" * 78)
