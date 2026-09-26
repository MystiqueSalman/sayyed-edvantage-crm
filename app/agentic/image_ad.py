from __future__ import annotations

import re
from typing import Any

from app.agentic.creative_provider import (
    CreativeGenerationRequest,
    ImageGenerationProvider,
    UnconfiguredImageGenerationProvider,
)
from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task


FORMAT_SPECS = {
    "instagram post": ("1:1", "1080x1080"),
    "instagram story": ("9:16", "1080x1920"),
    "instagram reel cover": ("9:16", "1080x1920"),
    "facebook post": ("1:1", "1200x1200"),
    "youtube thumbnail": ("16:9", "1280x720"),
    "linkedin post": ("1:1", "1200x1200"),
    "whatsapp promotional creative": ("4:5", "1080x1350"),
}


def _format(request: str, supplied: str | None) -> tuple[str, str, str]:
    value = str(supplied or request).lower()
    for name, spec in FORMAT_SPECS.items():
        if name in value:
            return name.title(), spec[0], spec[1]
    if "vertical" in value or "story" in value:
        return "Vertical Creative", "9:16", "1080x1920"
    if "landscape" in value or "thumbnail" in value:
        return "Landscape Creative", "16:9", "1280x720"
    return "Square Creative", "1:1", "1080x1080"


def image_ad_handler(task: Task, context: AgentContext, provider: ImageGenerationProvider | None = None) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    if not courses:
        return {"agent_id": "IMAGE_AD", "status": "blocked", "creative_type": "IMAGE_AD", "course": None, "approval_status": "NEEDS_COURSE_CONFIRMATION", "authorization_required": False, "execution_performed": False, "asset_generated": False, "errors": ["No approved course was identified"]}
    course = courses[0]["course"]
    platform, aspect_ratio, dimensions = _format(task.user_request, task.input.get("format"))
    headline = f"Explore {course}"
    body = "Build practical direction with an approved Sayyed EdVantage learning program."
    cta = "Speak with admissions"
    variants = [
        {"variant": "A", "hook": headline, "layout": "course-led headline with clean learning-focused visual", "cta": cta},
        {"variant": "B", "hook": f"Your next step in technology: {course}", "layout": "audience-led composition with clear course identity", "cta": "Learn more"},
        {"variant": "C", "hook": f"Start exploring {course}", "layout": "minimal poster with strong CTA hierarchy", "cta": cta},
    ]
    prompt = f"Create a professional Sayyed EdVantage {platform} advertisement for {course}. Use a factual education-focused composition, clear typography, accessible contrast, approved brand identity, and no unsupported claims, guarantees, fees, or invented credentials."
    generation = (provider or UnconfiguredImageGenerationProvider()).generate_image(CreativeGenerationRequest("IMAGE_AD", prompt, {"platform": platform, "aspect_ratio": aspect_ratio, "dimensions": dimensions}))
    publish_requested = bool(re.search(r"\b(upload|publish|post|launch)\b", task.user_request, re.IGNORECASE))
    return {
        "agent_id": "IMAGE_AD", "status": "prepared", "creative_type": "IMAGE_AD", "campaign": "Sayyed EdVantage course promotion",
        "course": course, "platform": platform, "aspect_ratio": aspect_ratio, "dimensions": dimensions,
        "headline": headline, "body_copy": body, "cta": cta, "visual_prompt": prompt, "variants": variants,
        "generation_status": generation.status, "provider": generation.provider, "asset_generated": bool(generation.asset_id),
        "approval_status": "PREPARED", "authorization_required": publish_requested, "execution_performed": False,
        "published": False, "external_action": False, "factual_sources": ["MASTER_KB_CLOSURE"],
        "errors": list(generation.errors),
    }