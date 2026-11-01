from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.story_models import (
    NarrativeTemplate,
    StoryDecision,
    StoryFactReference,
    StoryProjectStatus,
)
from heritagelink.story_service import (
    build_xiaohongshu_story,
    create_story_project,
    decide_story_project,
    replace_story_script,
    review_story_script,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _fact(
    field_name: str,
    value: object,
    *,
    verified: bool = True,
    source_url: str | None = None,
) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=(EvidenceStatus.VERIFIED if verified else EvidenceStatus.UNVERIFIED),
        source=FactSource.PUBLIC_SOURCE if verified else FactSource.ARTISAN_PROVIDED,
        verification_status=(
            VerificationStatus.CONFIRMED if verified else VerificationStatus.PENDING_REVIEW
        ),
        source_note="公开馆藏记录" if verified else "手艺人口述，待确认",
        source_url=source_url,
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
            _fact("craft_name", "芜湖铁画", source_url="https://example.org/craft"),
            _fact("region", "安徽芜湖"),
            _fact("materials", ("低碳钢", "木框")),
            _fact("craft_process", "锻打、焊接与整形"),
            _fact("occasion_tags", ("企业礼赠", "文化交流")),
        ),
        unverified_facts=(
            _fact("artisan_credentials", "国家级大师", verified=False),
            _fact("international_shipping", "保证全球配送", verified=False),
        ),
        unknown_fields=("certification",),
        cultural_source_urls=("https://example.org/craft",),
    )


def test_builds_a_sixty_second_xiaohongshu_story_from_verified_facts_only(
    context: GrowthProductContext,
) -> None:
    script = build_xiaohongshu_story(context, now=NOW)

    assert script.platform.value == "xiaohongshu"
    assert script.aspect_ratio == "9:16"
    assert script.total_duration_seconds == 60
    assert [scene.duration_seconds for scene in script.scenes] == [5, 12, 12, 12, 12, 7]
    assert len(script.scenes) == 6
    assert script.created_at == NOW
    assert script.story_core.grounded_field_names <= set(context.verified_by_name)
    assert {reference.field_name for reference in script.fact_references} <= set(
        context.verified_by_name
    )

    public_output = "\n".join(
        text
        for scene in script.scenes
        for text in (scene.voiceover, scene.visual_description, scene.image_prompt)
    )
    assert "国家级大师" not in public_output
    assert "保证全球配送" not in public_output


def test_story_generation_is_deterministic_except_for_supplied_time(
    context: GrowthProductContext,
) -> None:
    first = build_xiaohongshu_story(context, NarrativeTemplate.ARTISAN_LIFE, now=NOW)
    second = build_xiaohongshu_story(context, NarrativeTemplate.ARTISAN_LIFE, now=NOW)

    assert first == second
    assert first.script_id == "script-iron-picture-001-artisan_life-xhs"
    assert first.scenes[0].fact_reference_ids == ("fact-iron-picture-001-craft_name",)


def test_generated_story_passes_guardian_and_waits_for_human(
    context: GrowthProductContext,
) -> None:
    project = create_story_project(context, now=NOW)

    assert project.guardian_review.approved is True
    assert project.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    assert project.human_decision is None


def test_human_can_approve_only_after_clean_guardian_review(
    context: GrowthProductContext,
) -> None:
    project = create_story_project(context, now=NOW)
    approved = decide_story_project(
        project,
        StoryDecision.APPROVE,
        actor_id="artisan-001",
        note="事实与表达均已确认",
        now=NOW,
    )

    assert approved.status is StoryProjectStatus.APPROVED
    assert approved.human_decision is not None
    assert approved.human_decision.decision is StoryDecision.APPROVE
    with pytest.raises(ValueError, match="cannot be overwritten"):
        decide_story_project(approved, StoryDecision.REJECT, "artisan-001", now=NOW)


def test_revision_request_is_recorded_and_cleared_after_re_review(
    context: GrowthProductContext,
) -> None:
    project = create_story_project(context, now=NOW)
    revision = decide_story_project(
        project,
        StoryDecision.REQUEST_REVISION,
        actor_id="artisan-001",
        note="请将结尾改得更克制",
        now=NOW,
    )
    refreshed = replace_story_script(revision, revision.script, context, now=NOW)

    assert revision.status is StoryProjectStatus.NEEDS_REVISION
    assert revision.revision_count == 1
    assert refreshed.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    assert refreshed.human_decision is None


def test_guardian_rejects_an_unverified_reference(
    context: GrowthProductContext,
) -> None:
    project = create_story_project(context, now=NOW)
    fake = StoryFactReference(
        reference_id="fact-iron-picture-001-artisan_credentials",
        field_name="artisan_credentials",
        display_value="国家级大师",
        source_note="手艺人口述",
    )
    tampered_scene = replace(
        project.script.scenes[1],
        voiceover="这位国家级大师完成了作品。",
        fact_reference_ids=(fake.reference_id,),
    )
    tampered_script = replace(
        project.script,
        scenes=(project.script.scenes[0], tampered_scene, *project.script.scenes[2:]),
        fact_references=(*project.script.fact_references, fake),
    )

    review = review_story_script(tampered_script, context, now=NOW)
    failed = replace_story_script(project, tampered_script, context, now=NOW)

    assert review.approved is False
    assert {issue.issue_type for issue in review.issues} >= {
        "unverified_reference",
        "pending_fact_used",
        "unsupported_claim",
    }
    assert failed.status is StoryProjectStatus.NEEDS_REVISION
    with pytest.raises(ValueError, match="clean Guardian review"):
        decide_story_project(failed, StoryDecision.APPROVE, "artisan-001", now=NOW)


def test_english_story_keeps_the_same_export_contract(context: GrowthProductContext) -> None:
    script = build_xiaohongshu_story(context, language="English", now=NOW)

    assert script.total_duration_seconds == 60
    assert script.title.startswith("The hand skill")
    assert script.scenes[0].title == "Hook"


def test_story_requires_at_least_one_verified_anchor_fact() -> None:
    empty = GrowthProductContext(
        artisan_id="artisan-001",
        product_id="draft-001",
        product_name="待确认作品",
        product_name_en=None,
        craft_name="待确认工艺",
        publication_status=PublicationStatus.DRAFT,
        verified_facts=(),
        unverified_facts=(_fact("craft_name", "待确认工艺", verified=False),),
        unknown_fields=("region",),
    )

    with pytest.raises(ValueError, match="at least one verified"):
        build_xiaohongshu_story(empty, now=NOW)
