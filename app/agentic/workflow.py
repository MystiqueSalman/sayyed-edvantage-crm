from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.agentic.models import ActionLevel, AgentContext, TaskStatus


WORKFLOW_STATUSES = {"PENDING", "READY", "RUNNING", "COMPLETED", "BLOCKED", "FAILED", "PAUSED", "CANCELLED", "WAITING_AUTHORIZATION", "WAITING_HUMAN"}


@dataclass
class WorkflowTask:
    task_id: str
    parent_task_id: str | None
    agent: str
    objective: str
    input: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "PENDING"
    execution_level: str = ActionLevel.THINK.value
    authorization_required: bool = False
    result: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    retry_count: int = 0


class TaskGraph:
    def __init__(self, workflow_id: str | None = None) -> None:
        self.workflow_id = workflow_id or f"workflow-{uuid4().hex}"
        self.tasks: dict[str, WorkflowTask] = {}

    def add_task(self, agent: str, objective: str, *, dependencies: list[str] | None = None, execution_level: ActionLevel = ActionLevel.THINK, input: dict[str, Any] | None = None) -> WorkflowTask:
        task = WorkflowTask(
            task_id=f"wtask-{uuid4().hex}", parent_task_id=None, agent=agent,
            objective=objective, input=input or {}, dependencies=dependencies or [],
            status="READY" if not dependencies else "PENDING", execution_level=execution_level.value,
            authorization_required=execution_level is ActionLevel.EXECUTE,
        )
        self.tasks[task.task_id] = task
        return task

    def ready_tasks(self) -> list[WorkflowTask]:
        ready = []
        for task in self.tasks.values():
            if task.status == "READY":
                ready.append(task)
                continue
            if task.status != "PENDING":
                continue
            dependencies = [self.tasks[dependency] for dependency in task.dependencies]
            if all(dependency.status == "COMPLETED" for dependency in dependencies):
                task.status = "READY"
            if task.status == "READY":
                ready.append(task)
        return ready

    def parallel_groups(self) -> list[list[str]]:
        groups: list[list[str]] = []
        for task in self.tasks.values():
            if task.status in {"PENDING", "READY"}:
                group = [candidate.task_id for candidate in self.tasks.values() if candidate.status in {"PENDING", "READY"} and candidate.dependencies == task.dependencies]
                if group and group not in groups:
                    groups.append(group)
        return groups

    def validate(self) -> list[str]:
        errors = []
        for task in self.tasks.values():
            for dependency in task.dependencies:
                if dependency not in self.tasks:
                    errors.append(f"missing dependency: {dependency}")
            if task.status not in WORKFLOW_STATUSES:
                errors.append(f"invalid status: {task.status}")
        return errors

    def snapshot(self, objective: str = "") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        tasks = list(self.tasks.values())
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": "agentic_workflow",
            "objective": objective,
            "status": "COMPLETED" if tasks and all(task.status == "COMPLETED" for task in tasks) else "RUNNING",
            "current_step": next((task.task_id for task in tasks if task.status in {"RUNNING", "READY", "PENDING"}), None),
            "completed_steps": [task.task_id for task in tasks if task.status == "COMPLETED"],
            "pending_steps": [task.task_id for task in tasks if task.status in {"PENDING", "READY", "RUNNING"}],
            "failed_steps": [task.task_id for task in tasks if task.status == "FAILED"],
            "blocked_steps": [task.task_id for task in tasks if task.status in {"BLOCKED", "WAITING_AUTHORIZATION", "WAITING_HUMAN"}],
            "retry_count": sum(task.retry_count for task in tasks),
            "created_timestamp": now,
            "updated_timestamp": now,
            "last_checkpoint": None,
            "authorization_state": {task.task_id: {"required": task.authorization_required, "status": task.status} for task in tasks if task.authorization_required or task.status == "WAITING_AUTHORIZATION"},
            "human_handoff_state": {task.task_id: task.status for task in tasks if task.status == "WAITING_HUMAN"},
            "workflow_context": {"objective": objective},
            "agent_results": {task.task_id: task.result for task in tasks if task.result is not None},
            "tasks": [
                {
                    "task_id": task.task_id, "parent_task_id": task.parent_task_id, "agent": task.agent,
                    "objective": task.objective, "input": task.input, "dependencies": task.dependencies,
                    "status": task.status, "execution_level": task.execution_level,
                    "authorization_required": task.authorization_required, "result": task.result,
                    "errors": task.errors, "retry_count": task.retry_count,
                }
                for task in tasks
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "TaskGraph":
        graph = cls(workflow_id=str(snapshot["workflow_id"]))
        for value in snapshot.get("tasks", []):
            task = WorkflowTask(
                task_id=value["task_id"], parent_task_id=value.get("parent_task_id"), agent=value["agent"],
                objective=value.get("objective", ""), input=value.get("input", {}), dependencies=value.get("dependencies", []),
                status=value.get("status", "PENDING"), execution_level=value.get("execution_level", ActionLevel.THINK.value),
                authorization_required=bool(value.get("authorization_required", False)), result=value.get("result"),
                errors=value.get("errors", []), retry_count=int(value.get("retry_count", 0)),
            )
            graph.tasks[task.task_id] = task
        return graph

    def retry_task(self, task_id: str) -> WorkflowTask:
        task = self.tasks[task_id]
        if task.status != "FAILED":
            raise ValueError("only failed tasks can be retried")
        if task.execution_level == ActionLevel.EXECUTE.value:
            raise ValueError("external tasks require explicit authorization and cannot be automatically retried")
        task.retry_count += 1
        task.status = "READY" if not task.dependencies else "PENDING"
        task.errors = []
        return task


def _external_request(request: str) -> bool:
    return bool(re.search(r"\b(publish|upload|send|message|launch|spend|purchase|change.*lead|modify crm|change budget)\b", request, re.IGNORECASE))


def decompose_request(user_request: str) -> TaskGraph:
    request = str(user_request or "").strip()
    graph = TaskGraph()
    value = request.lower()
    external = _external_request(request)
    if "analy" in value and "research" in value:
        analytics = graph.add_task("ANALYTICS", "Analyze internal performance")
        research = graph.add_task("RESEARCH", "Prepare external research request")
        graph.add_task("ANALYTICS", "Synthesize analytics and research", dependencies=[analytics.task_id, research.task_id])
        return graph
    if re.search(r"\b(open browser|navigate|click|type|upload|download|computer|screenshot)\b", value):
        level = ActionLevel.EXECUTE if re.search(r"\b(click|type|upload|download|publish|send)\b", value) else ActionLevel.THINK
        action = graph.add_task("COMPUTER_ACTION", "Plan computer/browser action", execution_level=level, input={"action": request})
        if level is ActionLevel.EXECUTE:
            graph.add_task("SAFETY_AUTH", "Validate computer action", dependencies=[action.task_id], input={"action": request})
        return graph
    if any(marker in value for marker in ("complete", "campaign", "advertisement")) and any(course in value for course in ("data science", "data analytics", "python", "devops", "linux", "ai")):
        marketing = graph.add_task("MARKETING", "Prepare campaign strategy")
        content = graph.add_task("CONTENT", "Prepare campaign copy", dependencies=[marketing.task_id], execution_level=ActionLevel.PREPARE)
        image = graph.add_task("IMAGE_AD", "Prepare image creative", dependencies=[marketing.task_id], execution_level=ActionLevel.PREPARE)
        video = graph.add_task("VIDEO_AD", "Prepare video creative", dependencies=[marketing.task_id], execution_level=ActionLevel.PREPARE)
        creative_dependencies = [content.task_id, image.task_id, video.task_id]
        graph.add_task("SOCIAL_MEDIA", "Prepare social distribution", dependencies=creative_dependencies, execution_level=ActionLevel.PREPARE)
        graph.add_task("ADS", "Prepare advertising plan", dependencies=creative_dependencies, execution_level=ActionLevel.PREPARE)
        graph.add_task("LEAD_GENERATION", "Prepare lead capture plan", dependencies=[marketing.task_id], execution_level=ActionLevel.PREPARE)
        if external:
            graph.add_task("SAFETY_AUTH", "Validate external campaign action", dependencies=[task.task_id for task in graph.tasks.values()], input={"action": request})
        return graph
    if any(marker in value for marker in ("enquiry", "inquiry", "student") ) and "follow" in value:
        sales = graph.add_task("SALES", "Understand student enquiry")
        counselling = graph.add_task("COUNSELLING", "Assess counselling needs", dependencies=[sales.task_id], execution_level=ActionLevel.PREPARE)
        memory = graph.add_task("MEMORY", "Retrieve relevant conversation", dependencies=[counselling.task_id])
        crm = graph.add_task("CRM", "Retrieve lead context", dependencies=[memory.task_id])
        follow = graph.add_task("FOLLOW_UP", "Prepare next follow-up", dependencies=[crm.task_id], execution_level=ActionLevel.PREPARE)
        graph.add_task("SAFETY_AUTH", "Validate follow-up action", dependencies=[follow.task_id], input={"action": request})
        return graph
    if external:
        agent = "SOCIAL_MEDIA" if any(marker in value for marker in ("publish", "upload", "post", "message")) else "ADS" if any(marker in value for marker in ("ad", "campaign", "budget", "spend", "launch")) else "CRM" if any(marker in value for marker in ("lead", "crm")) else "SOCIAL_MEDIA"
        action = graph.add_task(agent, "Prepare requested external action", execution_level=ActionLevel.PREPARE, input={"action": request})
        graph.add_task("SAFETY_AUTH", "Validate external action", dependencies=[action.task_id], input={"action": request})
        return graph
    agent = "RESEARCH" if "research" in value else "ANALYTICS" if any(marker in value for marker in ("analy", "funnel", "metric", "lead")) else "MARKETING"
    graph.add_task(agent, "Complete requested objective", execution_level=ActionLevel.PREPARE if agent == "RESEARCH" else ActionLevel.THINK)
    return graph


def aggregate_workflow(graph: TaskGraph, objective: str) -> dict[str, Any]:
    tasks = list(graph.tasks.values())
    conflicts = []
    claims: dict[str, Any] = {}
    observations = []
    recommendations = []
    for task in tasks:
        if not task.result:
            continue
        for observation in task.result.get("observations", []):
            observations.append(observation)
        recommendations.extend(task.result.get("recommendations", []))
        for key, value in task.result.items():
            if key in {"status", "errors", "agent", "agent_id"} or not isinstance(value, (str, int, float)):
                continue
            if key in claims and claims[key] != value:
                conflicts.append({"source": task.agent, "claim": claims[key], "conflicting_claim": value, "affected_task": task.task_id, "required_resolution": "human review"})
            claims[key] = value
    blocked = [task for task in tasks if task.status in {"BLOCKED", "PAUSED", "WAITING_AUTHORIZATION", "WAITING_HUMAN"}]
    failed = [task for task in tasks if task.status == "FAILED"]
    return {
        "workflow_id": graph.workflow_id, "objective": objective,
        "completed_tasks": [task.task_id for task in tasks if task.status == "COMPLETED"],
        "blocked_tasks": [task.task_id for task in blocked], "failed_tasks": [task.task_id for task in failed],
        "agent_results": [{"task_id": task.task_id, "agent": task.agent, "status": task.status, "result": task.result, "errors": task.errors} for task in tasks],
        "observations": observations, "recommendations": list(dict.fromkeys(recommendations)),
        "authorization_required": any(task.authorization_required or (task.result or {}).get("authorization_required", False) for task in tasks),
        "human_handoff_required": bool(blocked or conflicts), "conflicts": conflicts,
        "final_status": "WAITING_AUTHORIZATION" if any(task.status == "WAITING_AUTHORIZATION" or (task.agent == "SAFETY_AUTH" and (task.result or {}).get("authorization_required", False)) for task in tasks) else "CONFLICT_DETECTED" if conflicts else "PAUSED" if any(task.status == "PAUSED" for task in tasks) else "WAITING_HUMAN" if blocked else "FAILED" if failed else "COMPLETED",
        "workflow_context": {"pending_tasks": [task.task_id for task in tasks if task.status in {"PENDING", "READY"}], "errors": [error for task in tasks for error in task.errors]},
    }


def execute_workflow(graph: TaskGraph, objective: str, handlers: dict[str, Callable], orchestrator: Any, session_id: str | None = None, state_store: Any = None, max_tasks: int | None = None) -> dict[str, Any]:
    executed_count = 0

    def checkpoint(event_type: str, **metadata: Any) -> None:
        if state_store is not None:
            state_store.checkpoint(graph.workflow_id, event_type, graph.snapshot(objective), **metadata)

    orchestrator.audit_log.record("WORKFLOW_CREATED", "ORCHESTRATOR", workflow_id=graph.workflow_id, objective=objective)
    orchestrator.audit_log.record("TASK_DECOMPOSED", "ORCHESTRATOR", workflow_id=graph.workflow_id, task_count=len(graph.tasks))
    checkpoint("workflow_created")
    while True:
        ready = graph.ready_tasks()
        if not ready:
            break
        for workflow_task in ready:
            if max_tasks is not None and executed_count >= max_tasks:
                for remaining in graph.tasks.values():
                    if remaining.status in {"READY", "PENDING"}:
                        remaining.status = "PAUSED"
                checkpoint("workflow_paused")
                return aggregate_workflow(graph, objective)
            workflow_task.status = "RUNNING"
            checkpoint("task_started", task_id=workflow_task.task_id, agent=workflow_task.agent)
            handler = handlers.get(workflow_task.agent)
            if handler is None:
                workflow_task.status = "BLOCKED"
                workflow_task.errors.append(f"no handler registered: {workflow_task.agent}")
                checkpoint("task_blocked", task_id=workflow_task.task_id)
                continue
            orchestrator.register_handler(workflow_task.agent, handler)
            task = __import__("app.agentic.models", fromlist=["Task"]).Task(user_request=objective, agent_id=workflow_task.agent, input=workflow_task.input, action_level=ActionLevel(workflow_task.execution_level))
            result = orchestrator.run(task, AgentContext(user_request=objective, session_id=session_id, current_task_id=workflow_task.task_id))
            workflow_task.result = result.output or {"errors": [result.error] if result.error else []}
            if result.status is TaskStatus.COMPLETED or (workflow_task.agent != "SAFETY_AUTH" and workflow_task.input.get("action") and result.status is TaskStatus.BLOCKED):
                workflow_task.status = "COMPLETED"
                if result.status is TaskStatus.BLOCKED:
                    workflow_task.result = {**workflow_task.result, "status": "prepared", "input_required": True}
            elif result.status is TaskStatus.WAITING_AUTHORIZATION:
                workflow_task.status = "WAITING_AUTHORIZATION"
                workflow_task.authorization_required = True
                checkpoint("authorization_required", task_id=workflow_task.task_id)
            else:
                workflow_task.status = "FAILED" if result.status is TaskStatus.FAILED else "BLOCKED"
                if result.error:
                    workflow_task.errors.append(result.error)
                checkpoint("task_failed" if workflow_task.status == "FAILED" else "task_blocked", task_id=workflow_task.task_id)
            if workflow_task.status == "COMPLETED":
                checkpoint("task_completed", task_id=workflow_task.task_id)
            executed_count += 1
            orchestrator.audit_log.record("TASK_RESULT_AGGREGATED", "ORCHESTRATOR", workflow_id=graph.workflow_id, task_id=workflow_task.task_id, agent=workflow_task.agent, status=workflow_task.status)
    if any(task.status == "PENDING" for task in graph.tasks.values()):
        for task in graph.tasks.values():
            if task.status == "PENDING":
                task.status = "BLOCKED"
                task.errors.append("dependency not satisfied")
        checkpoint("workflow_paused")
    result = aggregate_workflow(graph, objective)
    checkpoint("workflow_completed" if result["final_status"] == "COMPLETED" else "workflow_paused")
    orchestrator.audit_log.record("WORKFLOW_RESULT_AGGREGATED", "ORCHESTRATOR", workflow_id=graph.workflow_id, final_status=result["final_status"])
    return result


def resume_workflow(workflow_id: str, objective: str, handlers: dict[str, Callable], orchestrator: Any, state_store: Any, session_id: str | None = None, max_tasks: int | None = None) -> dict[str, Any]:
    snapshot = state_store.get(workflow_id)
    if snapshot is None:
        raise KeyError(f"workflow not found: {workflow_id}")
    graph = TaskGraph.from_snapshot(snapshot)
    for task in graph.tasks.values():
        if task.status == "RUNNING":
            task.status = "READY" if not task.dependencies else "PENDING"
        elif task.status == "PAUSED":
            task.status = "READY" if not task.dependencies or all(graph.tasks[dependency].status == "COMPLETED" for dependency in task.dependencies) else "PENDING"
    if any(task.status == "WAITING_AUTHORIZATION" for task in graph.tasks.values()):
        state_store.checkpoint(workflow_id, "workflow_paused", graph.snapshot(objective), reason="authorization remains pending")
        return aggregate_workflow(graph, objective)
    return execute_workflow(graph, objective, handlers, orchestrator, session_id=session_id, state_store=state_store, max_tasks=max_tasks)