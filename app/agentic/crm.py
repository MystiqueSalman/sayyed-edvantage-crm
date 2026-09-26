from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agentic.models import AgentContext, Task
from app.leads import lead_manager


READ_FIELDS = {
    "profile": None,
    "lead": None,
    "pipeline_stage": "status",
    "course_interest": "course_interest",
    "counselling_history": "counselling_history",
    "follow_up_history": "follow_up_history",
    "activity_timeline": "status_history",
    "admission_status": "admission_status",
    "crm_context": None,
}


def _lead_id(task: Task, context: AgentContext) -> str:
    return str(
        task.input.get("lead_id")
        or context.lead_id
        or context.crm_state.get("lead_id", "")
    ).strip()


def _read_result(lead_id: str, operation: str) -> dict[str, Any]:
    lead = lead_manager.get_lead(lead_id)
    if not isinstance(lead, dict):
        return {
            "agent_id": "CRM",
            "status": "not_found",
            "lead_id": lead_id,
            "data": None,
            "execution_performed": False,
            "authorization_required": False,
            "actions_requested": [],
            "errors": ["lead not found"],
        }
    field = READ_FIELDS.get(operation)
    data = lead if field is None else lead.get(field, [] if field.endswith("history") or field == "status_history" else "")
    return {
        "agent_id": "CRM",
        "status": "completed",
        "lead_id": lead_id,
        "operation": operation,
        "data": deepcopy(data),
        "execution_performed": False,
        "authorization_required": False,
        "actions_requested": [],
        "errors": [],
    }


def _write_result(task: Task, context: AgentContext) -> dict[str, Any]:
    lead_id = _lead_id(task, context)
    action = str(task.input.get("action", "")).strip().lower()
    if not task.authorization_required or task.authorization_status.value != "APPROVED":
        return {
            "agent_id": "CRM",
            "status": "waiting_authorization",
            "lead_id": lead_id,
            "execution_performed": False,
            "authorization_required": True,
            "actions_requested": [action or "crm_write"],
            "errors": [],
        }

    result = None
    if action in {"update_lead", "change_pipeline_stage", "change_admission_status"}:
        updates = dict(task.input.get("updates", {}))
        if action == "change_pipeline_stage":
            updates = {"status": task.input.get("status", updates.get("status", ""))}
        if action == "change_admission_status":
            updates = {"admission_status": task.input.get("admission_status", updates.get("admission_status", ""))}
        result = lead_manager.update_lead(lead_id, **updates)
    elif action == "add_follow_up":
        result = lead_manager.add_follow_up_action(
            lead_id,
            outcome=task.input.get("outcome", "Contacted"),
            notes=task.input.get("notes", ""),
            next_follow_up_date=task.input.get("next_follow_up_date", ""),
            next_follow_up_time=task.input.get("next_follow_up_time", ""),
            counsellor=task.input.get("counsellor", ""),
        )
    elif action == "add_counselling":
        result = lead_manager.add_counselling_session(
            lead_id,
            counsellor=task.input.get("counsellor", ""),
            counselling_date=task.input.get("counselling_date", ""),
            counselling_time=task.input.get("counselling_time", ""),
            mode=task.input.get("mode", "Phone"),
            outcome=task.input.get("outcome", "Pending"),
            notes=task.input.get("notes", ""),
            next_follow_up_date=task.input.get("next_follow_up_date", ""),
            next_follow_up_time=task.input.get("next_follow_up_time", ""),
        )
    elif action == "delete_lead":
        result = lead_manager.delete_lead(lead_id)
    else:
        return {
            "agent_id": "CRM",
            "status": "blocked",
            "lead_id": lead_id,
            "execution_performed": False,
            "authorization_required": True,
            "actions_requested": [action or "crm_write"],
            "errors": ["unsupported CRM write action"],
        }

    succeeded = bool(result) if action == "delete_lead" else isinstance(result, dict)
    verified = bool(lead_manager.get_lead(lead_id)) if action != "delete_lead" else lead_manager.get_lead(lead_id) is None
    return {
        "agent_id": "CRM",
        "status": "completed" if succeeded and verified else "failed",
        "lead_id": lead_id,
        "execution_performed": succeeded and verified,
        "authorization_required": True,
        "actions_requested": [action],
        "verified": verified,
        "data": deepcopy(result) if isinstance(result, dict) else result,
        "errors": [] if succeeded and verified else ["CRM write verification failed"],
    }


def crm_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    if task.input.get("action"):
        return _write_result(task, context)
    operation = str(task.input.get("operation", "lead") or "lead").strip().lower()
    if operation in READ_FIELDS:
        return _read_result(_lead_id(task, context), operation)
    return _write_result(task, context)