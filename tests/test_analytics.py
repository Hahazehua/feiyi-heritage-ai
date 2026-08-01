from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from heritagelink.analytics import (
    AnalyticsSettings,
    build_recommendation_event,
    build_selection_event,
    create_choice_repository,
    persist_recommendation_choice,
)
from heritagelink.analytics_models import SaveResult
from heritagelink.data_loader import build_products, load_data
from heritagelink.inference_policy import build_recommendation_context
from heritagelink.progressive_recommender import recommend_progressively
from heritagelink.request_parser import demo_parse_request

ROOT = Path(__file__).parents[1]


class RecordingRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sessions: list[object] = []
        self.requirements: list[object] = []
        self.recommendations: list[object] = []
        self.selections: list[object] = []

    def _record(self, target: list[object], value: object) -> None:
        if self.fail:
            raise RuntimeError("database unavailable")
        target.append(value)

    def save_session(self, value: object) -> SaveResult:
        self._record(self.sessions, value)
        return SaveResult(True)

    def save_final_requirement(self, value: object) -> SaveResult:
        self._record(self.requirements, value)
        return SaveResult(True)

    def save_recommendation(self, value: object) -> SaveResult:
        self._record(self.recommendations, value)
        return SaveResult(True)

    def save_selection(self, value: object) -> SaveResult:
        self._record(self.selections, value)
        return SaveResult(True)


def _context_and_result():  # type: ignore[no-untyped-def]
    parsed = demo_parse_request("送给20位合作伙伴的周年礼物，每件预算1000元")
    context = build_recommendation_context(parsed)
    products = build_products(load_data(ROOT / "data" / "demo"))
    return context, recommend_progressively(products, context.effective_request)


def test_recommendation_and_selection_ids_are_stable() -> None:
    context, result = _context_and_result()
    timestamp = datetime(2026, 7, 30, tzinfo=UTC)
    first = build_recommendation_event("anon_test", context, result, timestamp=timestamp)
    second = build_recommendation_event("anon_test", context, result, timestamp=timestamp)
    selection_a = build_selection_event(
        first, first.recommended_product_ids[0], timestamp=timestamp
    )
    selection_b = build_selection_event(
        second, second.recommended_product_ids[0], timestamp=timestamp
    )

    assert first.recommendation_event_id == second.recommendation_event_id
    assert selection_a.selection_event_id == selection_b.selection_event_id


def test_different_products_generate_different_selection_events() -> None:
    context, result = _context_and_result()
    event = build_recommendation_event("anon_test", context, result)

    first = build_selection_event(event, event.recommended_product_ids[0])
    second = build_selection_event(event, event.recommended_product_ids[1])

    assert first.selection_event_id != second.selection_event_id


def test_customization_brief_is_a_distinct_final_action_event() -> None:
    context, result = _context_and_result()
    event = build_recommendation_event("anon_test", context, result)
    product_id = event.recommended_product_ids[0]

    selected = build_selection_event(event, product_id)
    brief = build_selection_event(
        event,
        product_id,
        final_action="customization_brief_generated",
        brief_generated=True,
    )

    assert selected.selection_event_id != brief.selection_event_id


def test_no_consent_writes_nothing() -> None:
    context, result = _context_and_result()
    event = build_recommendation_event("anon_test", context, result)
    repository = RecordingRepository()

    saved = persist_recommendation_choice(
        repository,  # type: ignore[arg-type]
        consent=False,
        session_id="anon_test",
        session_started_at=datetime.now(UTC),
        conversation_turn_count=2,
        entry_source="chat",
        app_version="test",
        context=context,
        recommendation_event=event,
    )

    assert saved is False
    assert not repository.sessions
    assert not repository.requirements
    assert not repository.recommendations


def test_consent_saves_anonymous_structured_choice_without_raw_chat() -> None:
    context, result = _context_and_result()
    event = build_recommendation_event("anon_test", context, result)
    selection = build_selection_event(event, event.recommended_product_ids[0])
    repository = RecordingRepository()

    saved = persist_recommendation_choice(
        repository,  # type: ignore[arg-type]
        consent=True,
        session_id="anon_test",
        session_started_at=datetime.now(UTC),
        conversation_turn_count=2,
        entry_source="chat",
        app_version="test",
        context=context,
        recommendation_event=event,
        selection_event=selection,
    )

    assert saved is True
    assert len(repository.selections) == 1
    requirement = repository.requirements[0]
    assert not hasattr(requirement, "raw_chat")
    assert not hasattr(requirement, "raw_user_texts")


def test_database_failure_never_breaks_recommendation_flow() -> None:
    context, result = _context_and_result()
    event = build_recommendation_event("anon_test", context, result)

    assert (
        persist_recommendation_choice(
            RecordingRepository(fail=True),  # type: ignore[arg-type]
            consent=True,
            session_id="anon_test",
            session_started_at=datetime.now(UTC),
            conversation_turn_count=1,
            entry_source="chat",
            app_version="test",
            context=context,
            recommendation_event=event,
        )
        is False
    )
    assert result.response.recommendations


def test_analytics_defaults_are_private_and_disabled(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    for name in (
        "ANALYTICS_ENABLED",
        "ANALYTICS_DATABASE_URL",
        "ANALYTICS_STORE_RAW_CHAT",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = AnalyticsSettings.from_env()

    assert settings.enabled is False
    assert settings.store_raw_chat is False
    assert create_choice_repository(settings) is None


def test_raw_chat_flag_cannot_enable_unimplemented_storage(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ANALYTICS_STORE_RAW_CHAT", "true")

    assert AnalyticsSettings.from_env().store_raw_chat is False
