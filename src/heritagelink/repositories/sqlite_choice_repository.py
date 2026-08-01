"""SQLite repository for local development and automated tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SaveResult,
    SelectionEvent,
    SessionRecord,
)


class SQLiteChoiceRepository:
    """Idempotent local repository; never stores raw conversation text."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    anonymous_session_id TEXT PRIMARY KEY,
                    session_started_at TEXT NOT NULL,
                    session_completed_at TEXT,
                    conversation_turn_count INTEGER NOT NULL,
                    entry_source TEXT NOT NULL,
                    app_version TEXT NOT NULL,
                    consent_version TEXT NOT NULL DEFAULT 'analytics-consent-v1',
                    consented_at TEXT,
                    data_source TEXT NOT NULL DEFAULT 'consented_user'
                );
                CREATE TABLE IF NOT EXISTS final_requirements (
                    anonymous_session_id TEXT PRIMARY KEY,
                    recipient TEXT, scene TEXT, budget_type TEXT,
                    budget_per_item REAL, total_budget REAL, quantity INTEGER,
                    style_preferences TEXT NOT NULL,
                    symbolism_preferences TEXT NOT NULL,
                    customization_types TEXT NOT NULL,
                    logo_required INTEGER, destination TEXT,
                    required_delivery_days INTEGER, output_language TEXT,
                    user_provided_fields TEXT NOT NULL,
                    inferred_fields TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recommendation_events (
                    recommendation_event_id TEXT PRIMARY KEY,
                    anonymous_session_id TEXT NOT NULL,
                    recommendation_signature TEXT NOT NULL,
                    recommended_product_ids TEXT NOT NULL,
                    ranking_positions TEXT NOT NULL,
                    match_scores TEXT NOT NULL,
                    recommendation_timestamp TEXT NOT NULL,
                    UNIQUE(anonymous_session_id, recommendation_signature)
                );
                CREATE TABLE IF NOT EXISTS selection_events (
                    selection_event_id TEXT PRIMARY KEY,
                    recommendation_event_id TEXT NOT NULL,
                    anonymous_session_id TEXT NOT NULL,
                    selected_product_id TEXT NOT NULL,
                    selected_rank_position INTEGER NOT NULL,
                    selected_at TEXT NOT NULL,
                    final_action TEXT NOT NULL,
                    whether_customization_brief_generated INTEGER NOT NULL,
                    selection_reason TEXT, rejection_reason TEXT,
                    satisfaction_rating INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_recommendation_session
                    ON recommendation_events(anonymous_session_id);
                CREATE INDEX IF NOT EXISTS idx_selection_session
                    ON selection_events(anonymous_session_id);
                """
            )
            session_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            migrations = {
                "consent_version": (
                    "ALTER TABLE sessions ADD COLUMN consent_version TEXT NOT NULL "
                    "DEFAULT 'analytics-consent-v1'"
                ),
                "consented_at": "ALTER TABLE sessions ADD COLUMN consented_at TEXT",
                "data_source": (
                    "ALTER TABLE sessions ADD COLUMN data_source TEXT NOT NULL "
                    "DEFAULT 'consented_user'"
                ),
            }
            for column, sql in migrations.items():
                if column not in session_columns:
                    connection.execute(sql)

    def save_session(self, session: SessionRecord) -> SaveResult:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT session_completed_at, conversation_turn_count, entry_source, app_version, "
                "consent_version, consented_at, data_source FROM sessions "
                "WHERE anonymous_session_id = ?",
                (session.anonymous_session_id,),
            ).fetchone()
            values = (
                session.session_completed_at.isoformat() if session.session_completed_at else None,
                session.conversation_turn_count,
                session.entry_source,
                session.app_version,
                session.consent_version,
                session.consented_at.isoformat() if session.consented_at else None,
                session.data_source,
            )
            connection.execute(
                """
                INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anonymous_session_id) DO UPDATE SET
                  session_completed_at=excluded.session_completed_at,
                  conversation_turn_count=excluded.conversation_turn_count,
                  entry_source=excluded.entry_source,
                  app_version=excluded.app_version,
                  consent_version=excluded.consent_version,
                  consented_at=excluded.consented_at,
                  data_source=excluded.data_source
                """,
                (
                    session.anonymous_session_id,
                    session.session_started_at.isoformat(),
                    *values,
                ),
            )
        duplicate = existing == values
        return SaveResult(saved=not duplicate, duplicate=duplicate)

    def save_final_requirement(self, requirement: FinalRequirementRecord) -> SaveResult:
        values = (
            requirement.anonymous_session_id,
            requirement.recipient,
            requirement.scene,
            requirement.budget_type,
            requirement.budget_per_item,
            requirement.total_budget,
            requirement.quantity,
            _json(requirement.style_preferences),
            _json(requirement.symbolism_preferences),
            _json(requirement.customization_types),
            _optional_bool(requirement.logo_required),
            requirement.destination,
            requirement.required_delivery_days,
            requirement.output_language,
            _json(requirement.user_provided_fields),
            _json(requirement.inferred_fields),
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM final_requirements WHERE anonymous_session_id = ?",
                (requirement.anonymous_session_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT OR REPLACE INTO final_requirements VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        return SaveResult(saved=True, duplicate=existing is not None)

    def save_recommendation(self, event: RecommendationEvent) -> SaveResult:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO recommendation_events VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.recommendation_event_id,
                    event.anonymous_session_id,
                    event.recommendation_signature,
                    _json(event.recommended_product_ids),
                    _json(event.ranking_positions),
                    _json(event.match_scores),
                    event.recommendation_timestamp.isoformat(),
                ),
            )
        return SaveResult(saved=cursor.rowcount == 1, duplicate=cursor.rowcount == 0)

    def save_selection(self, event: SelectionEvent) -> SaveResult:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT final_action, whether_customization_brief_generated, selection_reason, "
                "rejection_reason, satisfaction_rating FROM selection_events "
                "WHERE selection_event_id = ?",
                (event.selection_event_id,),
            ).fetchone()
            values = (
                event.final_action,
                int(event.whether_customization_brief_generated),
                event.selection_reason,
                event.rejection_reason,
                event.satisfaction_rating,
            )
            connection.execute(
                """
                INSERT INTO selection_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(selection_event_id) DO UPDATE SET
                  final_action=excluded.final_action,
                  whether_customization_brief_generated=excluded.whether_customization_brief_generated,
                  selection_reason=excluded.selection_reason,
                  rejection_reason=excluded.rejection_reason,
                  satisfaction_rating=excluded.satisfaction_rating
                """,
                (
                    event.selection_event_id,
                    event.recommendation_event_id,
                    event.anonymous_session_id,
                    event.selected_product_id,
                    event.selected_rank_position,
                    event.selected_at.isoformat(),
                    event.final_action,
                    int(event.whether_customization_brief_generated),
                    event.selection_reason,
                    event.rejection_reason,
                    event.satisfaction_rating,
                ),
            )
        duplicate = existing == values
        return SaveResult(saved=not duplicate, duplicate=duplicate)


def _json(value: tuple[object, ...]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _optional_bool(value: bool | None) -> int | None:
    return None if value is None else int(value)
