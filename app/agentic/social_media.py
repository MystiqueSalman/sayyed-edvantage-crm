from __future__ import annotations

import re
from typing import Any

from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task
from app.agentic.platform_provider import SocialMediaProvider, UnconfiguredPlatformProvider


PLATFORMS = ("Instagram", "Facebook", "YouTube", "LinkedIn", "WhatsApp")


def _platform(request: str, supplied: str | None = None) -> str:
    value = str(supplied or request).lower()
    for platform in PLATFORMS:
        if platform.lower() in value:
            return platform
    return "Instagram"


def _hashtags(course: str) -> list[str]:
    tags = ["#SayyedEdVantage", "#Education", "#TechnologyCareers"]
    for token in ("Data Science", "Data Analytics", "AI", "Generative AI", "Python", "Linux", "DevOps", "Cybersecurity"):
        if token.lower() in course.lower():
            tags.append("#" + token.replace(" ", ""))
    return list(dict.fromkeys(tags))


def social_media_handler(task: Task, context: AgentContext, provider: SocialMediaProvider | None = None) -> dict[str, Any]:
    platform = _platform(task.user_request, task.input.get("platform"))
    courses = find_courses(task.user_request)
    course = courses[0]["course"] if courses else None
    external = bool(re.search(r"\b(login|upload|publish|post|delete|edit|send|follow|unfollow|comment|like|react)\b", task.user_request, re.IGNORECASE))
    content_type = "reel" if "reel" in task.user_request.lower() or "video" in task.user_request.lower() else "post"
    if not course:
        return {"agent": "SOCIAL_MEDIA", "status": "blocked", "platform": platform, "campaign": "", "content_type": content_type, "publication_status": "NOT_EXECUTED", "authorization_required": external, "execution_performed": False, "external_action": False, "errors": ["No approved course was identified"]}
    caption = f"Explore {course} with Sayyed EdVantage. Learn more and speak with admissions for current details."
    action = "PUBLISH_POST" if "publish" in task.user_request.lower() else "UPLOAD_CREATIVE" if "upload" in task.user_request.lower() else "ENTER_CAPTION" if "caption" in task.user_request.lower() else "PREPARE_POST"
    response = None
    if external and task.authorization_status.value == "APPROVED":
        response = (provider or UnconfiguredPlatformProvider("social_media")).execute(__import__("app.agentic.platform_provider", fromlist=["PlatformActionRequest"]).PlatformActionRequest(action, platform, f"{course} campaign", {"caption": caption, "hashtags": _hashtags(course)}))
    return {
        "agent": "SOCIAL_MEDIA", "agent_id": "SOCIAL_MEDIA", "status": "prepared", "platform": platform, "campaign": f"{course} campaign",
        "content_type": content_type, "caption": caption, "hashtags": _hashtags(course), "cta": "Speak with admissions",
        "creative_reference": f"prepared_{content_type}_{course}", "schedule": task.input.get("schedule", "next approved posting window"),
        "publication_status": "NOT_EXECUTED" if external else "PREPARED", "authorization_required": external,
        "execution_performed": bool(response and response.execution_performed), "external_action": False,
        "analytics_requirements": ["reach", "engagement", "clicks", "enquiries"], "errors": list(response.errors) if response else (["authorization required before external action"] if external else []),
    }