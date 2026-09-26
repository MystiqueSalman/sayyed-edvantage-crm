from __future__ import annotations

import re
from typing import Any

from app.agentic.models import ActionLevel, AgentContext, Task


AUTHORIZATION_MATRIX = {
    "CRM_READ": (ActionLevel.THINK, False, "crm.read"),
    "CRM_WRITE": (ActionLevel.EXECUTE, True, "crm.write"),
    "FILE_READ": (ActionLevel.THINK, False, "file.read"),
    "FILE_WRITE": (ActionLevel.EXECUTE, True, "file.write"),
    "BROWSER_READ": (ActionLevel.THINK, False, "browser.read"),
    "BROWSER_WRITE": (ActionLevel.EXECUTE, True, "browser.write"),
    "SOCIAL_READ": (ActionLevel.THINK, False, "social.read"),
    "SOCIAL_WRITE": (ActionLevel.EXECUTE, True, "social.write"),
    "MESSAGE_SEND": (ActionLevel.EXECUTE, True, "message.send"),
    "PUBLISH": (ActionLevel.EXECUTE, True, "social.publish"),
    "AD_SPEND": (ActionLevel.EXECUTE, True, "ads.spend"),
    "EXTERNAL_REQUEST": (ActionLevel.EXECUTE, True, "external.request"),
    "RESEARCH_EXTERNAL": (ActionLevel.PREPARE, False, "research.external"),
    "APPLICATION_OPEN": (ActionLevel.EXECUTE, True, "application.open"),
    "BROWSER_READ": (ActionLevel.THINK, False, "browser.read"),
    "BROWSER_WRITE": (ActionLevel.EXECUTE, True, "browser.write"),
    "UPLOAD": (ActionLevel.EXECUTE, True, "file.upload"),
    "DOWNLOAD": (ActionLevel.EXECUTE, True, "file.download"),
    "EXTERNAL_ACTION": (ActionLevel.EXECUTE, True, "external.action"),
    "SOCIAL_MEDIA_ACTION": (ActionLevel.EXECUTE, True, "social.action"),
}


def classify_action(action: str) -> dict[str, Any]:
    value = str(action or "").lower()
    if re.search(r"upload", value):
        operation = "UPLOAD"
    elif re.search(r"download", value):
        operation = "DOWNLOAD"
    elif re.search(r"open.*(browser|application)|navigate", value):
        operation = "APPLICATION_OPEN" if "application" in value else "BROWSER_READ"
    elif re.search(r"publish|send|message|spend|launch|delete|modify crm|change.*lead|external", value):
        operation = "PUBLISH" if "publish" in value or "upload" in value else "MESSAGE_SEND" if "send" in value or "message" in value else "AD_SPEND" if "spend" in value or "launch" in value else "CRM_WRITE" if "crm" in value or "lead" in value else "EXTERNAL_REQUEST"
    elif re.search(r"prepare|create|generate|plan", value):
        if "post" in value or "social" in value:
            return {"operation": "SOCIAL_WRITE", "action_level": ActionLevel.PREPARE.value, "authorization_required": False, "required_scope": "social.write"}
        operation = "FILE_READ"
    else:
        operation = "CRM_READ" if "crm" in value or "lead" in value else "FILE_READ"
    level, required, scope = AUTHORIZATION_MATRIX[operation]
    return {"operation": operation, "action_level": level.value, "authorization_required": required, "required_scope": scope}


def safety_auth_handler(task: Task, context: AgentContext) -> dict[str, Any]:
    decision = classify_action(str(task.input.get("action") or task.user_request))
    allowed = not decision["authorization_required"]
    return {
        "agent": "SAFETY_AUTH", "agent_id": "SAFETY_AUTH", "allowed": allowed,
        "authorization_required": decision["authorization_required"], "reason": "Explicit authorization is required before this external action" if not allowed else "Action is limited to internal analysis or preparation",
        "required_scope": decision["required_scope"], "action_level": decision["action_level"],
        "handoff_required": not allowed, "recommended_human_role": "account owner or admissions manager" if not allowed else "none",
        "context": {"operation": decision["operation"]}, "execution_performed": False, "errors": [],
    }