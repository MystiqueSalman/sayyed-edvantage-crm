from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


NORMAL_PRIORITY = 50


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActionLevel(str, Enum):
    THINK = "THINK"
    PREPARE = "PREPARE"
    EXECUTE = "EXECUTE"


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    WAITING_AUTHORIZATION = "WAITING_AUTHORIZATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class AuthorizationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    description: str
    capabilities: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    permission_scopes: tuple[str, ...] = ()
    action_level: ActionLevel = ActionLevel.THINK
    dependencies: tuple[str, ...] = ()
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    authorization_requirements: tuple[str, ...] = ()
    enabled: bool = True
    version: str = "1.0.0"


@dataclass
class Task:
    user_request: str
    agent_id: str
    input: dict[str, Any] = field(default_factory=dict)
    action_level: ActionLevel = ActionLevel.THINK
    priority: int =  NORMAL_PRIORITY
    task_id: str = field(default_factory=lambda: f"task-{uuid4().hex}")
    parent_task_id: str | None = None
    status: TaskStatus = TaskStatus.CREATED
    output: dict[str, Any] | None = None
    dependencies: list[str] = field(default_factory=list)
    authorization_required: bool = False
    authorization_status: AuthorizationStatus = AuthorizationStatus.NOT_REQUIRED
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    audit_id: str | None = None

@dataclass(frozen=True)
class AgentContext:
    user_request: str
    session_id: str | None = None
    conversation_history: tuple[dict[str, Any], ...] = ()
    student_profile: dict[str, Any] = field(default_factory=dict)
    lead_id: str | None = None
    crm_state: dict[str, Any] = field(default_factory=dict)
    course_information: dict[str, Any] = field(default_factory=dict)
    commercial_information: dict[str, Any] = field(default_factory=dict)
    current_task_id: str | None = None
    agent_outputs: dict[str, Any] = field(default_factory=dict)
    authorization_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    requires_action: bool = False
    message_id: str = field(default_factory=lambda: f"msg-{uuid4().hex}")


@dataclass(frozen=True)
class AuthorizationDecision:
    action: str
    risk: str
    authorization_required: bool
    approved: bool = False
    reason: str = ""
    approval_id: str | None = None
