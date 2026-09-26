from __future__ import annotations

from uuid import uuid4

from app.agentic.models import (
    ActionLevel,
    AgentSpec,
    AuthorizationDecision,
    AuthorizationStatus,
    Task,
)


class AuthorizationBoundary:
    """Single decision point for actions that can affect external state."""

    def evaluate(self, task: Task, agent: AgentSpec) -> AuthorizationDecision:
        if task.action_level is not ActionLevel.EXECUTE:
            return AuthorizationDecision(
                action=task.input.get("action", task.agent_id),
                risk="internal",
                authorization_required=False,
                approved=True,
                reason="Think and prepare actions do not mutate external state.",
            )

        task.authorization_required = True
        if task.authorization_status is AuthorizationStatus.APPROVED:
            return AuthorizationDecision(
                action=task.input.get("action", task.agent_id),
                risk="external_write",
                authorization_required=True,
                approved=True,
                reason="Explicit authorization recorded.",
            )
        task.authorization_status = AuthorizationStatus.PENDING
        return AuthorizationDecision(
            action=task.input.get("action", task.agent_id),
            risk="external_write",
            authorization_required=True,
            approved=False,
            reason=f"{agent.name} requires explicit authorization before execution.",
        )

    def approve(self, task: Task, approval_id: str) -> AuthorizationDecision:
        if not approval_id.strip():
            raise ValueError("approval_id must not be blank")
        if not task.authorization_required:
            raise ValueError("task does not require authorization")
        task.authorization_status = AuthorizationStatus.APPROVED
        return AuthorizationDecision(
            action=task.input.get("action", task.agent_id),
            risk="external_write",
            authorization_required=True,
            approved=True,
            approval_id=approval_id,
            reason="Explicit authorization recorded.",
        )

    def approval_token(self) -> str:
        return f"approval-{uuid4().hex}"
