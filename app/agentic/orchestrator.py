from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agentic.audit import AuditLog
from app.agentic.authorization import AuthorizationBoundary
from app.agentic.models import AgentContext, Task, TaskStatus, utc_now
from app.agentic.registry import AgentRegistry, build_default_registry

Handler = Callable[[Task, AgentContext], dict[str, Any]]


class Orchestrator:
    def __init__(
        self,
        registry: AgentRegistry | None = None,
        authorization: AuthorizationBoundary | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.authorization = authorization or AuthorizationBoundary()
        self.audit_log = audit_log or AuditLog()
        self._handlers: dict[str, Handler] = {}

    def register_handler(self, agent_id: str, handler: Handler) -> None:
        normalized_id = agent_id.strip().upper()
        self.registry.get(normalized_id)
        self._handlers[normalized_id] = handler

    def run(self, task: Task, context: AgentContext) -> Task:
        agent = self.registry.get(task.agent_id)
        if not agent.enabled:
            task.status = TaskStatus.BLOCKED
            task.error = f"agent is disabled: {agent.agent_id}"
            return task

        decision = self.authorization.evaluate(task, agent)
        audit = self.audit_log.record(
            "TASK_AUTHORIZATION_EVALUATED",
            "ORCHESTRATOR",
            task_id=task.task_id,
            agent_id=agent.agent_id,
            approved=decision.approved,
            authorization_required=decision.authorization_required,
        )
        task.audit_id = audit.event_id
        if decision.authorization_required and not decision.approved:
            task.status = TaskStatus.WAITING_AUTHORIZATION
            return task

        handler = self._handlers.get(agent.agent_id)
        if handler is None:
            task.status = TaskStatus.BLOCKED
            task.error = f"no handler registered for agent: {agent.agent_id}"
            return task

        task.status = TaskStatus.RUNNING
        task.started_at = utc_now()
        try:
            task.output = handler(task, context)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            self.audit_log.record(
                "TASK_FAILED", agent.agent_id, task_id=task.task_id, error=str(exc)
            )
            return task

        task.status = TaskStatus.COMPLETED
        task.completed_at = utc_now()
        self.audit_log.record("TASK_COMPLETED", agent.agent_id, task_id=task.task_id)
        return task

    def run_authorized(self, task: Task, context: AgentContext, approval_id: str) -> Task:
        self.authorization.approve(task, approval_id)
        return self.run(task, context)
