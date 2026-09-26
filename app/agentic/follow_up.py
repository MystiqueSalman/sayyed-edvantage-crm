from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from app.leads import lead_manager
from app.agentic.models import AgentContext, Task


def _due(lead: dict[str, Any]) -> bool:
    value = str(lead.get("follow_up_date", "")).strip()
    if not value:
        return False
    try:
        return date.fromisoformat(value[:10]) <= date.today()
    except ValueError:
        return False


def _lead_summary(lead: dict[str, Any]) -> dict[str, Any]:
    status = str(lead.get("status", "New"))
    payment = str(lead.get("payment_status", "Not Started"))
    admission = str(lead.get("admission_status", "Not Started"))
    reasons = []
    if _due(lead): reasons.append("overdue_or_due")
    if payment == "Pending": reasons.append("payment_pending")
    if admission in {"Application", "Documents Pending", "Payment Pending", "Ready for Enrollment"}: reasons.append("admission_stage")
    if lead.get("counselling_history"): reasons.append("counselling_follow_up")
    return {"lead_id": lead.get("lead_id"), "status": status, "reasons": reasons, "follow_up_date": lead.get("follow_up_date", "")}


def follow_up_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    action = str(task.input.get("action", "discover") or "discover").lower()
    lead_id = str(task.input.get("lead_id") or context.lead_id or "").strip()
    if action in {"send", "schedule"}:
        return {
            "agent_id": "FOLLOW_UP", "status": "waiting_authorization", "execution_performed": False,
            "authorization_required": True, "actions_requested": [action],
            "message_sent": False, "message_scheduled": False,
            "errors": ["no messaging or scheduling provider configured"],
        }
    if action == "prepare":
        lead = lead_manager.get_lead(lead_id) or {}
        name = str(lead.get("name") or "there")
        course = str(lead.get("course_interest") or "your course enquiry")
        return {
            "agent_id": "FOLLOW_UP", "status": "prepared", "execution_performed": False,
            "authorization_required": False, "lead_id": lead_id,
            "draft_message": f"Hello {name}, following up on your {course} enquiry. How can our counselling team help with the next step?",
            "recommended_timing": lead.get("follow_up_date") or "next business day",
            "actions_requested": [], "errors": [],
        }
    leads = lead_manager.get_all_leads()
    if lead_id:
        leads = [lead for lead in leads if lead.get("lead_id") == lead_id]
    summaries = [_lead_summary(lead) for lead in leads if _lead_summary(lead)["reasons"]]
    return {
        "agent_id": "FOLLOW_UP", "status": "completed", "execution_performed": False,
        "authorization_required": False, "follow_up_candidates": deepcopy(summaries),
        "recommended_next_step": "prepare" if summaries else "no_follow_up_required",
        "actions_requested": [], "errors": [],
    }