from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(default)
    return value


class WorkflowStateStore:
    """Durable JSON store for workflow snapshots and append-only checkpoints."""

    def __init__(self, root: str | Path = "data/agentic") -> None:
        root_path = Path(root)
        self.state_path = root_path / "workflows.json"
        self.checkpoint_path = root_path / "workflow_checkpoints.json"
        self._lock = RLock()

    def save(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            workflows = _read_json(self.state_path, {})
            workflows[str(snapshot["workflow_id"])] = deepcopy(snapshot)
            _write_json(self.state_path, workflows)
        return deepcopy(snapshot)

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = _read_json(self.state_path, {}).get(workflow_id)
        return deepcopy(value) if isinstance(value, dict) else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            values = _read_json(self.state_path, {})
        return [deepcopy(value) for value in values.values() if isinstance(value, dict)]

    def checkpoint(self, workflow_id: str, event_type: str, snapshot: dict[str, Any], **metadata: Any) -> dict[str, Any]:
        event = {
            "checkpoint_id": f"checkpoint-{datetime.now(timezone.utc).timestamp()}-{len(self.history(workflow_id))}",
            "workflow_id": workflow_id,
            "event_type": event_type,
            "created_at": _now(),
            "snapshot": deepcopy(snapshot),
            "metadata": deepcopy(metadata),
        }
        with self._lock:
            history = _read_json(self.checkpoint_path, {})
            history.setdefault(workflow_id, []).append(event)
            _write_json(self.checkpoint_path, history)
            self.save(snapshot)
        return deepcopy(event)

    def history(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            history = _read_json(self.checkpoint_path, {}).get(workflow_id, [])
        return deepcopy(history) if isinstance(history, list) else []

    def latest_checkpoint(self, workflow_id: str) -> dict[str, Any] | None:
        history = self.history(workflow_id)
        return history[-1] if history else None


class PersistentAuditLog:
    """Append-only JSON audit log with the same events() / record() API as AuditLog."""

    def __init__(self, path: str | Path = "data/agentic/audit_events.json") -> None:
        self.path = Path(path)
        self._lock = RLock()

    def _events(self) -> list[dict[str, Any]]:
        value = _read_json(self.path, [])
        return value if isinstance(value, list) else []

    def record(self, event_type: str, actor: str, **details: Any):
        from app.agentic.audit import AuditEvent

        event = AuditEvent(event_type=event_type, actor=actor, details=details)
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "actor": event.actor,
            "details": deepcopy(event.details),
            "created_at": event.created_at.isoformat(),
        }
        with self._lock:
            events = self._events()
            events.append(payload)
            _write_json(self.path, events)
        return event

    def events(self) -> tuple:
        from app.agentic.audit import AuditEvent

        with self._lock:
            values = self._events()
        result = []
        for value in values:
            try:
                created_at = datetime.fromisoformat(value["created_at"])
                result.append(AuditEvent(event_type=value["event_type"], actor=value["actor"], details=value.get("details", {}), event_id=value["event_id"], created_at=created_at))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(result)
