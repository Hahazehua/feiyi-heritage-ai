"""Fact-safe multi-platform publication exports for approved Story Studio projects."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from heritagelink.story_distribution_models import (
    PlatformStoryAsset,
    StoryDistributionPackage,
)
from heritagelink.story_models import (
    StoryDecision,
    StoryPlatform,
    StoryProject,
    StoryProjectStatus,
    StoryScene,
)

VERTICAL_ASPECT_RATIO = "9:16"
SUPPORTED_DISTRIBUTION_PLATFORMS = (
    StoryPlatform.XIAOHONGSHU,
    StoryPlatform.TIKTOK,
    StoryPlatform.INSTAGRAM_REELS,
    StoryPlatform.YOUTUBE_SHORTS,
)

_PLATFORM_LABELS = {
    StoryPlatform.XIAOHONGSHU: "小红书 / Xiaohongshu",
    StoryPlatform.TIKTOK: "TikTok",
    StoryPlatform.INSTAGRAM_REELS: "Instagram Reels",
    StoryPlatform.YOUTUBE_SHORTS: "YouTube Shorts",
}
_CTA = {
    "Chinese": {
        StoryPlatform.XIAOHONGSHU: "收藏这段手艺故事，关注下一集。",
        StoryPlatform.TIKTOK: "关注账号，继续看手艺背后的人。",
        StoryPlatform.INSTAGRAM_REELS: "收藏这段故事，认识作品背后的双手。",
        StoryPlatform.YOUTUBE_SHORTS: "订阅频道，观看下一段手艺人故事。",
    },
    "English": {
        StoryPlatform.XIAOHONGSHU: "Save this craft story and follow the next chapter.",
        StoryPlatform.TIKTOK: "Follow to meet more hands behind the craft.",
        StoryPlatform.INSTAGRAM_REELS: "Save this story and meet the hands behind the work.",
        StoryPlatform.YOUTUBE_SHORTS: "Subscribe for the next maker story.",
    },
}
_HASHTAGS = {
    "Chinese": {
        StoryPlatform.XIAOHONGSHU: ("#手艺故事", "#手作过程", "#看见手艺人"),
        StoryPlatform.TIKTOK: ("#CraftStory", "#MadeByHand", "#MeetTheMaker"),
        StoryPlatform.INSTAGRAM_REELS: (
            "#CraftStory",
            "#HandmadeProcess",
            "#MeetTheMaker",
        ),
        StoryPlatform.YOUTUBE_SHORTS: ("#CraftStory", "#MadeByHand", "#Shorts"),
    },
    "English": {
        StoryPlatform.XIAOHONGSHU: ("#CraftStory", "#MadeByHand", "#MeetTheMaker"),
        StoryPlatform.TIKTOK: ("#CraftStory", "#MadeByHand", "#MeetTheMaker"),
        StoryPlatform.INSTAGRAM_REELS: (
            "#CraftStory",
            "#HandmadeProcess",
            "#MeetTheMaker",
        ),
        StoryPlatform.YOUTUBE_SHORTS: ("#CraftStory", "#MadeByHand", "#Shorts"),
    },
}


def build_distribution_package(
    project: StoryProject,
    *,
    now: datetime | None = None,
) -> StoryDistributionPackage:
    """Derive four publication assets without changing the approved factual script."""
    _require_approved_project(project)
    script = project.script
    language = "English" if script.story_core.language.casefold() == "english" else "Chinese"
    fact_reference_ids = tuple(reference.reference_id for reference in script.fact_references)
    source_scene_ids = tuple(scene.scene_id for scene in script.scenes)
    subtitles = build_srt_subtitles(script.scenes)
    generated_at = now or datetime.now(UTC)

    assets = tuple(
        _build_platform_asset(
            project,
            platform,
            language=language,
            fact_reference_ids=fact_reference_ids,
            source_scene_ids=source_scene_ids,
            subtitles=subtitles,
        )
        for platform in SUPPORTED_DISTRIBUTION_PLATFORMS
    )
    decision = project.human_decision
    if decision is None:  # pragma: no cover - guarded by _require_approved_project
        raise ValueError("approved story is missing a human decision")
    return StoryDistributionPackage(
        package_id=f"distribution-{project.project_id}",
        source_project_id=project.project_id,
        source_script_id=script.script_id,
        language=language,
        assets=assets,
        fact_reference_ids=fact_reference_ids,
        guardian_reviewed_at=project.guardian_review.reviewed_at,
        approved_by=decision.actor_id,
        approved_at=decision.decided_at,
        generated_at=generated_at,
    )


def build_srt_subtitles(scenes: tuple[StoryScene, ...]) -> str:
    """Render approved scene voiceover as a continuous UTF-8 SRT track."""
    elapsed = 0
    blocks: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        start = elapsed
        elapsed += scene.duration_seconds
        blocks.append(
            f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(elapsed)}\n{scene.voiceover}"
        )
    return "\n\n".join(blocks) + "\n"


def export_distribution_package_zip(package: StoryDistributionPackage) -> bytes:
    """Export copy, metadata, and subtitles for every supported platform."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                asdict(package),
                ensure_ascii=False,
                indent=2,
                default=_json_default,
            ),
        )
        for asset in package.assets:
            folder = asset.platform.value
            archive.writestr(f"{folder}/post.md", platform_asset_markdown(asset))
            archive.writestr(f"{folder}/subtitles.srt", asset.subtitle_srt)
            archive.writestr(
                f"{folder}/metadata.json",
                json.dumps(
                    asdict(asset),
                    ensure_ascii=False,
                    indent=2,
                    default=_json_default,
                ),
            )
    return buffer.getvalue()


