from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SelectionEvent,
    SessionRecord,
)
from heritagelink.repositories.postgres_choice_repository import PostgresChoiceRepository
from heritagelink.repositories.sqlite_choice_repository import SQLiteChoiceRepository


def _records():  # type: ignore[no-untyped-def]
    now = datetime(2026, 7, 30, tzinfo=UTC)
    session = SessionRecord("anon_test", now, None, 2, "chat", "test")
    requirement = FinalRequirementRecord(
        "anon_test",
        "business_partner",
        "anniversary",
        "per_item",
        1000,
        None,
        20,
        ("elegant",),
        ("heritage",),
        ("logo",),
        True,
        None,
        None,
        "bilingual",
        ("recipient", "scene"),
        ("style_preferences",),
    )
    recommendation = RecommendationEvent(
        "rec_test", "anon_test", "signature", ("prod_1", "prod_2"), (1, 2), (90.0, 80.0), now
    )
    selection = SelectionEvent(
        "sel_test", "rec_test", "anon_test", "prod_1", 1, now, "selected", False
    )
    return session, requirement, recommendation, selection


def test_sqlite_repository_is_idempotent_and_updates_brief_status(tmp_path: Path) -> None:
    path = tmp_path / "choices.sqlite3"
    repository = SQLiteChoiceRepository(path)
    session, requirement, recommendation, selection = _records()

    for _ in range(2):
        repository.save_session(session)
        repository.save_final_requirement(requirement)
        repository.save_recommendation(recommendation)
        repository.save_selection(selection)
    repository.save_selection(
        replace(
            selection,
            final_action="customization_brief_generated",
            whether_customization_brief_generated=True,
        )
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recommendation_events").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM selection_events").fetchone()[0] == 1
        row = connection.execute(
            "SELECT final_action, whether_customization_brief_generated FROM selection_events"
        ).fetchone()
    assert row == ("customization_brief_generated", 1)


class FakeCursor:
    def __init__(self, calls: list[tuple[str, tuple[object, ...]]]) -> None:
        self.calls = calls

    def execute(self, sql: str, values: tuple[object, ...] = ()) -> None:
        self.calls.append((sql, values))

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self, calls: list[tuple[str, tuple[object, ...]]]) -> None:
        self.calls = calls
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.calls)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        pass


def test_postgres_repository_uses_parameterized_idempotent_statements() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    repository = PostgresChoiceRepository(
        "postgresql://example.invalid/test",
        connect=lambda _: FakeConnection(calls),
        initialize=False,
    )
    session, requirement, recommendation, selection = _records()

    repository.save_session(session)
    repository.save_final_requirement(requirement)
    repository.save_recommendation(recommendation)
    repository.save_selection(selection)

    assert len(calls) == 4
    assert all("%s" in sql for sql, _ in calls)
    assert all("ON CONFLICT" in sql for sql, _ in calls)
    assert not any("postgresql://" in sql for sql, _ in calls)
