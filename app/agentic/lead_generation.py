from __future__ import annotations

import re
from typing import Any

from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task
from app.agentic.platform_provider import LeadSourceProvider, UnconfiguredPlatformProvider


def lead_generation_handler(task: Task, context: AgentContext, provider: LeadSourceProvider | None = None) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    course = courses[0]["course"] if courses else None
    source = next((name for name in ("Instagram", "Facebook", "YouTube", "LinkedIn", "WhatsApp", "Website", "Landing page", "Referral", "Manual entry") if name.lower() in task.user_request.lower()), "Website")
    capture_requested = bool(re.search(r"\b(capture|create lead|submit|connect|import)\b", task.user_request, re.IGNORECASE))
    if not course:
        return {"agent_id": "LEAD_GENERATION", "status": "blocked", "lead_source": source, "authorization_required": capture_requested, "execution_performed": False, "crm_mutation_performed": False, "errors": ["No approved course was identified"]}
    response = None
    if capture_requested:
        request = __import__("app.agentic.platform_provider", fromlist=["PlatformActionRequest"]).PlatformActionRequest("SUBMIT_LEAD_FORM", source, f"{course} lead flow")
        if task.authorization_status.value == "APPROVED":
            response = (provider or UnconfiguredPlatformProvider("lead_source")).execute(request)
    return {
        "agent_id": "LEAD_GENERATION", "status": "prepared", "lead_source": source,
        "campaign": f"{course} lead campaign", "course_interest": course,
        "lead_form_fields": ["name", "phone", "email", "course_interest", "preferred_contact_time"],
        "lead_qualification_requirements": ["course interest", "education or experience", "location", "admission intent"],
        "lead_record_template": {"lead_source": source, "campaign": f"{course} lead campaign", "course_interest": course, "status": "NEW"},
        "crm_handoff": "Prepare structured lead for authorized existing CRM boundary",
        "authorization_required": True, "execution_performed": False, "crm_mutation_performed": False,
        "external_source_connected": False, "provider": response.provider if response else "unconfigured",
        "errors": list(response.errors) if response else (["authorization required before external action"] if capture_requested else []), "factual_sources": ["MASTER_KB_CLOSURE"],
    }