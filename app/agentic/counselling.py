from __future__ import annotations

from app.agentic.batch02 import run_existing_ai
from app.agentic.models import AgentContext, Task


def counselling_handler(task: Task, context: AgentContext) -> dict:
    """Adapt the existing AI Agent for counselling and suitability questions."""
    return run_existing_ai("COUNSELLING", task, context)