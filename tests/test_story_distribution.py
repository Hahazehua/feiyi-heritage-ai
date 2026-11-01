from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import pytest

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.story_distribution_service import (
    SUPPORTED_DISTRIBUTION_PLATFORMS,
    build_distribution_package,
    export_distribution_package_zip,
)
from heritagelink.story_models import StoryDecision, StoryPlatform
from heritagelink.story_service import create_story_project, decide_story_project

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _fact(field_name: str, value: object, *, verified: bool = True) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=(EvidenceStatus.VERIFIED if verified else EvidenceStatus.UNVERIFIED),
        source=FactSource.PUBLIC_SOURCE if verified else FactSource.ARTISAN_PROVIDED,
        verification_status=(
            VerificationStatus.CONFIRMED if verified else VerificationStatus.PENDING_REVIEW
        ),
        source_note="公开资料" if verified else "手艺人口述，待确认",
        source_url="https://example.org/craft" if verified else None,
    )


@pytest.fixture
def context() -> GrowthProductContext:
    return GrowthProductContext(
        artisan_id="artisan-001",
        product_id="iron-picture-001",
        product_name="迎客松铁画",
        product_name_en="Welcoming Pine Iron Picture",
        craft_name="芜湖铁画",
        publication_status=PublicationStatus.RECOMMENDABLE,
        verified_facts=(
            _fact("product_name", "迎客松铁画"),
            _fact("craft_name", "芜湖铁画"),
            _fact("region", "安徽芜湖"),
            _fact("materials", ("低碳钢", "木框")),
            _fact("craft_process", "锻打、焊接与整形"),
        ),
        unverified_facts=(
            _fact("artisan_credentials", "国家级大师", verified=False),
            _fact("international_shipping", "保证全球配送", verified=False),
        ),
        unknown_fields=("certification",),
    )


def _approved_project(context: GrowthProductContext, *, language: str = "Chinese"):
    project = create_story_project(context, language=language, now=NOW)
    return decide_story_project(
        project,
        StoryDecision.APPROVE,
        actor_id=context.artisan_id,
        note="事实与表达已确认",
        now=NOW,
    )


def test_distribution_requires_guardian_and_human_approval(
    context: GrowthProductContext,
) -> None:
    project = create_story_project(context, now=NOW)

    with pytest.raises(ValueError, match="Guardian and human approval"):
        build_distribution_package(project, now=NOW)


def test_builds_four_platforms_from_one_approved_fact_set(
    context: GrowthProductContext,
) -> None:
    project = _approved_project(context)
    package = build_distribution_package(project, now=NOW)
    expected_references = tuple(
        reference.reference_id for reference in project.script.fact_references
    )

    assert tuple(asset.platform for asset in package.assets) == SUPPORTED_DISTRIBUTION_PLATFORMS
    assert set(package.assets_by_platform) == set(StoryPlatform)
    assert package.fact_reference_ids == expected_references
    assert package.approved_by == "artisan-001"
    assert package.guardian_reviewed_at == NOW
    assert package.approved_at == NOW
    assert package.generated_at == NOW

    for asset in package.assets:
        assert asset.aspect_ratio == "9:16"
        assert asset.target_duration_seconds == 60
        assert asset.fact_reference_ids == expected_references
        assert asset.source_scene_ids == tuple(scene.scene_id for scene in project.script.scenes)
        public_output = "\n".join(
            (
                asset.title,
                asset.hook,
                asset.caption,
                asset.call_to_action,
                asset.hashtag_line,
                asset.subtitle_srt,
            )
        )
        assert "国家级大师" not in public_output
        assert "保证全球配送" not in public_output


def test_platform_copy_and_sixty_second_subtitles_are_deterministic(
    context: GrowthProductContext,
) -> None:
    project = _approved_project(context)
    first = build_distribution_package(project, now=NOW)
    second = build_distribution_package(project, now=NOW)

    assert first == second
    assert len({asset.caption for asset in first.assets}) == 4
    assert first.assets_by_platform[StoryPlatform.TIKTOK].call_to_action.startswith("关注")
    assert "00:00:00,000 --> 00:00:05,000" in first.assets[0].subtitle_srt
    assert "00:00:53,000 --> 00:01:00,000" in first.assets[0].subtitle_srt
    assert first.assets[0].subtitle_srt.count(" --> ") == 6


def test_english_master_produces_english_platform_controls(
    context: GrowthProductContext,
) -> None:
    package = build_distribution_package(_approved_project(context, language="English"), now=NOW)

    assert package.language == "English"
    assert package.assets_by_platform[StoryPlatform.YOUTUBE_SHORTS].call_to_action == (
        "Subscribe for the next maker story."
    )
    assert all("#CraftStory" in asset.hashtags for asset in package.assets)


def test_distribution_zip_contains_copy_metadata_and_srt_for_each_platform(
    context: GrowthProductContext,
) -> None:
    package = build_distribution_package(_approved_project(context), now=NOW)
    archive_bytes = export_distribution_package_zip(package)

    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        for platform in SUPPORTED_DISTRIBUTION_PLATFORMS:
            folder = platform.value
            assert f"{folder}/post.md" in names
            assert f"{folder}/metadata.json" in names
            assert f"{folder}/subtitles.srt" in names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["source_project_id"] == package.source_project_id
        assert manifest["approved_by"] == "artisan-001"
        assert len(manifest["assets"]) == 4
        assert "00:01:00,000" in archive.read("tiktok/subtitles.srt").decode("utf-8")
