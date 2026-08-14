from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from heritagelink.artisan_studio import (
    RECOMMENDABLE_REQUIRED_FIELDS,
    build_passport,
    confirm_facts,
    create_draft,
    enrich_draft,
    merge_artisan_values,
    simulate_review_approval,
    submit_for_review,
    update_bilingual_draft,
)
from heritagelink.comparison_models import ApplicationTraceStatus, ExplanationSource
from heritagelink.heritage_passport_models import (
    FactGroup,
    FactSource,
    ProvenancedFact,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.repositories.memory_artisan_draft_repository import (
    MemoryArtisanDraftRepository,
)

NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


class SuccessfulArtisanClient:
    def extract_artisan_draft(self, payload: dict[str, object]) -> dict[str, object]:
        assert "facts" in payload
        return {
            "price_min_fen": 80_000,
            "price_max_fen": 150_000,
            "currency": "CNY",
            "customization": ("题字",),
            "logo_supported": True,
        }

    def write_artisan_bilingual(self, payload: dict[str, object]) -> dict[str, object]:
        assert payload
        return {
            "overview_zh": "芜湖铁画迎客松作品介绍草稿。",
            "overview_en": "A draft introduction to the Wuhu iron painting.",
            "craft_background_zh": "铁画工艺背景草稿。",
            "craft_background_en": "A draft account of the iron-painting craft.",
            "cultural_meaning_zh": "迎客主题寓意草稿。",
            "cultural_meaning_en": "A draft account of the welcoming-pine motif.",
            "gifting_contexts_zh": "企业礼赠场景草稿。",
            "gifting_contexts_en": "A draft for corporate gifting contexts.",
            "customization_zh": "定制信息仍待手艺人确认。",
            "customization_en": "Customization remains subject to artisan confirmation.",
        }


class FailingArtisanClient:
    def extract_artisan_draft(self, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("provider unavailable")

    def write_artisan_bilingual(self, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("provider unavailable")


@pytest.mark.parametrize(
    "unknown_value",
    (None, "", "unknown", "暂不确定", "待确认", "不清楚", "待补充"),
)
def test_unknown_commercial_values_are_first_class_facts(unknown_value: object) -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "international_shipping": unknown_value,
        },
        now=NOW,
    )

    fact = draft.facts_by_name["international_shipping"]
    assert fact.value is None
    assert fact.group is FactGroup.COMMERCIAL
    assert fact.source is FactSource.UNKNOWN
    assert fact.verification_status is VerificationStatus.UNKNOWN
    assert draft.publication_status is PublicationStatus.DRAFT


def test_artisan_provided_fields_are_pending_then_only_selected_fields_confirm() -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            "price_min_fen": 80_000,
        },
        now=NOW,
    )

    assert all(fact.source is FactSource.ARTISAN_PROVIDED for fact in draft.facts)
    assert all(
        fact.verification_status is VerificationStatus.PENDING_REVIEW for fact in draft.facts
    )

    confirmed = confirm_facts(draft, ("product_name_zh",), now=LATER)

    name = confirmed.facts_by_name["product_name_zh"]
    assert name.source is FactSource.ARTISAN_CONFIRMED
    assert name.verification_status is VerificationStatus.CONFIRMED
    assert name.confirmed_at == LATER
    for field_name in ("craft_name", "price_min_fen"):
        fact = confirmed.facts_by_name[field_name]
        assert fact.source is FactSource.ARTISAN_PROVIDED
        assert fact.verification_status is VerificationStatus.PENDING_REVIEW
        assert fact.confirmed_at is None


def test_bulk_confirmation_does_not_promote_an_unknown_value() -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "international_shipping": "暂不确定",
        },
        now=NOW,
    )

    confirmed = confirm_facts(draft, ("product_name_zh", "international_shipping"), now=LATER)

    shipping = confirmed.facts_by_name["international_shipping"]
    assert shipping.value is None
    assert shipping.source is FactSource.UNKNOWN
    assert shipping.verification_status is VerificationStatus.UNKNOWN
    assert shipping.confirmed_at is None


