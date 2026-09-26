from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PlatformActionRequest:
    action: str
    platform: str
    campaign: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformActionResponse:
    status: str
    provider: str
    execution_performed: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


class SocialMediaProvider(Protocol):
    def execute(self, request: PlatformActionRequest) -> PlatformActionResponse: ...


class AdsProvider(Protocol):
    def execute(self, request: PlatformActionRequest) -> PlatformActionResponse: ...


class LeadSourceProvider(Protocol):
    def execute(self, request: PlatformActionRequest) -> PlatformActionResponse: ...


class UnconfiguredPlatformProvider:
    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def execute(self, request: PlatformActionRequest) -> PlatformActionResponse:
        return PlatformActionResponse(
            status="PROVIDER_NOT_CONFIGURED",
            provider=self.provider_name,
            errors=(f"{self.provider_name} provider is not configured",),
        )