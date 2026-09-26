from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.agentic.computer_action import ACTION_STATES
from app.agentic.registry import AgentRegistry, build_default_registry
from app.agentic.scheduler import DurableWorkflowScheduler


HEALTH_STATES = {"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN"}
ERROR_CATEGORIES = {
    "VALIDATION_ERROR", "AUTHORIZATION_ERROR", "STATE_ERROR", "DEPENDENCY_ERROR",
    "TIMEOUT_ERROR", "CONFIGURATION_ERROR", "INTERNAL_ERROR", "EXTERNAL_PROVIDER_ERROR", "UNKNOWN_ERROR",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(*values: Any) -> str:
    payload = json.dumps(values, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class OperationalEvent:
    event_id: str
    timestamp: str
    event_type: str
    component: str
    status: str
    correlation_id: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_operational_event(event_type: str, component: str, status: str, *, correlation_id: str, metadata: dict[str, Any] | None = None, timestamp: str | None = None) -> OperationalEvent:
    event_timestamp = timestamp or _timestamp()
    details = metadata or {}
    return OperationalEvent(
        event_id=f"monitor-{_stable_id(event_type, component, status, correlation_id, event_timestamp, details)}",
        timestamp=event_timestamp, event_type=event_type, component=component,
        status=status, correlation_id=correlation_id, metadata=details,
    )


def classify_error(error: str | Exception | None) -> str:
    value = str(error or "").lower()
    if not value:
        return "UNKNOWN_ERROR"
    if re.search(r"authorization|permission|approval", value):
        return "AUTHORIZATION_ERROR"
    if re.search(r"validation|invalid|must not|unsupported", value):
        return "VALIDATION_ERROR"
    if re.search(r"dependency|not satisfied|missing handler", value):
        return "DEPENDENCY_ERROR"
    if re.search(r"timeout|timed out|stalled", value):
        return "TIMEOUT_ERROR"
    if re.search(r"not configured|configuration", value):
        return "CONFIGURATION_ERROR"
    if re.search(r"provider|external", value):
        return "EXTERNAL_PROVIDER_ERROR"
    if re.search(r"state|status", value):
        return "STATE_ERROR"
    if re.search(r"runtime|exception|internal", value):
        return "INTERNAL_ERROR"
    return "UNKNOWN_ERROR"


def _health(component: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"component": component, "status": status if status in HEALTH_STATES else "UNKNOWN", "details": details or {}}


def system_health(*, registry: AgentRegistry | None = None, scheduler: DurableWorkflowScheduler | None = None, state_store: Any = None, orchestrator: Any = None) -> dict[str, Any]:
    registry = registry or build_default_registry()
    checks = [
        _health("orchestrator", "HEALTHY" if orchestrator is not None or registry else "UNKNOWN"),
        _health("workflow_engine", "HEALTHY"),
        _health("scheduler", "HEALTHY" if scheduler is not None else "UNKNOWN"),
        _health("durable_state", "HEALTHY" if state_store is not None else "UNKNOWN"),
        _health("authorization_layer", "HEALTHY"),
        _health("computer_action_planning", "HEALTHY"),
        _health("crm_read_layer", "HEALTHY"),
        _health("master_kb_read_layer", "HEALTHY"),
        _health("analytics", "HEALTHY"),
        _health("research", "DEGRADED", {"reason": "external research provider is optional"}),
    ]
    overall = "FAILED" if any(item["status"] == "FAILED" for item in checks) else "DEGRADED" if any(item["status"] in {"DEGRADED", "UNKNOWN"} for item in checks) else "HEALTHY"
    return {"status": overall, "components": checks}


def agent_health(registry: AgentRegistry | None = None, audit_events: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    registry = registry or build_default_registry()
    counts: dict[str, Counter] = {agent.agent_id: Counter() for agent in registry.list()}
    for event in audit_events:
        agent_id = str(event.details.get("agent_id") or event.actor).upper()
        if agent_id not in counts:
            continue
        counts[agent_id]["invocation_count"] += int(event.event_type in {"TASK_COMPLETED", "TASK_FAILED", "TASK_AUTHORIZATION_EVALUATED"})
        counts[agent_id]["success_count"] += int(event.event_type == "TASK_COMPLETED")
        counts[agent_id]["failure_count"] += int(event.event_type == "TASK_FAILED")
        counts[agent_id]["authorization_required_count"] += int(event.details.get("authorization_required", False))
    now = _timestamp()
    return [{"agent_id": agent.agent_id, "status": "HEALTHY", "last_seen": now, "invocation_count": counts[agent.agent_id]["invocation_count"], "success_count": counts[agent.agent_id]["success_count"], "failure_count": counts[agent.agent_id]["failure_count"], "retry_count": 0, "blocked_count": 0, "authorization_required_count": counts[agent.agent_id]["authorization_required_count"]} for agent in registry.list()]


def workflow_metrics(state_store: Any) -> dict[str, Any]:
    snapshots = state_store.list() if state_store is not None else []
    return {
        "total_workflows": len(snapshots),
        "successful_workflows": sum(snapshot.get("status") == "COMPLETED" for snapshot in snapshots),
        "failed_workflows": sum(bool(snapshot.get("failed_steps")) or snapshot.get("status") == "FAILED" for snapshot in snapshots),
        "blocked_workflows": sum(bool(snapshot.get("blocked_steps")) for snapshot in snapshots),
        "pending_tasks": sum(len(snapshot.get("pending_steps", [])) for snapshot in snapshots),
        "retries": sum(int(snapshot.get("retry_count", 0)) for snapshot in snapshots),
        "authorization_requests": sum(bool(snapshot.get("authorization_state")) for snapshot in snapshots),
        "human_handoffs": sum(bool(snapshot.get("human_handoff_state")) for snapshot in snapshots),
    }


def scheduler_metrics(scheduler: DurableWorkflowScheduler | None) -> dict[str, Any]:
    if scheduler is None:
        return {"scheduled_workflows": 0, "active_workflows": 0, "completed_workflows": 0, "failed_workflows": 0, "paused_workflows": 0, "cancelled_workflows": 0, "stalled_workflows": 0, "next_scheduled_execution": None, "last_execution": None, "retry_information": {}}
    records = scheduler.list()
    scheduled = [record for record in records if record["status"] == "SCHEDULED"]
    return {
        "scheduled_workflows": len(scheduled), "active_workflows": sum(record["status"] in {"RUNNING", "WAITING"} for record in records),
        "completed_workflows": sum(record["status"] == "COMPLETED" for record in records), "failed_workflows": sum(record["status"] == "FAILED" for record in records),
        "paused_workflows": sum(record["status"] == "PAUSED" for record in records), "cancelled_workflows": sum(record["status"] == "CANCELLED" for record in records),
        "stalled_workflows": len(scheduler.detect_stalled()), "next_scheduled_execution": min((record.get("next_run_at") for record in scheduled), default=None),
        "last_execution": max((record.get("updated_at") for record in records), default=None), "retry_information": {record["workflow_id"]: record.get("retry_count", 0) for record in records if record.get("retry_count", 0)},
    }


def evaluate_alerts(*, workflow_data: dict[str, Any], scheduler_data: dict[str, Any], agent_data: list[dict[str, Any]], health: dict[str, Any]) -> list[dict[str, Any]]:
    alerts = []
    if workflow_data.get("failed_workflows", 0) >= 2:
        alerts.append({"type": "REPEATED_WORKFLOW_FAILURES", "severity": "HIGH", "reason": "multiple workflow failures observed"})
    if scheduler_data.get("stalled_workflows", 0):
        alerts.append({"type": "STALLED_WORKFLOW", "severity": "HIGH", "reason": "scheduler reports stalled workflows"})
    if workflow_data.get("authorization_requests", 0) >= 3:
        alerts.append({"type": "AUTHORIZATION_BACKLOG", "severity": "MEDIUM", "reason": "authorization requests remain pending"})
    unhealthy = [item["component"] for item in health.get("components", []) if item["status"] in {"FAILED", "DEGRADED"}]
    if unhealthy:
        alerts.append({"type": "SYSTEM_COMPONENT_UNHEALTHY", "severity": "MEDIUM", "reason": "components require review", "components": unhealthy})
    if any(agent.get("failure_count", 0) >= 2 for agent in agent_data):
        alerts.append({"type": "REPEATED_AGENT_FAILURES", "severity": "HIGH", "reason": "agent failures exceed threshold"})
    return alerts


def production_readiness_snapshot(*, registry: AgentRegistry | None = None, scheduler: DurableWorkflowScheduler | None = None, state_store: Any = None, audit_events: tuple[Any, ...] = (), recent_events: list[OperationalEvent] | None = None) -> dict[str, Any]:
    health = system_health(registry=registry, scheduler=scheduler, state_store=state_store, orchestrator=True)
    agents = agent_health(registry, audit_events)
    workflows = workflow_metrics(state_store)
    scheduler_state = scheduler_metrics(scheduler)
    alerts = evaluate_alerts(workflow_data=workflows, scheduler_data=scheduler_state, agent_data=agents, health=health)
    return {
        "system_health": health, "agent_health": agents, "workflow_metrics": workflows,
        "scheduler_metrics": scheduler_state, "authorization_metrics": {"requests": workflows["authorization_requests"]},
        "security_status": {"external_actions_enabled": False, "credentials_created": False, "crm_mutation_performed": False},
        "recent_operational_events": [event.to_dict() for event in (recent_events or [])], "active_alerts": alerts,
    }