def test_ai_commercial_candidates_remain_inferred_and_pending() -> None:
    draft = create_draft(
        "artisan-session",
        {"product_name_zh": "芜湖铁画迎客松"},
        description="支持企业 Logo 和题字，价格约为 800–1500 元。",
        now=NOW,
    )

    enriched, trace = enrich_draft(draft, client=SuccessfulArtisanClient(), now=LATER)

    for field_name in (
        "price_min_fen",
        "price_max_fen",
        "currency",
        "customization",
        "logo_supported",
    ):
        fact = enriched.facts_by_name[field_name]
        assert fact.group is FactGroup.COMMERCIAL
        assert fact.source is FactSource.AI_INFERRED
        assert fact.verification_status is VerificationStatus.PENDING_REVIEW
        assert fact.confirmed_at is None
    assert trace.status is ApplicationTraceStatus.SUCCESS
    assert trace.narrative_source is ExplanationSource.LLM
    assert trace.output_summary["recommendation_eligibility"] is False


def test_ai_inferred_fact_model_rejects_automatic_confirmation() -> None:
    with pytest.raises(ValueError, match="AI inferred"):
        ProvenancedFact(
            field_name="price_min_fen",
            value=80_000,
            group=FactGroup.COMMERCIAL,
            source=FactSource.AI_INFERRED,
            verification_status=VerificationStatus.CONFIRMED,
        )


def test_llm_failure_keeps_manual_review_passport_and_submission_available() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = create_draft(
        "artisan-session",
        {"product_name_zh": "芜湖铁画迎客松"},
        description=(
            "这是一件芜湖铁画作品，以迎客松为主题，适合作为企业礼赠。"
            "支持企业 Logo 和题字，价格约为 800–1500 元。"
        ),
        now=NOW,
    )

    enriched, trace = enrich_draft(draft, client=FailingArtisanClient(), now=LATER)
    reviewed = confirm_facts(enriched, ("product_name_zh", "craft_name"), now=LATER)
    passport = build_passport(reviewed)
    submitted = submit_for_review(reviewed, repository, now=LATER)

    assert trace.status is ApplicationTraceStatus.FALLBACK
    assert trace.narrative_source is ExplanationSource.DETERMINISTIC_FALLBACK
    assert enriched.bilingual_draft is not None
    assert passport.product_name_zh == "芜湖铁画迎客松"
    assert passport.craft_name == "铁画"
    assert submitted.publication_status is PublicationStatus.PENDING_REVIEW
    assert submitted.submitted_at == LATER
    assert repository.get(submitted.draft_id) == submitted


def test_explicitly_confirmed_bilingual_edit_is_preserved_in_passport() -> None:
    draft = create_draft(
        "artisan-session",
        {"product_name_zh": "芜湖铁画迎客松", "craft_name": "芜湖铁画"},
        description="这件作品适合文化礼赠。",
        now=NOW,
    )
    enriched, _ = enrich_draft(draft, now=LATER)
    assert enriched.bilingual_draft is not None
    edited_text = "这是手艺人检查并修改后的中文作品简介。"
    edited = update_bilingual_draft(
        enriched,
        {"overview_zh": edited_text},
        now=LATER,
    )

    confirmed = confirm_facts(edited, (), bilingual_confirmed=True, now=LATER)
    passport = build_passport(confirmed)

    assert confirmed.bilingual_draft is not None
    assert confirmed.bilingual_draft.source is FactSource.ARTISAN_CONFIRMED
    assert confirmed.bilingual_draft.verification_status is VerificationStatus.CONFIRMED
    assert passport.bilingual_content is not None
    assert passport.bilingual_content.overview_zh == edited_text


@pytest.mark.parametrize(
    ("field_name", "current_value", "incoming_value"),
    (
        ("price_min_fen", 120_000, 80_000),
        ("customization", ("题字",), ("企业 Logo",)),
        ("domestic_shipping", True, False),
        ("international_shipping", False, True),
    ),
)
def test_protected_conflicts_are_reported_without_silent_overwrite(
    field_name: str,
    current_value: object,
    incoming_value: object,
) -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            field_name: current_value,
        },
        now=NOW,
    )

    merged = merge_artisan_values(draft, {field_name: incoming_value}, now=LATER)

    assert merged.facts_by_name[field_name].value == current_value
    assert len(merged.conflicts) == 1
    conflict = merged.conflicts[0]
    assert conflict.field_name == field_name
    assert conflict.current_value == current_value
    assert conflict.incoming_value == incoming_value
    assert not conflict.is_resolved


