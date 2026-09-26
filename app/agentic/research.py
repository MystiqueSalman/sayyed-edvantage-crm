from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.agentic.models import AgentContext, Task


@dataclass(frozen=True)
class ResearchRequest:
    query: str
    scope: str
    required_evidence: tuple[str, ...] = ("source", "date", "claim", "evidence", "confidence", "limitation")


class ResearchProvider(Protocol):
    def search(self, request: ResearchRequest) -> dict[str, Any]: ...


class UnconfiguredResearchProvider:
    def search(self, request: ResearchRequest) -> dict[str, Any]:
        return {"status": "RESEARCH_REQUEST_READY", "sources": [], "findings": [], "limitations": ["External research provider is not configured"], "confidence": "unknown", "external_action_required": False}


def research_handler(task: Task, context: AgentContext, provider: ResearchProvider | None = None) -> dict[str, Any]:
    query = str(task.input.get("query") or task.user_request).strip()
    scope = str(task.input.get("scope", "market and education-industry research"))
    result = (provider or UnconfiguredResearchProvider()).search(ResearchRequest(query, scope))
    sources = []
    for source in result.get("sources", []):
        if isinstance(source, dict) and {"source", "date", "claim", "evidence", "confidence", "limitation"} <= set(source):
            sources.append(source)
    return {
        "agent": "RESEARCH", "agent_id": "RESEARCH", "query": query, "status": result.get("status", "RESEARCH_REQUEST_READY"),
        "scope": scope, "sources": sources, "findings": result.get("findings", []),
        "limitations": result.get("limitations", ["No verified external source was supplied"]),
        "confidence": result.get("confidence", "unknown"), "external_action_required": bool(result.get("external_action_required", False)),
        "authorization_required": False, "execution_performed": False,
    }