from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CreativeGenerationRequest:
    creative_type: str
    prompt: str
    specification: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreativeGenerationResponse:
    status: str
    creative_type: str
    provider: str
    asset_id: str | None = None
    asset_url: str | None = None
    errors: tuple[str, ...] = ()


class ImageGenerationProvider(Protocol):
    def generate_image(self, request: CreativeGenerationRequest) -> CreativeGenerationResponse: ...
    def generate_variants(self, requests: list[CreativeGenerationRequest]) -> list[CreativeGenerationResponse]: ...
    def get_status(self, asset_id: str) -> CreativeGenerationResponse: ...
    def download_asset(self, asset_id: str) -> bytes: ...


class VideoGenerationProvider(Protocol):
    def generate_video(self, request: CreativeGenerationRequest) -> CreativeGenerationResponse: ...
    def generate_variants(self, requests: list[CreativeGenerationRequest]) -> list[CreativeGenerationResponse]: ...
    def get_status(self, asset_id: str) -> CreativeGenerationResponse: ...
    def download_asset(self, asset_id: str) -> bytes: ...


class UnconfiguredImageGenerationProvider:
    def generate_image(self, request: CreativeGenerationRequest) -> CreativeGenerationResponse:
        return CreativeGenerationResponse("GENERATION_REQUEST_READY", "IMAGE_AD", "unconfigured", errors=("image generation provider is not configured",))

    def generate_variants(self, requests: list[CreativeGenerationRequest]) -> list[CreativeGenerationResponse]:
        return [self.generate_image(request) for request in requests]

    def get_status(self, asset_id: str) -> CreativeGenerationResponse:
        return CreativeGenerationResponse("UNAVAILABLE", "IMAGE_AD", "unconfigured", errors=("image generation provider is not configured",))

    def download_asset(self, asset_id: str) -> bytes:
        raise RuntimeError("image generation provider is not configured")


class UnconfiguredVideoGenerationProvider:
    def generate_video(self, request: CreativeGenerationRequest) -> CreativeGenerationResponse:
        return CreativeGenerationResponse("GENERATION_REQUEST_READY", "VIDEO_AD", "unconfigured", errors=("video generation provider is not configured",))

    def generate_variants(self, requests: list[CreativeGenerationRequest]) -> list[CreativeGenerationResponse]:
        return [self.generate_video(request) for request in requests]

    def get_status(self, asset_id: str) -> CreativeGenerationResponse:
        return CreativeGenerationResponse("UNAVAILABLE", "VIDEO_AD", "unconfigured", errors=("video generation provider is not configured",))

    def download_asset(self, asset_id: str) -> bytes:
        raise RuntimeError("video generation provider is not configured")