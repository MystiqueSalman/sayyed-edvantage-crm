from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.agentic.batch02_integration import build_batch02_orchestrator, build_workflow_scheduler
from app.agentic.durable import PersistentAuditLog, WorkflowStateStore
from app.agentic.monitoring import production_readiness_snapshot
from app.agentic.scheduler import DurableWorkflowScheduler


class OperationalControl:
    """Provider-neutral, read/control-only interface for the Agentic system."""

    def __init__(self, root: str = "data/agentic", *, scheduler: DurableWorkflowScheduler | None = None, state_store: WorkflowStateStore | None = None, audit_log: Any = None) -> None:
        self.root = root
        self.scheduler = scheduler or build_workflow_scheduler(root)
        self.state_store = state_store or WorkflowStateStore(root)
        self.audit_log = audit_log or PersistentAuditLog(f"{root}/audit_events.json")
        self.orchestrator = build_batch02_orchestrator()

    def _request_event(self, action: str, *, workflow_id: str | None = None, agent_id: str | None = None, authorization_state: str = "NOT_REQUIRED", execution_state: str = "NOT_EXECUTED", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"action": action, "workflow_id": workflow_id, "agent_id": agent_id, "authorization_state": authorization_state, "execution_state": execution_state, "metadata": metadata or {}}
        correlation_id = f"control-{hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:24]}"
        event = {"event_id": f"control-event-{hashlib.sha256((action + correlation_id).encode()).hexdigest()[:24]}", "timestamp": datetime.now(timezone.utc).isoformat(), "event_type": "CONTROL_REQUEST", "component": "operational_control", "status": "RECORDED", "correlation_id": correlation_id, **payload}
        self.audit_log.record("CONTROL_REQUEST", "OPERATIONAL_CONTROL", **event)
        return event

    def system_status(self) -> dict[str, Any]:
        self._request_event("system_status")
        return production_readiness_snapshot(registry=self.orchestrator.registry, scheduler=self.scheduler, state_store=self.state_store, audit_events=self.audit_log.events())

    def list_agents(self) -> list[dict[str, Any]]:
        self._request_event("list_agents")
        return [{"agent_id": agent.agent_id, "name": agent.name, "capabilities": list(agent.capabilities), "allowed_permission_scopes": list(agent.permission_scopes), "action_level": agent.action_level.value, "enabled": agent.enabled} for agent in self.orchestrator.registry.list()]

    def create_workflow(self, objective: str, **options: Any) -> dict[str, Any]:
        record = self.scheduler.schedule(objective, **options)
        self._request_event("create_workflow", workflow_id=record["workflow_id"], authorization_state=record["authorization_state"], metadata={"workflow_type": record["workflow_type"]})
        return record

    def inspect_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        self._request_event("inspect_workflow", workflow_id=workflow_id)
        return self.scheduler.get(workflow_id) or self.state_store.get(workflow_id)

    def workflow_history(self, workflow_id: str) -> list[dict[str, Any]]:
        self._request_event("workflow_history", workflow_id=workflow_id)
        return self.state_store.history(workflow_id)

    def pause_workflow(self, workflow_id: str) -> dict[str, Any]:
        result = self.scheduler.pause(workflow_id)
        self._request_event("pause_workflow", workflow_id=workflow_id, metadata={"status": result["status"]})
        return result

    def resume_workflow(self, workflow_id: str) -> dict[str, Any]:
        result = self.scheduler.resume(workflow_id)
        self._request_event("resume_workflow", workflow_id=workflow_id, authorization_state=result.get("authorization_state", "NOT_REQUIRED"), metadata={"status": result["status"]})
        return result

    def cancel_workflow(self, workflow_id: str) -> dict[str, Any]:
        result = self.scheduler.cancel(workflow_id)
        self._request_event("cancel_workflow", workflow_id=workflow_id, metadata={"status": result["status"]})
        return result

    def retry_workflow(self, workflow_id: str, *, retryable: bool = True) -> dict[str, Any]:
        result = self.scheduler.fail(workflow_id, "operator requested retry", retryable=retryable)
        self._request_event("retry_workflow", workflow_id=workflow_id, authorization_state=result.get("authorization_state", "NOT_REQUIRED"), metadata={"status": result["status"]})
        return result

    def approve_workflow(self, workflow_id: str, approval_id: str) -> dict[str, Any]:
        result = self.scheduler.approve(workflow_id, approval_id)
        self._request_event("approve_workflow", workflow_id=workflow_id, authorization_state=result.get("authorization_state", "PENDING"), metadata={"approval_recorded": True})
        return result

    def reject_workflow(self, workflow_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("rejection reason must not be blank")
        result = self.scheduler._transition(workflow_id, "WAITING_HUMAN", "authorization_denied", authorization_state="DENIED", rejection_reason=reason)
        self._request_event("reject_workflow", workflow_id=workflow_id, authorization_state="DENIED", metadata={"reason": reason})
        return result

    def monitoring_status(self) -> dict[str, Any]:
        self._request_event("monitoring_status")
        return self.system_status()

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        self._request_event("recent_events")
        events = self.scheduler._events()
        return deepcopy(events[-max(0, limit):])

    def authorization_status(self) -> dict[str, Any]:
        pending = self.scheduler.list(authorization_state="PENDING")
        self._request_event("authorization_status", authorization_state="PENDING" if pending else "NOT_REQUIRED")
        return {"pending_count": len(pending), "pending_workflow_ids": [record["workflow_id"] for record in pending], "external_execution_enabled": False}