@pytest.mark.parametrize(
    ("field_name", "current_value", "incoming_value", "invalid_resolution"),
    (
        ("price_min_fen", 120_000, 80_000, 100_000),
        ("customization", ("题字",), ("企业 Logo",), ("包装",)),
        ("international_shipping", False, True, "待确认"),
    ),
)
def test_conflict_resolution_rejects_an_unrelated_third_value(
    field_name: str,
    current_value: object,
    incoming_value: object,
    invalid_resolution: object,
) -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            field_name: current_value,
        },
        now=NOW,
    )

    with pytest.raises(ValueError, match="只能保留当前记录或采用本次输入"):
        merge_artisan_values(
            draft,
            {field_name: incoming_value},
            resolutions={field_name: invalid_resolution},
            now=LATER,
        )


def test_unresolved_conflict_blocks_submission() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            "price_min_fen": 120_000,
        },
        now=NOW,
    )
    conflicted = merge_artisan_values(draft, {"price_min_fen": 80_000}, now=LATER)

    with pytest.raises(ValueError, match="仍有资料冲突"):
        submit_for_review(conflicted, repository, now=LATER)
    assert repository.get(draft.draft_id) is None


def test_submit_for_review_persists_pending_without_publishing() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            "international_shipping": "暂不确定",
        },
        now=NOW,
    )

    submitted = submit_for_review(draft, repository, now=LATER)

    assert submitted.publication_status is PublicationStatus.PENDING_REVIEW
    assert submitted.submitted_at == LATER
    assert submitted.reviewed_at is None
    assert repository.get(submitted.draft_id) == submitted


def test_simulated_review_requires_explicit_authorization() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = create_draft(
        "artisan-session",
        {"product_name_zh": "芜湖铁画迎客松", "craft_name": "芜湖铁画"},
        now=NOW,
    )
    submitted = submit_for_review(draft, repository, now=LATER)

    with pytest.raises(PermissionError, match="双门"):
        simulate_review_approval(submitted, now=LATER)
    assert submitted.publication_status is PublicationStatus.PENDING_REVIEW
    assert submitted.reviewed_at is None


def test_authorized_review_is_reference_only_when_qualification_is_incomplete() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = create_draft(
        "artisan-session",
        {"product_name_zh": "芜湖铁画迎客松", "craft_name": "芜湖铁画"},
        now=NOW,
    )
    submitted = submit_for_review(draft, repository, now=LATER)

    reviewed = simulate_review_approval(submitted, review_authorized=True, now=LATER)

    assert reviewed.publication_status is PublicationStatus.REFERENCE_ONLY
    assert reviewed.reviewed_at == LATER


def test_authorized_review_requires_all_qualification_facts_source_and_image() -> None:
    values: dict[str, object] = {
        "product_name_zh": "芜湖铁画迎客松",
        "craft_name": "芜湖铁画",
        "region": "安徽 · 芜湖",
        "cultural_background": "由手艺人提供并确认的工艺背景。",
        "price_min_fen": 80_000,
        "price_max_fen": 150_000,
        "currency": "CNY",
        "moq": 1,
        "lead_time_days": 30,
        "materials": "待审查样品所示材料",
        "customization": ("题字",),
        "logo_supported": True,
        "domestic_shipping": True,
        "international_shipping": False,
        "quantity_capacity": 20,
        "cultural_source_url": "https://example.org/cultural-source",
    }
    assert RECOMMENDABLE_REQUIRED_FIELDS.issubset(values)
    draft = create_draft(
        "artisan-session",
        values,
        image_name="iron-painting.jpg",
        image_bytes=b"test-image-bytes",
        now=NOW,
    )
    confirmed = confirm_facts(draft, tuple(values), now=LATER)
    submitted = submit_for_review(confirmed, MemoryArtisanDraftRepository(), now=LATER)

    reviewed = simulate_review_approval(submitted, review_authorized=True, now=LATER)

    assert reviewed.publication_status is PublicationStatus.RECOMMENDABLE
    assert reviewed.reviewed_at == LATER
