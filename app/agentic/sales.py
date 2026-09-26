from __future__ import annotations

from app.agentic.batch02 import run_existing_ai
from app.agentic.models import AgentContext, Task


def sales_handler(task: Task, context: AgentContext) -> dict:
    """Adapt the existing AI Agent for read-only sales qualification."""
    return run_existing_ai("SALES", task, context)