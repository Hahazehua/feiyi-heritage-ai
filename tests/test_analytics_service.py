from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from heritagelink.analytics import build_recommendation_event, build_selection_event
from heritagelink.analytics_service import capture_consented_choice
from heritagelink.data_loader import build_products, load_data
from heritagelink.inference_policy import build_recommendation_context
from heritagelink.progressive_recommender import recommend_progressively
from heritagelink.repositories.memory_choice_repository import MemoryChoiceRepository
from heritagelink.request_parser import demo_parse_request

ROOT = Path(__file__).parents[1]


def _inputs():  # type: ignore[no-untyped-def]
    timestamp = datetime(2026, 7, 30, tzinfo=UTC)
    context = build_recommendation_context(
        demo_parse_request("送给20位合作伙伴的周年礼物，每件预算1000元")
    )
    products = build_products(load_data(ROOT / "data" / "demo"))
    result = recommend_progressively(products, context.effective_request)
    recommendation = build_recommendation_event(
        "anon_service", context, result, timestamp=timestamp
    )
    selection = build_selection_event(
        recommendation, recommendation.recommended_product_ids[0], timestamp=timestamp
    )
    return context, recommendation, selection


def _capture(repository, *, consent=True, selection=True):  # type: ignore[no-untyped-def]
    context, recommendation, event = _inputs()
    return capture_consented_choice(
        repository,
        consent_granted=consent,
        consent_version="analytics-consent-v1",
        consented_at=datetime(2026, 7, 30, tzinfo=UTC),
        session_id="anon_service",
        session_started_at=datetime(2026, 7, 30, tzinfo=UTC),
        conversation_turn_count=2,
        entry_source="chat",
        app_version="test",
        context=context,
        recommendation_event=recommendation,
        selection_event=event if selection else None,
    )


def test_no_consent_and_no_selection_are_safe_zero_writes() -> None:
    repository = MemoryChoiceRepository()
    no_consent = _capture(repository, consent=False)
    no_selection = _capture(repository, selection=False)

    assert no_consent.status == "skipped_no_consent"
    assert no_selection.status == "skipped_no_selection"
    assert not repository.sessions
    assert not repository.recommendations
    assert not repository.selections


def test_consent_saves_anonymous_chain_without_raw_chat_or_pii() -> None:
    repository = MemoryChoiceRepository()
    result = _capture(repository)

    assert result.status == "saved"
    assert len(repository.sessions) == len(repository.requirements) == 1
    assert len(repository.recommendations) == len(repository.selections) == 1
    serialized_names = {
        field
        for record in (*repository.sessions.values(), *repository.requirements.values())
        for field in record.__dataclass_fields__
    }
    assert not serialized_names & {"raw_chat", "name", "email", "phone", "ip_address"}


def test_identical_rerun_is_duplicate_and_product_change_is_new() -> None:
    repository = MemoryChoiceRepository()
    first = _capture(repository)
    second = _capture(repository)
    context, recommendation, _ = _inputs()
    changed = build_selection_event(recommendation, recommendation.recommended_product_ids[1])
    third = capture_consented_choice(
        repository,
        consent_granted=True,
        consent_version="analytics-consent-v1",
        consented_at=changed.selected_at,
        session_id="anon_service",
        session_started_at=datetime(2026, 7, 30, tzinfo=UTC),
        conversation_turn_count=2,
        entry_source="chat",
        app_version="test",
        context=context,
        recommendation_event=recommendation,
        selection_event=changed,
    )

    assert first.status == "saved"
    assert second.status == "duplicate_ignored"
    assert third.status == "saved"
    assert len(repository.selections) == 2


def test_unavailable_repository_and_invalid_chain_return_safe_status() -> None:
    assert _capture(None).status == "storage_unavailable"
    assert _capture(MemoryChoiceRepository(fail=True)).status == "storage_unavailable"

    context, recommendation, selection = _inputs()
    invalid = capture_consented_choice(
        MemoryChoiceRepository(),
        consent_granted=True,
        consent_version="analytics-consent-v1",
        consented_at=selection.selected_at,
        session_id="not-anonymous",
        session_started_at=selection.selected_at,
        conversation_turn_count=1,
        entry_source="chat",
        app_version="test",
        context=context,
        recommendation_event=recommendation,
        selection_event=selection,
    )
    assert invalid.status == "validation_failed"
