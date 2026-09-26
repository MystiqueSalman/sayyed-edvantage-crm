from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.agentic.models import utc_now


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor: str
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"audit-{uuid4().hex}")
    created_at: datetime = field(default_factory=utc_now)


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event_type: str, actor: str, **details: Any) -> AuditEvent:
        event = AuditEvent(event_type=event_type, actor=actor, details=details)
        self._events.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
