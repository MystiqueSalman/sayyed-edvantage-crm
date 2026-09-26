from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.agentic.durable import PersistentAuditLog, WorkflowStateStore, _read_json, _write_json


WORKFLOW_STATUSES = {
    "CREATED", "QUEUED", "RUNNING", "WAITING", "SCHEDULED", "PAUSED",
    "WAITING_AUTHORIZATION", "WAITING_HUMAN", "RETRY_PENDING", "FAILED",
    "COMPLETED", "CANCELLED",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _deterministic_id(key: str) -> str:
    return f"workflow-{hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]}"


def _requires_authorization(objective: str) -> bool:
    return bool(re.search(r"\b(login|upload|publish|post|delete|edit|send|message|follow|unfollow|comment|like|react|launch|spend|purchase|change.*lead|modify crm|admission status|change budget|browser|computer|external submission)\b", objective, re.IGNORECASE))


class DurableWorkflowScheduler:
    """Deterministic, JSON-backed scheduler for existing agentic workflows."""

    def __init__(self, root: str | Path = "data/agentic", *, state_store: WorkflowStateStore | None = None, audit_log: Any = None) -> None:
        self.root = Path(root)
        self.registry_path = self.root / "scheduler_workflows.json"
        self.events_path = self.root / "operational_events.json"
        self.state_store = state_store or WorkflowStateStore(self.root)
        self.audit_log = audit_log or PersistentAuditLog(self.root / "audit_events.json")
        self._lock = RLock()

    def _records(self) -> dict[str, dict[str, Any]]:
        value = _read_json(self.registry_path, {})
        return value if isinstance(value, dict) else {}

    def _save_records(self, records: dict[str, dict[str, Any]]) -> None:
        _write_json(self.registry_path, records)

    def _events(self) -> list[dict[str, Any]]:
        value = _read_json(self.events_path, [])
        return value if isinstance(value, list) else []

    def _event(self, event_type: str, record: dict[str, Any], **metadata: Any) -> dict[str, Any]:
        event_key = f"{record['workflow_id']}:{event_type}:{record.get('updated_at')}"
        event = {
            "event_id": f"event-{hashlib.sha256(event_key.encode('utf-8')).hexdigest()[:24]}",
            "event_type": event_type,
            "workflow_id": record["workflow_id"],
            "timestamp": _iso(_now()),
            "status": record["status"],
            "authorization_state": record.get("authorization_state", "NOT_REQUIRED"),
            "metadata": deepcopy(metadata),
        }
        events = self._events()
        if not any(item.get("event_id") == event["event_id"] for item in events):
            events.append(event)
            _write_json(self.events_path, events)
            audit_details = dict(event)
            audit_details["operational_event_type"] = audit_details.pop("event_type")
            self.audit_log.record("OPERATIONAL_EVENT", "SCHEDULER", **audit_details)
        return deepcopy(event)

    def schedule(self, objective: str, *, workflow_type: str = "agentic_workflow", run_at: datetime | str | None = None, recurring_seconds: int | None = None, priority: int = 50, owner: str = "system", workflow_id: str | None = None, idempotency_key: str | None = None, max_retries: int = 3) -> dict[str, Any]:
        key = idempotency_key or workflow_id or f"{workflow_type}:{owner}:{objective}:{run_at}:{recurring_seconds}"
        workflow_id = workflow_id or _deterministic_id(key)
        with self._lock:
            records = self._records()
            existing = records.get(workflow_id)
            if existing is not None:
                if not all(existing.get(key) == value for key, value in {"objective": objective, "workflow_type": workflow_type, "owner": owner, "priority": priority, "recurring_seconds": recurring_seconds}.items()):
                    raise ValueError("idempotency key conflicts with an existing workflow")
                return deepcopy(existing)
            scheduled = _parse(run_at)
            status = "SCHEDULED" if scheduled and scheduled > _now() else "QUEUED"
            now = _iso(_now())
            record = {
                "workflow_id": workflow_id, "workflow_type": workflow_type, "objective": objective,
                "created_at": now, "updated_at": now, "status": status, "priority": priority,
                "owner": owner, "current_step": None, "next_run_at": _iso(scheduled) if scheduled else now,
                "recurring_seconds": recurring_seconds, "retry_count": 0, "max_retries": max_retries,
                "last_error": None, "authorization_state": "PENDING" if _requires_authorization(objective) else "NOT_REQUIRED",
                "audit_reference": None, "human_handoff_state": None, "last_checkpoint": None,
            }
            records[workflow_id] = record
            self._save_records(records)
            self._event("workflow_created", record)
            self._event("workflow_scheduled" if status == "SCHEDULED" else "workflow_queued", record)
            return deepcopy(record)

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        return deepcopy(self._records().get(workflow_id))

    def list(self, *, status: str | None = None, workflow_type: str | None = None, owner: str | None = None, priority: int | None = None, authorization_state: str | None = None) -> list[dict[str, Any]]:
        records = list(self._records().values())
        return [deepcopy(record) for record in records if (status is None or record.get("status") == status) and (workflow_type is None or record.get("workflow_type") == workflow_type) and (owner is None or record.get("owner") == owner) and (priority is None or record.get("priority") == priority) and (authorization_state is None or record.get("authorization_state") == authorization_state)]

    def start(self, workflow_id: str, runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None, *, now: datetime | None = None) -> dict[str, Any]:
        with self._lock:
            records = self._records()
            record = records.get(workflow_id)
            if record is None:
                raise KeyError(workflow_id)
            if record["status"] in {"COMPLETED", "CANCELLED", "PAUSED", "WAITING_AUTHORIZATION", "WAITING_HUMAN"}:
                return deepcopy(record)
            due_at = _parse(record.get("next_run_at"))
            if due_at and due_at > (now or _now()):
                return deepcopy(record)
            record["status"] = "WAITING_AUTHORIZATION" if record.get("authorization_state") == "PENDING" else "RUNNING"
            record["updated_at"] = _iso(_now())
            records[workflow_id] = record
            self._save_records(records)
            self._event("authorization_requested" if record["status"] == "WAITING_AUTHORIZATION" else "workflow_started", record)
            if record["status"] == "WAITING_AUTHORIZATION" or runner is None:
                return deepcopy(record)
        try:
            result = runner(deepcopy(record))
        except Exception as exc:
            return self.fail(workflow_id, str(exc), retryable=True)
        return self.complete(workflow_id, result=result)

    def start_due(self, runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or _now()
        due = [record for record in self.list() if record["status"] in {"QUEUED", "SCHEDULED", "RETRY_PENDING"} and (_parse(record.get("next_run_at")) or current) <= current]
        due.sort(key=lambda record: (-int(record.get("priority", 50)), record.get("created_at", "")))
        return [self.start(record["workflow_id"], runner, now=current) for record in due]

    def pause(self, workflow_id: str) -> dict[str, Any]:
        return self._transition(workflow_id, "PAUSED", "workflow_paused")

    def resume(self, workflow_id: str) -> dict[str, Any]:
        record = self.get(workflow_id)
        if record is None:
            raise KeyError(workflow_id)
        if record["status"] in {"WAITING_AUTHORIZATION", "WAITING_HUMAN", "FAILED", "COMPLETED", "CANCELLED"}:
            return record
        return self._transition(workflow_id, "QUEUED", "workflow_resumed", next_run_at=_iso(_now()))

    def approve(self, workflow_id: str, approval_id: str) -> dict[str, Any]:
        if not str(approval_id or "").strip():
            raise ValueError("approval_id must not be blank")
        record = self.get(workflow_id)
        if record is None:
            raise KeyError(workflow_id)
        if record.get("authorization_state") != "PENDING":
            return record
        return self._transition(workflow_id, "QUEUED", "authorization_received", authorization_state="APPROVED", authorization_reference=approval_id, next_run_at=_iso(_now()))

    def cancel(self, workflow_id: str) -> dict[str, Any]:
        return self._transition(workflow_id, "CANCELLED", "workflow_cancelled")

    def complete(self, workflow_id: str, *, result: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.get(workflow_id)
        if record is None:
            raise KeyError(workflow_id)
        if record["status"] == "COMPLETED":
            return record
        if record["status"] in {"CANCELLED", "FAILED", "WAITING_AUTHORIZATION", "WAITING_HUMAN"}:
            return record
        if record.get("recurring_seconds"):
            return self._transition(workflow_id, "SCHEDULED", "workflow_scheduled", next_run_at=_iso(_now() + timedelta(seconds=int(record["recurring_seconds"]))), last_result=result)
        return self._transition(workflow_id, "COMPLETED", "workflow_completed", last_result=result)

    def fail(self, workflow_id: str, error: str, *, retryable: bool = True) -> dict[str, Any]:
        record = self.get(workflow_id)
        if record is None:
            raise KeyError(workflow_id)
        if record["status"] in {"COMPLETED", "CANCELLED"}:
            return record
        if retryable and record["retry_count"] < record["max_retries"]:
            delay = 2 ** record["retry_count"]
            return self._transition(workflow_id, "RETRY_PENDING", "retry_scheduled", retry_count=record["retry_count"] + 1, next_run_at=_iso(_now() + timedelta(seconds=delay)), last_error=error)
        return self._transition(workflow_id, "FAILED", "workflow_failed", last_error=error)

    def detect_stalled(self, *, now: datetime | None = None, threshold_seconds: int = 3600) -> list[dict[str, Any]]:
        current = now or _now()
        result = []
        for record in self.list():
            if record["status"] not in {"RUNNING", "WAITING"}:
                continue
            updated = _parse(record["updated_at"])
            elapsed = (current - updated).total_seconds() if updated else 0
            if elapsed >= threshold_seconds:
                item = {"workflow_id": record["workflow_id"], "current_state": record["status"], "last_update": record["updated_at"], "elapsed_seconds": elapsed, "suspected_reason": record.get("last_error") or "no state transition observed", "recommended_action": "inspect or pause workflow"}
                result.append(item)
                self._event("stalled_detected", record, **item)
        return result

    def monitor(self, *, now: datetime | None = None, threshold_seconds: int = 3600) -> dict[str, Any]:
        records = self.list()
        stalled = self.detect_stalled(now=now, threshold_seconds=threshold_seconds)
        counts = {status.lower(): sum(record["status"] == status for record in records) for status in WORKFLOW_STATUSES}
        return {"total_workflows": len(records), **counts, "stalled": len(stalled), "stalled_workflows": stalled}

    def _transition(self, workflow_id: str, status: str, event_type: str, **updates: Any) -> dict[str, Any]:
        if status not in WORKFLOW_STATUSES:
            raise ValueError(f"unsupported workflow status: {status}")
        with self._lock:
            records = self._records()
            record = records.get(workflow_id)
            if record is None:
                raise KeyError(workflow_id)
            if record["status"] == status and all(record.get(key) == value for key, value in updates.items()):
                return deepcopy(record)
            record.update(updates)
            record["status"] = status
            record["updated_at"] = _iso(_now())
            records[workflow_id] = record
            self._save_records(records)
            self._event(event_type, record)
            return deepcopy(record)


def operational_snapshot(scheduler: DurableWorkflowScheduler, *, now: datetime | None = None, threshold_seconds: int = 3600) -> dict[str, Any]:
    return scheduler.monitor(now=now, threshold_seconds=threshold_seconds)