def platform_asset_markdown(asset: PlatformStoryAsset) -> str:
    """Human-readable copy sheet for one publication target."""
    return (
        f"# {asset.title}\n\n"
        f"## Hook\n\n{asset.hook}\n\n"
        f"## Caption\n\n{asset.caption}\n\n"
        f"## Call to action\n\n{asset.call_to_action}\n\n"
        f"## Hashtags\n\n{asset.hashtag_line}\n"
    )


def _build_platform_asset(
    project: StoryProject,
    platform: StoryPlatform,
    *,
    language: str,
    fact_reference_ids: tuple[str, ...],
    source_scene_ids: tuple[str, ...],
    subtitles: str,
) -> PlatformStoryAsset:
    script = project.script
    hook = script.scenes[0].voiceover
    cta = _CTA[language][platform]
    caption = _caption_for(platform, script.title, hook, cta, language)
    return PlatformStoryAsset(
        asset_id=f"{script.script_id}-{platform.value}",
        platform=platform,
        platform_label=_PLATFORM_LABELS[platform],
        title=script.title,
        hook=hook,
        caption=caption,
        call_to_action=cta,
        hashtags=_HASHTAGS[language][platform],
        aspect_ratio=VERTICAL_ASPECT_RATIO,
        target_duration_seconds=script.total_duration_seconds,
        subtitle_srt=subtitles,
        source_scene_ids=source_scene_ids,
        fact_reference_ids=fact_reference_ids,
    )


def _caption_for(
    platform: StoryPlatform,
    title: str,
    hook: str,
    cta: str,
    language: str,
) -> str:
    source_note = (
        "事实来源与审核记录随制作包提供。"
        if language == "Chinese"
        else "Sources and approval records are included in the production package."
    )
    if platform is StoryPlatform.TIKTOK:
        return f"{hook}\n\n{cta}"
    if platform is StoryPlatform.INSTAGRAM_REELS:
        return f"{title}\n\n{hook}\n\n{cta}"
    if platform is StoryPlatform.YOUTUBE_SHORTS:
        return f"{hook}\n\n{source_note}\n\n{cta}"
    return f"{title}\n\n{hook}\n\n{cta}"


def _require_approved_project(project: StoryProject) -> None:
    decision = project.human_decision
    if (
        project.status is not StoryProjectStatus.APPROVED
        or not project.guardian_review.approved
        or decision is None
        or decision.decision is not StoryDecision.APPROVE
    ):
        raise ValueError("multi-platform export requires Guardian and human approval")


def _srt_timestamp(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported distribution export value: {type(value).__name__}")


__all__ = [
    "SUPPORTED_DISTRIBUTION_PLATFORMS",
    "VERTICAL_ASPECT_RATIO",
    "build_distribution_package",
    "build_srt_subtitles",
    "export_distribution_package_zip",
    "platform_asset_markdown",
]
