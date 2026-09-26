from __future__ import annotations

import re
from typing import Any

from app.agentic.creative_provider import (
    CreativeGenerationRequest,
    UnconfiguredVideoGenerationProvider,
    VideoGenerationProvider,
)
from app.agentic.marketing import find_courses
from app.agentic.models import AgentContext, Task


def _duration(request: str, supplied: Any) -> int:
    if supplied in {10, 15, 30, 60}:
        return int(supplied)
    match = re.search(r"\b(10|15|30|60)\s*-?\s*(?:second|sec|s)\b", request, re.IGNORECASE)
    return int(match.group(1)) if match else 15


def video_ad_handler(task: Task, context: AgentContext, provider: VideoGenerationProvider | None = None) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    if not courses:
        return {"agent_id": "VIDEO_AD", "status": "blocked", "creative_type": "VIDEO_AD", "course": None, "approval_status": "NEEDS_COURSE_CONFIRMATION", "authorization_required": False, "execution_performed": False, "asset_generated": False, "errors": ["No approved course was identified"]}
    course = courses[0]["course"]
    duration = _duration(task.user_request, task.input.get("duration"))
    video_format = str(task.input.get("format", "VERTICAL" if "vertical" in task.user_request.lower() or "reel" in task.user_request.lower() or "short" in task.user_request.lower() else "SQUARE")).upper()
    scene_count = 5 if duration >= 15 else 3
    scenes = []
    for number in range(1, scene_count + 1):
        scenes.append({
            "scene_number": number, "duration": max(1, duration // scene_count),
            "visual_description": [f"Clean branded opening for {course}", "Learner-focused technology visual", f"Approved course identity: {course}", "Clear next-step information", "Admissions CTA"][min(number - 1, 4)],
            "camera_direction": "steady, clear framing",
            "on_screen_text": [f"Explore {course}", "Learn with direction", course, "Discover the program", "Speak with admissions"][min(number - 1, 4)],
            "voiceover": f"Explore {course} with Sayyed EdVantage." if number == 1 else "Learn more and confirm current details with admissions.",
            "audio_direction": "clear, restrained educational bed",
            "transition": "clean cut" if number == 1 else "soft dissolve",
            "branding": "Sayyed EdVantage",
            "CTA": "Speak with admissions" if number == scene_count else "",
        })
    visual_prompts = [f"Professional Sayyed EdVantage branded scene for {course}, factual education-focused visual, no guarantees or unsupported claims" for _ in scenes]
    prompt = f"Create a {duration}-second {video_format.lower()} advertisement plan for {course}; use the supplied scene structure and factual educational positioning."
    generation = (provider or UnconfiguredVideoGenerationProvider()).generate_video(CreativeGenerationRequest("VIDEO_AD", prompt, {"duration": duration, "format": video_format, "scenes": scenes}))
    publish_requested = bool(re.search(r"\b(upload|publish|post|launch)\b", task.user_request, re.IGNORECASE))
    return {
        "agent_id": "VIDEO_AD", "status": "prepared", "creative_type": "VIDEO_AD", "campaign": "Sayyed EdVantage course promotion",
        "course": course, "duration": duration, "format": video_format, "scenes": scenes,
        "voiceover": "Explore the approved program and speak with admissions for current details.",
        "on_screen_text": [scene["on_screen_text"] for scene in scenes], "cta": "Speak with admissions",
        "visual_prompts": visual_prompts, "production_prompt": prompt, "generation_status": generation.status,
        "provider": generation.provider, "asset_generated": bool(generation.asset_id), "approval_status": "PREPARED",
        "authorization_required": publish_requested, "execution_performed": False, "published": False,
        "external_action": False, "factual_sources": ["MASTER_KB_CLOSURE"], "errors": list(generation.errors),
    }