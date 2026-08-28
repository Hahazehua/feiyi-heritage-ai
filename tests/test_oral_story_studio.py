from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.oral_story_models import (
    OralClaimCategory,
    OralClaimStatus,
    OralSourceKind,
    OralStoryStatus,
)
from heritagelink.oral_story_service import (
    build_oral_story_context,
    confirm_publishable_oral_claims,
    create_oral_story_session,
    create_project_from_oral_story,
    export_oral_story_session,
    media_sha256,
    review_oral_story_claims,
)
from heritagelink.story_models import NarrativeTemplate, StoryProjectStatus

NOW = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
TRANSCRIPT = """[00:05] 我叫李师傅，在芜湖做铁画。
[00:18] 我从十八岁开始跟着父亲学艺。
[00:42] 最难的是把铁丝焊牢，又不能留下太重的焊点。
[01:10] 我希望年轻人以后还能听见工作台上的敲击声。
[01:35] 有人叫我是国家级大师。
[01:50] 我们保证全球配送。"""


def _fact(field_name: str, value: object, *, verified: bool = True) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=EvidenceStatus.VERIFIED if verified else EvidenceStatus.UNVERIFIED,
        source=FactSource.PUBLIC_SOURCE if verified else FactSource.ARTISAN_PROVIDED,
        verification_status=(
            VerificationStatus.CONFIRMED if verified else VerificationStatus.PENDING_REVIEW
        ),
        source_note="公开资料" if verified else "待核实资料",
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
        ),
        unverified_facts=(
            _fact("artisan_credentials", "国家级大师", verified=False),
            _fact("international_shipping", "保证全球配送", verified=False),
        ),
        unknown_fields=("certification",),
    )


def test_intake_preserves_timestamped_quotes_and_blocks_external_claims(
    context: GrowthProductContext,
) -> None:
    session = create_oral_story_session(
        context,
        TRANSCRIPT,
        source_kind=OralSourceKind.AUDIO,
        source_name="interview.wav",
        media_sha256="a" * 64,
        now=NOW,
    )

    assert session.source_kind is OralSourceKind.AUDIO
    assert session.segments[0].locator == "00:05"
    assert session.claims[0].source_quote == "我叫李师傅，在芜湖做铁画。"
    assert {claim.category for claim in session.claims} >= {
        OralClaimCategory.IDENTITY,
        OralClaimCategory.JOURNEY,
        OralClaimCategory.CHALLENGE,
        OralClaimCategory.ASPIRATION,
        OralClaimCategory.CREDENTIAL,
        OralClaimCategory.COMMERCIAL,
    }
    blocked = [claim for claim in session.claims if claim.requires_external_evidence]
    assert len(blocked) == 2
    assert all(claim.status is OralClaimStatus.NEEDS_EVIDENCE for claim in blocked)


def test_external_claim_cannot_be_confirmed_from_testimony(
    context: GrowthProductContext,
) -> None:
    session = create_oral_story_session(context, TRANSCRIPT, now=NOW)
    credential = next(
        claim for claim in session.claims if claim.category is OralClaimCategory.CREDENTIAL
    )

    with pytest.raises(ValueError, match="require external evidence"):
        review_oral_story_claims(
            session,
            {credential.claim_id: OralClaimStatus.CONFIRMED},
            actor_id=context.artisan_id,
            now=NOW,
        )


def test_explicit_bulk_review_confirms_testimony_and_excludes_risky_claims(
    context: GrowthProductContext,
) -> None:
    session = create_oral_story_session(context, TRANSCRIPT, now=NOW)
    reviewed = confirm_publishable_oral_claims(session, actor_id=context.artisan_id, now=NOW)

    assert reviewed.status is OralStoryStatus.READY_FOR_SCRIPT
    assert reviewed.confirmed_count == 4
    assert reviewed.blocked_count == 0
    assert all(
        claim.status is OralClaimStatus.EXCLUDED
        for claim in reviewed.claims
        if claim.requires_external_evidence
    )
    assert all(
        claim.reviewer_id == context.artisan_id
        for claim in reviewed.claims
        if claim.status in {OralClaimStatus.CONFIRMED, OralClaimStatus.EXCLUDED}
    )


def test_confirmed_testimony_builds_guardian_clean_traceable_story(
    context: GrowthProductContext,
) -> None:
    reviewed = confirm_publishable_oral_claims(
        create_oral_story_session(context, TRANSCRIPT, now=NOW),
        actor_id=context.artisan_id,
        now=NOW,
    )
    oral_context = build_oral_story_context(context, reviewed)
    project = create_project_from_oral_story(context, reviewed, now=NOW)

    assert oral_context.context_label.startswith("oral-story:")
    assert {fact.field_name for fact in oral_context.verified_facts} >= {
        "maker_identity",
        "artisan_journey",
        "craft_challenge",
        "future_wish",
    }
    assert all(
        "手艺人口述并由本人确认" in fact.source_note
        for fact in oral_context.verified_facts
        if fact.field_name.startswith(("maker_", "artisan_", "craft_", "future_"))
        and fact.field_name not in {"craft_name"}
    )
    assert project.script.story_core.template is NarrativeTemplate.ORAL_HISTORY
    assert project.script.total_duration_seconds == 60
    assert len(project.script.scenes) == 6
    assert project.guardian_review.approved is True
    assert project.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    public_text = "\n".join(scene.voiceover for scene in project.script.scenes)
    assert "我叫李师傅" in public_text
    assert "最难的是" in public_text
    assert "国家级大师" not in public_text
    assert "保证全球配送" not in public_text


def test_session_export_contains_transcript_hash_decisions_and_locators(
    context: GrowthProductContext,
) -> None:
    first = create_oral_story_session(context, TRANSCRIPT, now=NOW)
    second = create_oral_story_session(context, TRANSCRIPT, now=NOW)
    reviewed = confirm_publishable_oral_claims(first, actor_id=context.artisan_id, now=NOW)
    exported = json.loads(export_oral_story_session(reviewed))

    assert first == second
    assert exported["transcript_sha256"] == reviewed.transcript_sha256
    assert exported["claims"][0]["source_locator"] == "00:05"
    assert exported["claims"][0]["status"] == "confirmed"
    assert media_sha256(b"audio") == (
        "6ed8919ce20490a5e3ad8630a4fab69475297abd07db73918dd5f36fcfaeb11b"
    )


def test_repeated_story_category_keeps_every_source_passage(
    context: GrowthProductContext,
) -> None:
    transcript = "[00:03] 我小时候看父亲做铁画。\n[00:16] 我十八岁开始正式学艺。"
    session = create_oral_story_session(context, transcript, now=NOW)
    reviewed = confirm_publishable_oral_claims(session, actor_id=context.artisan_id, now=NOW)
    oral_context = build_oral_story_context(context, reviewed)
    journey = oral_context.verified_by_name["artisan_journey"]

    assert len(session.claims) == 2
    assert "小时候" in journey.value
    assert "十八岁" in journey.value
    assert "00:03" in journey.source_note
    assert "00:16" in journey.source_note
