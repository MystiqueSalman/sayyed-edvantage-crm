from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.ai.memory import load_memory, save_message
from app.agentic.models import AgentContext, Task


def _conflicts(history: list[dict[str, Any]], crm: dict[str, Any]) -> list[str]:
    conflicts = []
    text = " ".join(str(item.get("content", "")) for item in history if isinstance(item, dict)).lower()
    course = str(crm.get("course_interest", "")).strip().lower()
    country = str(crm.get("country", "")).strip().lower()
    if course and course not in text:
        conflicts.append("crm_course_not_present_in_conversation")
    if country and country not in text:
        conflicts.append("crm_country_not_present_in_conversation")
    return conflicts


def memory_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    session_id = context.session_id or str(task.input.get("session_id", "default_student"))
    history = load_memory(session_id)
    action = str(task.input.get("action", "retrieve") or "retrieve").lower()
    crm = deepcopy(context.crm_state)
    if not crm and context.lead_id:
        from app.leads.lead_manager import get_lead
        crm = deepcopy(get_lead(context.lead_id) or {})
    if action == "save_message":
        if not task.authorization_required or task.authorization_status.value != "APPROVED":
            return {
                "agent_id": "MEMORY", "status": "waiting_authorization", "session_id": session_id,
                "execution_performed": False, "authorization_required": True,
                "actions_requested": ["save_message"], "errors": [],
            }
        save_message(session_id, str(task.input.get("role", "user")), str(task.input.get("content", "")))
        saved = load_memory(session_id)
        return {
            "agent_id": "MEMORY", "status": "completed", "session_id": session_id,
            "execution_performed": bool(saved), "authorization_required": True,
            "actions_requested": ["save_message"], "memory": deepcopy(saved), "errors": [],
        }
    relevant = history[-int(task.input.get("limit", 10) or 10):]
    return {
        "agent_id": "MEMORY", "status": "completed", "session_id": session_id,
        "execution_performed": False, "authorization_required": False,
        "conversation_context": deepcopy(relevant),
        "student_context": deepcopy(context.student_profile),
        "course_interest": crm.get("course_interest", ""),
        "previous_questions": [item.get("content", "") for item in relevant if item.get("role") == "user"],
        "crm_context": crm,
        "conflicts": _conflicts(relevant, crm),
        "memory_update": task.input.get("prepared_update", {}),
        "actions_requested": [],
        "errors": [],
    }