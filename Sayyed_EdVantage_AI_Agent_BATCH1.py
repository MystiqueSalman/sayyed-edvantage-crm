from __future__ import annotations
"""
Sayyed EdVantage AI Agent — Phase 1 / Batch 1
READ-ONLY CRM intelligence layer.
Does not change the existing CRM UI or leads.json.
"""
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LEADS_FILE = PROJECT_ROOT / "data" / "leads.json"

STATUS_SCORE = {
    "New": 10, "Contacted": 20, "Counselling": 55, "Interested": 70,
    "Application": 80, "Payment Pending": 90, "Enrolled": 100, "Lost": 0,
}
HIGH_INTENT_WORDS = {
    "admission","enroll","enrollment","join","fees","fee","payment",
    "apply","application","batch","start","when","schedule","interested",
    "details","course","urgent",
}
MEDIUM_INTENT_WORDS = {
    "information","info","brochure","syllabus","duration","career",
    "job","certificate","eligibility","details",
}
OBJECTION_WORDS = {
    "expensive","cost","fee","fees","later","think","family","parent",
    "parents","not sure","doubt","difficult","busy",
}
COMPLETED_STATUSES = {"Enrolled", "Lost"}

def load_leads() -> dict[str, dict[str, Any]]:
    if not LEADS_FILE.exists():
        return {}
    try:
        data = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}

def get_lead(lead_id: str):
    return load_leads().get(str(lead_id))

def get_all_leads() -> list[dict[str, Any]]:
    return list(load_leads().values())

def _text(*values: Any) -> str:
    return " ".join(str(v or "").strip() for v in values if str(v or "").strip()).lower()

def _parse_date(value: Any):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None

def _history_count(lead, key):
    value = lead.get(key, [])
    return len(value) if isinstance(value, list) else 0

def _has_recent_contact(lead):
    raw = str(lead.get("last_contacted_at", "") or "").strip()
    if not raw:
        return False
    try:
        contacted = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return (date.today() - contacted).days <= 3

def calculate_lead_score(lead) -> int:
    status = str(lead.get("status", "New") or "New").strip()
    if status == "Lost":
        return 0
    if status == "Enrolled":
        return 100

    score = STATUS_SCORE.get(status, 10)
    message = _text(
        lead.get("message"),
        lead.get("follow_up_notes"),
        lead.get("course_interest"),
    )

    high_hits = sum(1 for word in HIGH_INTENT_WORDS if word in message)
    medium_hits = sum(1 for word in MEDIUM_INTENT_WORDS if word in message)
    objection_hits = sum(1 for word in OBJECTION_WORDS if word in message)

    if str(lead.get("phone", "")).strip():
        score += 5
    if str(lead.get("email", "")).strip():
        score += 3
    if str(lead.get("course_interest", "")).strip():
        score += 5
    if str(lead.get("education", "")).strip():
        score += 2

    score += min(high_hits * 4, 16)
    score += min(medium_hits * 2, 6)
    score -= min(objection_hits * 2, 8)

    score += min(_history_count(lead, "counselling_history") * 4, 12)
    score += min(_history_count(lead, "follow_up_history") * 2, 6)

    follow_date = _parse_date(lead.get("follow_up_date"))
    if follow_date:
        days = (follow_date - date.today()).days
        if days < 0:
            score += 8
        elif days == 0:
            score += 6
        elif days <= 3:
            score += 3

    if _has_recent_contact(lead):
        score += 2

    return max(0, min(100, int(score)))

def classify_lead(score: int, lead) -> str:
    status = str(lead.get("status", "New") or "New").strip()
    if status == "Enrolled":
        return "Enrolled"
    if status == "Lost":
        return "Lost"
    if score >= 75:
        return "Hot"
    if score >= 45:
        return "Warm"
    return "Cold"

def calculate_priority(score: int, lead) -> str:
    status = str(lead.get("status", "New") or "New").strip()
    follow_date = _parse_date(lead.get("follow_up_date"))
    if status in COMPLETED_STATUSES:
        return "Low"

    overdue = bool(follow_date and follow_date < date.today())
    due_today = bool(follow_date and follow_date == date.today())

    if overdue and score >= 45:
        return "Critical"
    if score >= 80 or (due_today and score >= 45):
        return "High"
    if score >= 45 or due_today:
        return "Medium"
    return "Low"

def next_best_action(lead) -> str:
    status = str(lead.get("status", "New") or "New").strip()
    follow_date = _parse_date(lead.get("follow_up_date"))
    payment_status = str(lead.get("payment_status", "Not Started") or "Not Started").strip()

    if status == "Enrolled":
        return "Admission completion / onboarding"
    if status == "Lost":
        return "No immediate action"
    if follow_date and follow_date < date.today():
        return "Call overdue follow-up"
    if follow_date and follow_date == date.today():
        return "Complete today's follow-up"
    if status == "New":
        return "Initial contact"
    if status == "Contacted":
        return "Schedule counselling"
    if status == "Counselling":
        return "Follow up on counselling outcome"
    if status == "Interested":
        return "Address objections and move toward application"
    if status == "Application":
        return "Check application / documents"
    if status == "Payment Pending":
        return "Discuss payment and admission completion"
    if payment_status in {"Pending", "Partial"}:
        return "Follow up on pending payment"
    return "Review lead and choose next action"

def activity_history_summary(lead):
    def count(key):
        value = lead.get(key, [])
        return len(value) if isinstance(value, list) else 0
    return {
        "status_changes": count("status_history"),
        "counselling_sessions": count("counselling_history"),
        "follow_up_actions": count("follow_up_history"),
        "payments_recorded": count("payment_history"),
        "last_contacted_at": lead.get("last_contacted_at", ""),
        "created_at": lead.get("created_at", ""),
        "updated_at": lead.get("updated_at", ""),
    }

def lead_intelligence(lead):
    score = calculate_lead_score(lead)
    return {
        "lead_id": str(lead.get("lead_id", "")),
        "name": str(lead.get("name", "")),
        "status": str(lead.get("status", "New") or "New"),
        "score": score,
        "classification": classify_lead(score, lead),
        "priority": calculate_priority(score, lead),
        "next_best_action": next_best_action(lead),
        "activity": activity_history_summary(lead),
    }

def intelligence_panel_data(lead_id):
    lead = get_lead(lead_id)
    return lead_intelligence(lead) if lead else None

def rank_leads(leads=None):
    if leads is None:
        leads = get_all_leads()
    priority_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    result = [lead_intelligence(lead) for lead in leads]
    result.sort(key=lambda x: (
        priority_rank.get(x["priority"], 9),
        -int(x["score"]),
        str(x["name"]).lower(),
    ))
    return result

if __name__ == "__main__":
    print("=" * 72)
    print("SAYYED EDVANTAGE AI AGENT — PHASE 1 / BATCH 1")
    print("=" * 72)
    print(f"Data file: {LEADS_FILE}")
    print(f"Leads loaded: {len(get_all_leads())}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-" * 72)
    for item in rank_leads():
        print(
            f'{item["lead_id"]:<10} {item["name"][:24]:<24} '
            f'Score={item["score"]:>3} {item["classification"]:<9} '
            f'{item["priority"]:<8} {item["next_best_action"]}'
        )
    print("=" * 72)
