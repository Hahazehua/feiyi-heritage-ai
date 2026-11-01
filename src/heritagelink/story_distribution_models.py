"""Typed contracts for fact-safe multi-platform Story Studio exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from heritagelink.story_models import StoryPlatform


@dataclass(frozen=True, slots=True)
class PlatformStoryAsset:
    """One platform's copy and subtitle package derived from an approved script."""

    asset_id: str
    platform: StoryPlatform
    platform_label: str
    title: str
    hook: str
    caption: str
    call_to_action: str
    hashtags: tuple[str, ...]
    aspect_ratio: str
    target_duration_seconds: int
    subtitle_srt: str
    source_scene_ids: tuple[str, ...]
    fact_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        required = (
            self.asset_id,
            self.platform_label,
            self.title,
            self.hook,
            self.caption,
            self.call_to_action,
            self.aspect_ratio,
            self.subtitle_srt,
        )
        if not all(value.strip() for value in required):
            raise ValueError("platform story asset fields cannot be blank")
        if self.target_duration_seconds < 1:
            raise ValueError("platform story asset duration must be positive")
        if not self.source_scene_ids:
            raise ValueError("platform story asset requires source scenes")
        if len(set(self.source_scene_ids)) != len(self.source_scene_ids):
            raise ValueError("platform story source scene ids must be unique")
        if len(set(self.fact_reference_ids)) != len(self.fact_reference_ids):
            raise ValueError("platform story fact reference ids must be unique")
        if not self.hashtags or any(not tag.startswith("#") for tag in self.hashtags):
            raise ValueError("platform story hashtags must be non-empty and start with #")

    @property
    def hashtag_line(self) -> str:
        return " ".join(self.hashtags)


@dataclass(frozen=True, slots=True)
class StoryDistributionPackage:
    """A four-platform snapshot of one Guardian- and human-approved story."""

    package_id: str
    source_project_id: str
    source_script_id: str
    language: str
    assets: tuple[PlatformStoryAsset, ...]
    fact_reference_ids: tuple[str, ...]
    guardian_reviewed_at: datetime
    approved_by: str
    approved_at: datetime
    generated_at: datetime

    def __post_init__(self) -> None:
        identity = (
            self.package_id,
            self.source_project_id,
            self.source_script_id,
            self.language,
            self.approved_by,
        )
        if not all(value.strip() for value in identity):
            raise ValueError("distribution package requires source and approval identity")
        if any(
            value.tzinfo is None
            for value in (self.guardian_reviewed_at, self.approved_at, self.generated_at)
        ):
            raise ValueError("distribution package timestamps must include timezone")
        if not self.assets:
            raise ValueError("distribution package requires at least one platform asset")
        platforms = [asset.platform for asset in self.assets]
        if len(set(platforms)) != len(platforms):
            raise ValueError("distribution package platforms must be unique")
        if len(set(self.fact_reference_ids)) != len(self.fact_reference_ids):
            raise ValueError("distribution package fact reference ids must be unique")
        allowed_references = set(self.fact_reference_ids)
        for asset in self.assets:
            if not set(asset.fact_reference_ids) <= allowed_references:
                raise ValueError("platform asset references facts outside the approved script")

    @property
    def assets_by_platform(self) -> dict[StoryPlatform, PlatformStoryAsset]:
        return {asset.platform: asset for asset in self.assets}


__all__ = ["PlatformStoryAsset", "StoryDistributionPackage"]
