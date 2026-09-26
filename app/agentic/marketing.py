from __future__ import annotations

import re
from typing import Any

from Sayyed_EdVantage_Master_KB_BATCH30 import build_master_kb_for_closure
from app.agentic.models import AgentContext, Task


CATALOG_ALIASES = {
    "data science": "SE-DS-001",
    "data analytics": "SE-DA-001",
    "ai + generative ai": "SE-AIGEN-001",
    "ai and generative ai": "SE-AIGEN-001",
    "python": "SE-PY-001",
    "linux": "SE-LINUX-001",
    "devops": "SE-DEVOPS-001",
    "ethical hacking": "SE-EHC-001",
    "cybersecurity": "SE-EHC-001",
    "data science + data analytics": "SE-DSDA-COMBO-001",
    "data science and data analytics": "SE-DSDA-COMBO-001",
    "linux + devops": "SE-LINUXDEVOPS-COMBO-001",
    "linux and devops": "SE-LINUXDEVOPS-COMBO-001",
}


def approved_catalog() -> list[dict[str, Any]]:
    kb = build_master_kb_for_closure()
    records = []
    for course_id, course in kb.courses.items():
        name = str(getattr(course, "official_name", "") or "").replace("\ufffd", "-").replace("  ", " ").strip()
        records.append({
            "course_id": course_id,
            "course": name,
            "category": getattr(course, "category", ""),
            "status": getattr(course, "status", "active"),
            "source_ids": list(getattr(course, "source_ids", []) or []),
        })
    records.extend([
        {"course_id": "SE-DSDA-COMBO-001", "course": "Data Science + Data Analytics", "category": "Approved combo", "status": "active", "source_ids": ["MASTER_KB_CLOSURE"]},
        {"course_id": "SE-LINUXDEVOPS-COMBO-001", "course": "Linux + DevOps", "category": "Approved combo", "status": "active", "source_ids": ["MASTER_KB_CLOSURE"]},
    ])
    return records


def _all_requested(request: str) -> bool:
    value = str(request or "").lower()
    return bool(re.search(r"\b(all|every)\b.*\b(courses|programs)\b", value))


def find_courses(request: str) -> list[dict[str, Any]]:
    catalog = approved_catalog()
    value = str(request or "").lower()
    if _all_requested(value):
        return catalog
    found_ids: list[str] = []
    for alias, course_id in sorted(CATALOG_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in value and course_id not in found_ids:
            found_ids.append(course_id)
    by_id = {item["course_id"]: item for item in catalog}
    result = [by_id[course_id] for course_id in found_ids if course_id in by_id]
    combo_names = {
        "SE-DSDA-COMBO-001": "Data Science + Data Analytics",
        "SE-LINUXDEVOPS-COMBO-001": "Linux + DevOps",
    }
    for course_id in found_ids:
        if course_id in combo_names and not any(item["course"] == combo_names[course_id] for item in result):
            result.append({"course_id": course_id, "course": combo_names[course_id], "category": "Approved combo", "status": "active", "source_ids": ["MASTER_KB_CLOSURE"]})
    return result


def campaign_objective(request: str) -> str:
    value = str(request or "").lower()
    if "lead" in value or "enquir" in value:
        return "Generate qualified course enquiries"
    if "awareness" in value:
        return "Build awareness of the approved course offering"
    return "Promote an approved Sayyed EdVantage course or program"


def marketing_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    courses = find_courses(task.user_request)
    audience = str(task.input.get("audience", "students, graduates, and career changers"))
    platform = str(task.input.get("platform", "Instagram, Facebook, YouTube, LinkedIn, WhatsApp"))
    publish_requested = bool(re.search(r"\b(publish|post|launch|send|run the ad)\b", task.user_request, re.IGNORECASE))
    course_names = [item["course"] for item in courses]
    if not courses:
        return {
            "agent_id": "MARKETING", "status": "blocked", "campaign_objective": campaign_objective(task.user_request),
            "course": None, "target_audience": audience, "platforms": platform.split(", "),
            "content_pillars": [], "campaign_themes": [], "cta": "Speak with the admissions team",
            "lead_generation_goal": "", "content_requirements": [], "factual_sources": [],
            "approval_status": "needs_course_confirmation", "authorization_required": publish_requested,
            "execution_performed": False, "publication_requested": publish_requested,
            "errors": ["No approved course was identified"],
        }
    return {
        "agent_id": "MARKETING", "status": "prepared", "campaign_objective": campaign_objective(task.user_request),
        "course": course_names[0] if len(course_names) == 1 else course_names,
        "target_audience": [part.strip() for part in audience.split(",") if part.strip()],
        "platforms": [part.strip() for part in platform.split(",") if part.strip()],
        "content_pillars": ["Course value and learning direction", "Practical learning journey", "Informed next steps"],
        "campaign_themes": ["Build practical skills with a clear learning path", "Explore the right next step in technology"],
        "cta": "Explore the program and speak with the admissions team",
        "lead_generation_goal": "Collect interested learner enquiries for counselling",
        "content_requirements": ["platform-specific copy", "short-form hook", "clear factual CTA", "admissions confirmation for commercial details"],
        "example_campaign_copy": f"Explore {', '.join(course_names)} with Sayyed EdVantage. Learn more and speak with the admissions team.",
        "factual_sources": ["MASTER_KB_CLOSURE"],
        "approval_status": "prepared_for_review",
        "authorization_required": publish_requested,
        "execution_performed": False,
        "publication_requested": publish_requested,
        "errors": [],
    }