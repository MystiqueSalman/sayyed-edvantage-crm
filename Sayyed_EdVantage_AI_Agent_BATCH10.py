"""
Sayyed EdVantage AI Agent — Phase 2 / Batch 10
Communication orchestration and response drafting.

Builds on Batch 9 intelligence:
- selects communication objective/channel
- creates personalized draft
- chooses follow-up timing
- creates counsellor action checklist
- preserves READ-ONLY data behavior

No external messaging is sent and leads.json is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import sys

BASE_DIR = Path(__file__).resolve().parent
BATCH9 = BASE_DIR / "Sayyed_EdVantage_AI_Agent_BATCH9.py"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Sayyed_EdVantage_AI_Agent_BATCH9 as batch9


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lead_channel(lead: Dict[str, Any]) -> str:
    channel = _text(lead.get("preferred_channel") or lead.get("channel"))
    return channel if channel else "WhatsApp"


def _timing(lead: Dict[str, Any], intelligence: Dict[str, Any]) -> str:
    urgency = _text(
        batch9.analysis(lead)
        .get("workflow_intelligence", {})
        .get("follow_up_timing", {})
        .get("urgency")
    ).lower()

    if intelligence["handoff"]["level"] == "Immediate":
        return "Immediate"
    if urgency == "immediate":
        return "Immediate"
    if intelligence["refined_conversion"]["conversion_band"] == "High":
        return "Within 24 hours"
    if intelligence["refined_conversion"]["conversion_band"] == "Medium":
        return "Within 48 hours"
    return "Within 3 days"


def communication_plan(lead: Dict[str, Any]) -> Dict[str, Any]:
    intel = batch9.analyze_lead(lead)
    name = _text(lead.get("name") or lead.get("student_name")) or "there"
    channel = _lead_channel(lead)
    objection = intel["objection_intelligence"]
    response = intel["objection_response"]
    questions = intel["adaptive_questions"]
    intent = intel["refined_intent"]["intent"]
    handoff = intel["handoff"]

    if objection["detected"]:
        objective = "Resolve objection and secure the next admission step"
        body = (
            f"Hi {name}, thank you for sharing your concern. "
            f"I understand that {objection['objection']} is important. "
            f"{response['response']} "
            f"Could we clarify this together and decide the most suitable next step?"
        )
    else:
        objective = "Discover needs and advance the admission conversation"
        body = (
            f"Hi {name}, I wanted to follow up regarding your admission enquiry. "
            f"To guide you correctly, I'd like to understand your priorities and timeline. "
            f"Would you be comfortable sharing what matters most in your decision?"
        )

    checklist = [
        f"Use {channel} as the recommended first channel.",
        f"Lead with the objective: {objective}.",
        "Ask only the most relevant adaptive question; do not overload the student.",
        "Record the outcome after the conversation.",
    ]

    if handoff["handoff_required"]:
        checklist.append(
            "Escalate to the senior counsellor before making a commitment or promise."
        )

    return {
        "lead_id": intel["lead_id"],
        "name": name,
        "channel": channel,
        "objective": objective,
        "timing": _timing(lead, intel),
        "intent": intent,
        "draft_message": body,
        "suggested_questions": questions,
        "counsellor_checklist": checklist,
        "handoff": handoff,
        "send_status": "NOT_SENT",
    }


def build_all_plans() -> List[Dict[str, Any]]:
    leads = batch9.load_leads()
    return [communication_plan(lead) for lead in leads.values()]


if __name__ == "__main__":
    plans = build_all_plans()

    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 2 / BATCH 10")
    print("=" * 78)
    print(f"Data file: {batch9.DATA_FILE}")
    print(f"Leads loaded: {len(plans)}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("MESSAGE STATUS: drafts only — nothing is sent.")
    print("-" * 78)

    for plan in plans:
        print(
            f'{plan["lead_id"]:<10} {plan["name"]:<24} '
            f'Channel={plan["channel"]:<9} '
            f'Timing={plan["timing"]:<14} '
            f'Handoff={plan["handoff"]["level"]}'
        )

    print("=" * 78)
