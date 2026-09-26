from __future__ import annotations
"""
Sayyed EdVantage AI Agent — Phase 1 / Batch 3
READ-ONLY workflow intelligence layer.

Adds:
1. Conversation memory
2. True admission-stage intelligence
3. Follow-up timing intelligence
4. Recommended communication channel
5. Escalation detection
6. Counsellor-ready lead briefing

No CRM UI or leads.json modification.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LEADS_FILE = PROJECT_ROOT / "data" / "leads.json"

STAGE_ORDER = {
    "New": 0,
    "Contacted": 1,
    "Counselling": 2,
    "Interested": 3,
    "Application": 4,
    "Payment Pending": 5,
    "Enrolled": 6,
    "Lost": 99,
}

def load_leads() -> dict[str, dict[str, Any]]:
    if not LEADS_FILE.exists():
        return {}
    try:
        data = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}

def all_leads():
    return list(load_leads().values())

def _str(value):
    return str(value or "").strip()

def _list(value):
    return value if isinstance(value, list) else []

def _date(value):
    raw = _str(value)[:10]
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None

def _datetime(value):
    raw = _str(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None

def _combined_history(lead):
    chunks = []
    for key in (
        "status_history",
        "counselling_history",
        "follow_up_history",
        "payment_history",
    ):
        for item in _list(lead.get(key)):
            if isinstance(item, dict):
                parts = []
                for field in ("date", "created_at", "timestamp", "status", "outcome", "notes", "note", "message", "remarks", "channel"):
                    if item.get(field):
                        parts.append(_str(item.get(field)))
                chunks.append(" | ".join(parts))
            else:
                chunks.append(_str(item))
    return [x for x in chunks if x]

def conversation_memory(lead) -> dict[str, Any]:
    history = _combined_history(lead)
    counselling = _list(lead.get("counselling_history"))
    followups = _list(lead.get("follow_up_history"))
    statuses = _list(lead.get("status_history"))
    payments = _list(lead.get("payment_history"))

    last_status = None
    if statuses:
        last = statuses[-1]
        last_status = _str(last.get("status") if isinstance(last, dict) else last)

    recent = history[-5:]
    topics = []
    text = " ".join(history).lower()
    topic_map = {
        "fees/payment": ("fee", "fees", "payment", "pay"),
        "course": ("course", "syllabus", "curriculum", "duration"),
        "timing": ("time", "timing", "schedule", "batch", "start"),
        "career": ("career", "job", "placement"),
        "family": ("parent", "parents", "family"),
        "documents": ("document", "certificate", "marksheet", "application"),
    }
    for topic, words in topic_map.items():
        if any(word in text for word in words):
            topics.append(topic)

    return {
        "interaction_count": len(history),
        "counselling_count": len(counselling),
        "follow_up_count": len(followups),
        "status_change_count": len(statuses),
        "payment_event_count": len(payments),
        "last_known_status": last_status,
        "recent_interactions": recent,
        "topics_detected": topics,
        "memory_available": bool(history),
    }

def infer_true_stage(lead, memory) -> dict[str, Any]:
    status = _str(lead.get("status")) or "New"
    stated_rank = STAGE_ORDER.get(status, 0)
    evidence = [f"crm_status:{status}"]

    text = " ".join(memory["recent_interactions"]).lower()
    if any(x in text for x in ("payment", "pay now", "payment link")):
        evidence.append("payment_language")
    if any(x in text for x in ("apply", "application", "documents")):
        evidence.append("application_language")
    if any(x in text for x in ("join", "enroll", "admission", "register")):
        evidence.append("admission_language")
    if memory["counselling_count"]:
        evidence.append("counselling_history")
    if memory["follow_up_count"]:
        evidence.append("follow_up_history")

    inferred = status
    if status == "New" and memory["interaction_count"] > 0:
        inferred = "Contacted"
    if status in {"Contacted", "Counselling"} and (
        "admission_language" in evidence or "application_language" in evidence
    ):
        inferred = "Interested"
    if status == "Interested" and "application_language" in evidence:
        inferred = "Application"
    if status == "Application" and "payment_language" in evidence:
        inferred = "Payment Pending"

    confidence = 65
    if inferred != status:
        confidence += 15
    if len(evidence) >= 3:
        confidence += 10
    confidence = min(95, confidence)

    return {
        "crm_stage": status,
        "inferred_stage": inferred,
        "stage_changed_by_agent": inferred != status,
        "confidence": confidence,
        "evidence": evidence,
    }

def follow_up_timing(lead, stage) -> dict[str, Any]:
    status = stage["inferred_stage"]
    due = _date(lead.get("follow_up_date"))
    today = date.today()

    if status in {"Enrolled", "Lost"}:
        return {
            "urgency": "None",
            "recommended_window": "No sales follow-up required",
            "recommended_date": None,
            "reason": "Lead is in a completed state.",
        }

    if due:
        if due < today:
            days = (today - due).days
            return {
                "urgency": "Immediate",
                "recommended_window": "Today",
                "recommended_date": today.isoformat(),
                "reason": f"Follow-up is overdue by {days} day(s).",
            }
        if due == today:
            return {
                "urgency": "Immediate",
                "recommended_window": "Today",
                "recommended_date": today.isoformat(),
                "reason": "Follow-up is due today.",
            }
        if (due - today).days <= 2:
            return {
                "urgency": "High",
                "recommended_window": "Within 48 hours",
                "recommended_date": due.isoformat(),
                "reason": "Follow-up is approaching.",
            }

    windows = {
        "New": ("High", "Within 24 hours", "New leads should receive prompt first contact."),
        "Contacted": ("Medium", "Within 1–2 days", "Continue qualification while interest is fresh."),
        "Counselling": ("High", "Within 24–48 hours", "Counselling should lead to a clear next step."),
        "Interested": ("High", "Within 24 hours", "Interested leads should not be left without a decision path."),
        "Application": ("High", "Within 24 hours", "Application-stage leads need progress confirmation."),
        "Payment Pending": ("Immediate", "Today", "Payment-stage leads need a clear completion path."),
    }
    urgency, window, reason = windows.get(status, ("Medium", "Within 2–3 days", "Maintain momentum."))
    days = 0 if urgency == "Immediate" else 1 if urgency == "High" else 2
    recommended = (today + timedelta(days=days)).isoformat()

    return {
        "urgency": urgency,
        "recommended_window": window,
        "recommended_date": recommended,
        "reason": reason,
    }

def communication_channel(lead, stage, memory) -> dict[str, Any]:
    text = " ".join(memory["recent_interactions"]).lower()
    status = stage["inferred_stage"]

    if status == "Payment Pending":
        channel = "Call"
        reason = "Payment-stage conversations benefit from immediate clarification."
    elif any(x in text for x in ("call me", "call back", "phone", "call")):
        channel = "Call"
        reason = "The interaction history indicates phone contact."
    elif any(x in text for x in ("whatsapp", "message", "text")):
        channel = "WhatsApp"
        reason = "The interaction history indicates messaging."
    elif status in {"Interested", "Application"}:
        channel = "Call"
        reason = "Higher-intent stages benefit from direct conversation."
    elif lead.get("email") and not lead.get("phone"):
        channel = "Email"
        reason = "Email is the available direct contact route."
    elif lead.get("phone"):
        channel = "WhatsApp"
        reason = "Phone contact is available and messaging is suitable for early-stage follow-up."
    else:
        channel = "Manual Review"
        reason = "No reliable direct channel is available."

    return {"recommended_channel": channel, "reason": reason}

def escalation_detection(lead, stage, timing, memory) -> dict[str, Any]:
    status = stage["inferred_stage"]
    reasons = []
    level = "None"

    if status == "Payment Pending":
        reasons.append("payment_stage")
    if timing["urgency"] == "Immediate":
        reasons.append("time_sensitive")
    if memory["interaction_count"] >= 6 and status not in {"Enrolled", "Lost"}:
        reasons.append("high_interaction_count")
    if len(memory["topics_detected"]) >= 4:
        reasons.append("multiple_topics")
    if "family" in memory["topics_detected"] and status in {"Interested", "Application"}:
        reasons.append("family_decision_factor")

    if "payment_stage" in reasons and "time_sensitive" in reasons:
        level = "High"
    elif len(reasons) >= 2:
        level = "Medium"
    elif reasons:
        level = "Low"

    return {
        "escalation_level": level,
        "escalate": level in {"High", "Medium"},
        "reasons": reasons,
        "recommended_owner": "Senior Counsellor" if level in {"High", "Medium"} else "Assigned Counsellor",
    }

def counsellor_brief(lead, memory, stage, timing, channel, escalation) -> dict[str, Any]:
    name = _str(lead.get("name")) or "Student"
    course = _str(lead.get("course_interest")) or "course not specified"
    topics = ", ".join(memory["topics_detected"]) if memory["topics_detected"] else "no clear topic history"

    headline = (
        f"{name} is currently at {stage['inferred_stage']} stage for {course}. "
        f"Recommended contact: {channel['recommended_channel']}. "
        f"Follow-up: {timing['recommended_window']}."
    )

    preparation = [
        f"Confirm the student's current goal and next admission step.",
        f"Review known discussion topics: {topics}.",
        f"Use a {channel['recommended_channel'].lower()}-first approach.",
    ]
    if escalation["escalate"]:
        preparation.append("Consider senior-counsellor involvement before closing the next commitment.")

    return {
        "headline": headline,
        "preparation_points": preparation,
        "last_known_context": memory["recent_interactions"][-2:],
        "escalation_note": (
            "Escalation recommended." if escalation["escalate"]
            else "No escalation currently required."
        ),
    }

def workflow_intelligence(lead) -> dict[str, Any]:
    memory = conversation_memory(lead)
    stage = infer_true_stage(lead, memory)
    timing = follow_up_timing(lead, stage)
    channel = communication_channel(lead, stage, memory)
    escalation = escalation_detection(lead, stage, timing, memory)
    brief = counsellor_brief(lead, memory, stage, timing, channel, escalation)

    return {
        "lead_id": _str(lead.get("lead_id")),
        "name": _str(lead.get("name")),
        "conversation_memory": memory,
        "stage_intelligence": stage,
        "follow_up_timing": timing,
        "communication_channel": channel,
        "escalation": escalation,
        "counsellor_brief": brief,
    }

def all_workflow_intelligence():
    return [workflow_intelligence(lead) for lead in all_leads()]

if __name__ == "__main__":
    print("=" * 78)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 1 / BATCH 3")
    print("=" * 78)
    print(f"Data file: {LEADS_FILE}")
    print(f"Leads loaded: {len(all_leads())}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 78)
    for item in all_workflow_intelligence():
        print(
            f'{item["lead_id"]:<10} {item["name"][:20]:<20} '
            f'Stage={item["stage_intelligence"]["inferred_stage"]:<18} '
            f'Follow-up={item["follow_up_timing"]["urgency"]:<9} '
            f'Channel={item["communication_channel"]["recommended_channel"]:<12} '
            f'Escalation={item["escalation"]["escalation_level"]}'
        )
    print("=" * 78)
