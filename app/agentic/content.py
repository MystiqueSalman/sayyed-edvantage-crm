from __future__ import annotations

import re
from typing import Any

from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task


PLATFORMS = {"instagram", "facebook", "youtube", "linkedin", "whatsapp", "email"}


def _platform(request: str, supplied: str | None) -> str:
    value = str(supplied or request).lower()
    for platform in PLATFORMS:
        if platform in value:
            return platform.title()
    return "General"


def _variants(course: str, platform: str, count: int) -> list[dict[str, str]]:
    hooks = [
        f"Ready to explore {course}?",
        f"Your next technology learning step could start with {course}.",
        f"Build direction and practical skills with {course}.",
    ]
    variants = []
    for index in range(max(1, min(count, 3))):
        variants.append({
            "variant": chr(65 + index),
            "hook": hooks[index],
            "caption": f"{hooks[index]} Learn more about the approved Sayyed EdVantage program and connect with the admissions team for current details.",
            "cta": "Learn more and speak with admissions",
            "hashtags": f"#SayyedEdVantage #{course.replace(' ', '').replace('+', '')} #CareerLearning",
        })
    return variants


def content_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    publish_requested = bool(re.search(r"\b(publish|post|launch|send|run the ad)\b", task.user_request, re.IGNORECASE))
    if not courses:
        return {
            "agent_id": "CONTENT", "status": "blocked", "content_type": "campaign_copy",
            "platform": _platform(task.user_request, task.input.get("platform")), "course": None,
            "approval_status": "needs_course_confirmation", "authorization_required": publish_requested,
            "execution_performed": False, "publication_requested": publish_requested,
            "factual_sources": [], "variants": [], "errors": ["No approved course was identified"],
        }
    course = courses[0]["course"] if len(courses) == 1 else ", ".join(item["course"] for item in courses)
    platform = _platform(task.user_request, task.input.get("platform"))
    count = int(task.input.get("variant_count", 3) or 3)
    return {
        "agent_id": "CONTENT", "status": "prepared", "content_type": str(task.input.get("content_type", "social_promotion")),
        "platform": platform, "audience": task.input.get("audience", "students and career changers"),
        "objective": "Create reviewable educational or promotional content", "course": course,
        "cta": "Learn more and speak with admissions", "variants": _variants(course, platform, count),
        "creative_concept": f"A clear, factual {platform} concept focused on the approved {course} program.",
        "factual_sources": ["MASTER_KB_CLOSURE"], "approval_status": "prepared_for_review",
        "authorization_required": publish_requested, "execution_performed": False,
        "publication_requested": publish_requested, "published": False, "external_action": False,
        "errors": ["Publication is deferred; no publishing provider is configured."] if publish_requested else [],
    }