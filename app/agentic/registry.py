from __future__ import annotations

from collections.abc import Iterable

from app.agentic.models import ActionLevel, AgentSpec


class AgentRegistry:
    def __init__(self, agents: Iterable[AgentSpec] = ()) -> None:
        self._agents: dict[str, AgentSpec] = {}
        for agent in agents:
            self.register(agent)

    def register(self, agent: AgentSpec) -> None:
        normalized_id = agent.agent_id.strip().upper()
        if not normalized_id:
            raise ValueError("agent_id must not be blank")
        if normalized_id in self._agents:
            raise ValueError(f"agent already registered: {normalized_id}")
        self._agents[normalized_id] = agent

    def get(self, agent_id: str) -> AgentSpec:
        try:
            return self._agents[agent_id.strip().upper()]
        except KeyError as exc:
            raise KeyError(f"unknown agent: {agent_id}") from exc

    def list(self) -> tuple[AgentSpec, ...]:
        return tuple(self._agents.values())


_AGENT_NAMES = {
    "ORCHESTRATOR": "Orchestrator",
    "SALES": "Sales",
    "COUNSELLING": "Counselling",
    "CRM": "CRM",
    "FOLLOW_UP": "Follow-up",
    "MEMORY": "Memory",
    "MARKETING": "Marketing",
    "CONTENT": "Content",
    "IMAGE_AD": "Image Advertisement",
    "VIDEO_AD": "Video Advertisement",
    "SOCIAL_MEDIA": "Social Media",
    "ADS": "Ads Campaign",
    "LEAD_GENERATION": "Lead Generation",
    "ANALYTICS": "Analytics",
    "RESEARCH": "Research",
    "SAFETY_AUTH": "Safety and Authorization",
    "COMPUTER_ACTION": "Computer Action",
}


def build_default_registry() -> AgentRegistry:
    specs = []
    for agent_id, name in _AGENT_NAMES.items():
        execute = agent_id in {"CRM", "FOLLOW_UP", "SOCIAL_MEDIA", "ADS", "COMPUTER_ACTION"}
        scopes = ("computer.use",) if agent_id == "COMPUTER_ACTION" else ()
        specs.append(
            AgentSpec(
                agent_id=agent_id,
                name=name,
                description=f"Specialized {name.lower()} agent.",
                capabilities=(agent_id.lower(),),
                permission_scopes=scopes,
                action_level=ActionLevel.EXECUTE if execute else ActionLevel.THINK,
                authorization_requirements=("explicit_human_approval",) if execute else (),
            )
        )
    return AgentRegistry(specs)
