from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.agentic.models import AuthorizationDecision


COMPUTER_PERMISSION_SCOPES = {
    "FILE_READ", "FILE_WRITE", "BROWSER_READ", "BROWSER_WRITE", "UPLOAD",
    "DOWNLOAD", "APPLICATION_OPEN", "EXTERNAL_ACTION", "SOCIAL_MEDIA_ACTION",
}

ACTION_STATES = {
    "PLANNED", "READY", "WAITING_AUTHORIZATION", "AUTHORIZED", "EXECUTING",
    "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "VERIFICATION_REQUIRED",
}


@dataclass
class ComputerAction:
    action_id: str
    workflow_id: str | None
    action_type: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_result: dict[str, Any] = field(default_factory=dict)
    authorization_required: bool = True
    authorization_state: str = "PENDING"
    status: str = "PLANNED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    audit_reference: str | None = None


@dataclass(frozen=True)
class BrowserState:
    current_url: str | None
    page_title: str | None
    visible_state_summary: str | None
    available_actions: tuple[str, ...] = ()
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    workflow_id: str | None = None


class FileOperationProvider(Protocol):
    def read_file(self, path: str) -> str: ...
    def create_file(self, path: str, content: str) -> dict[str, Any]: ...
    def edit_file(self, path: str, content: str) -> dict[str, Any]: ...
    def copy_file(self, source: str, target: str) -> dict[str, Any]: ...
    def move_file(self, source: str, target: str) -> dict[str, Any]: ...
    def download(self, source: str, target: str) -> dict[str, Any]: ...
    def upload(self, source: str, target: str) -> dict[str, Any]: ...


class UnconfiguredFileOperationProvider:
    def __getattr__(self, name: str):
        def unavailable(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("file operation provider is not configured")
        return unavailable


def _needs_authorization(action_type: str) -> bool:
    return action_type.upper() not in {"READ_PAGE", "READ_STATE", "SCREENSHOT_STATE", "VERIFY"}


def plan_action(action_type: str, target: str, *, workflow_id: str | None = None, parameters: dict[str, Any] | None = None, expected_result: dict[str, Any] | None = None) -> ComputerAction:
    action_type = action_type.upper()
    if action_type not in {"OPEN_APPLICATION", "NAVIGATE", "READ_PAGE", "READ_STATE", "CLICK", "TYPE", "SELECT", "SCROLL", "UPLOAD", "DOWNLOAD", "CREATE_FILE", "EDIT_FILE", "COPY_FILE", "MOVE_FILE", "SAVE", "SCREENSHOT_STATE", "VERIFY"}:
        raise ValueError(f"unsupported computer action: {action_type}")
    required = _needs_authorization(action_type)
    return ComputerAction(
        action_id=f"action-{uuid4().hex}", workflow_id=workflow_id, action_type=action_type,
        target=target, parameters=parameters or {}, expected_result=expected_result or {"target": target, "action_type": action_type},
        authorization_required=required, authorization_state="PENDING" if required else "NOT_REQUIRED",
        status="WAITING_AUTHORIZATION" if required else "READY",
    )


def plan_request(request: str, *, workflow_id: str | None = None) -> list[ComputerAction]:
    value = str(request or "")
    actions: list[ComputerAction] = []
    if re.search(r"open.*(browser|dashboard|application|page)", value, re.IGNORECASE):
        actions.append(plan_action("OPEN_APPLICATION", "browser", workflow_id=workflow_id, expected_result={"application_open": True}))
        actions.append(plan_action("NAVIGATE", "authorized target page", workflow_id=workflow_id, expected_result={"page_identity_verified": True}))
        actions.append(plan_action("READ_STATE", "target page", workflow_id=workflow_id, expected_result={"browser_state_captured": True}))
    if re.search(r"click|locate|upload interface", value, re.IGNORECASE):
        actions.append(plan_action("CLICK", "authorized interface", workflow_id=workflow_id, expected_result={"ui_state_changed": True}))
    if re.search(r"type|enter|caption", value, re.IGNORECASE):
        actions.append(plan_action("TYPE", "authorized input", workflow_id=workflow_id, parameters={"content": "provided at execution time"}, expected_result={"text_present": True}))
    if re.search(r"upload", value, re.IGNORECASE):
        actions.append(plan_action("UPLOAD", "authorized upload control", workflow_id=workflow_id, expected_result={"uploaded_file_state": True}))
    if re.search(r"download", value, re.IGNORECASE):
        actions.append(plan_action("DOWNLOAD", "authorized download target", workflow_id=workflow_id, expected_result={"local_file_exists": True}))
    if not actions:
        actions.append(plan_action("READ_STATE", "requested computer/browser state", workflow_id=workflow_id, expected_result={"state_observed": True}))
    return actions


def computer_action_handler(task: Any, context: Any) -> dict[str, Any]:
    actions = plan_request(task.user_request, workflow_id=context.current_task_id)
    return {
        "agent_id": "COMPUTER_ACTION", "status": "prepared", "actions": [action.__dict__ for action in actions],
        "authorization_required": any(action.authorization_required for action in actions),
        "execution_performed": False, "external_action": False, "browser_state": None,
        "human_handoff_required": any(action.authorization_required for action in actions),
        "errors": ["No computer-use executor is configured; action plan only."],
    }


class ComputerActionInterface(Protocol):
    def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        authorization: AuthorizationDecision,
    ) -> dict[str, Any]:
        """Execute one authorized computer action."""


class UnconfiguredComputerAction:
    """Safe default until a real computer-use provider is configured."""

    def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        authorization: AuthorizationDecision,
    ) -> dict[str, Any]:
        if not authorization.approved:
            raise PermissionError("computer action requires explicit authorization")
        raise RuntimeError("computer-use provider is not configured")
