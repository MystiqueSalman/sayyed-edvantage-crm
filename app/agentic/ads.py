from __future__ import annotations

import re
from typing import Any

from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task
from app.agentic.platform_provider import AdsProvider, UnconfiguredPlatformProvider


def ads_handler(task: Task, context: AgentContext, provider: AdsProvider | None = None) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    platform = next((name for name in ("Facebook", "Instagram", "YouTube", "LinkedIn") if name.lower() in task.user_request.lower()), "Facebook")
    course = courses[0]["course"] if courses else None
    external = bool(re.search(r"\b(launch|run|spend|purchase|change budget|start)\b", task.user_request, re.IGNORECASE))
    if not course:
        return {"agent_id": "ADS", "status": "blocked", "campaign_plan": {}, "authorization_required": external, "execution_status": "NOT_EXECUTED", "spend_performed": False, "errors": ["No approved course was identified"]}
    request = __import__("app.agentic.platform_provider", fromlist=["PlatformActionRequest"]).PlatformActionRequest("CREATE_CAMPAIGN", platform, f"{course} lead campaign")
    response = (provider or UnconfiguredPlatformProvider("ads")).execute(request) if external and task.authorization_status.value == "APPROVED" else None
    return {
        "agent_id": "ADS", "status": "prepared", "campaign_plan": {
            "objective": "Generate qualified course enquiries",
            "platform": platform, "course": course,
            "audience": ["students", "graduates", "working professionals", "career changers"],
            "ad_set_structure": ["course interest", "location", "audience intent"],
            "creative_requirements": ["approved caption", "image creative specification", "video creative specification"],
            "copy_variants": [f"Explore {course} with Sayyed EdVantage.", f"Speak with admissions about {course}."],
            "cta": "Learn more",
            "measurement": ["impressions", "clicks", "enquiries", "cost per enquiry"],
        },
        "budget_recommendation": {"status": "requires_human_budget_approval", "amount": None, "currency": None},
        "authorization_required": external or True, "execution_status": "NOT_EXECUTED", "spend_performed": False,
        "campaign_launched": False, "provider": response.provider if response else "unconfigured",
        "errors": list(response.errors) if response else (["authorization required before external action"] if external else []), "factual_sources": ["MASTER_KB_CLOSURE"],
    }