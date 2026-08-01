"""PostgreSQL adapter with lazy driver loading and idempotent writes."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import closing
from typing import Any, Protocol

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SaveResult,
    SelectionEvent,
    SessionRecord,
)


class ConnectionLike(Protocol):
    def cursor(self) -> Any: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


class PostgresChoiceRepository:
    """Production adapter; credentials are accepted only through a database URL."""

    def __init__(
        self,
        database_url: str,
        *,
        connect: Callable[[str], ConnectionLike] | None = None,
        initialize: bool = True,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL URL 格式不受支持")
        self.database_url = database_url
        self._connect_fn = connect or _load_psycopg_connect()
        if initialize:
            self._initialize()

    def _connection(self) -> ConnectionLike:
        return self._connect_fn(self.database_url)

    def _execute(self, sql: str, values: tuple[object, ...] = ()) -> None:
        with closing(self._connection()) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(sql, values)
            connection.commit()

    def _initialize(self) -> None:
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              anonymous_session_id TEXT PRIMARY KEY, session_started_at TIMESTAMPTZ NOT NULL,
              session_completed_at TIMESTAMPTZ, conversation_turn_count INTEGER NOT NULL,
              entry_source TEXT NOT NULL, app_version TEXT NOT NULL,
              consent_version TEXT NOT NULL, consented_at TIMESTAMPTZ,
              data_source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS final_requirements (
              anonymous_session_id TEXT PRIMARY KEY, recipient TEXT, scene TEXT, budget_type TEXT,
              budget_per_item DOUBLE PRECISION, total_budget DOUBLE PRECISION, quantity INTEGER,
              style_preferences JSONB NOT NULL, symbolism_preferences JSONB NOT NULL,
              customization_types JSONB NOT NULL, logo_required BOOLEAN, destination TEXT,
              required_delivery_days INTEGER, output_language TEXT,
              user_provided_fields JSONB NOT NULL, inferred_fields JSONB NOT NULL);
            CREATE TABLE IF NOT EXISTS recommendation_events (
              recommendation_event_id TEXT PRIMARY KEY, anonymous_session_id TEXT NOT NULL,
              recommendation_signature TEXT NOT NULL, recommended_product_ids JSONB NOT NULL,
              ranking_positions JSONB NOT NULL, match_scores JSONB NOT NULL,
              recommendation_timestamp TIMESTAMPTZ NOT NULL,
              UNIQUE(anonymous_session_id, recommendation_signature));
            CREATE TABLE IF NOT EXISTS selection_events (
              selection_event_id TEXT PRIMARY KEY, recommendation_event_id TEXT NOT NULL,
              anonymous_session_id TEXT NOT NULL, selected_product_id TEXT NOT NULL,
              selected_rank_position INTEGER NOT NULL, selected_at TIMESTAMPTZ NOT NULL,
              final_action TEXT NOT NULL, whether_customization_brief_generated BOOLEAN NOT NULL,
              selection_reason TEXT, rejection_reason TEXT, satisfaction_rating INTEGER);
            ALTER TABLE sessions ADD COLUMN IF NOT EXISTS
              consent_version TEXT NOT NULL DEFAULT 'analytics-consent-v1';
            ALTER TABLE sessions ADD COLUMN IF NOT EXISTS consented_at TIMESTAMPTZ;
            ALTER TABLE sessions ADD COLUMN IF NOT EXISTS
              data_source TEXT NOT NULL DEFAULT 'consented_user';
            """
        )

    def save_session(self, session: SessionRecord) -> SaveResult:
        self._execute(
            """INSERT INTO sessions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (anonymous_session_id) DO UPDATE SET
            session_completed_at=EXCLUDED.session_completed_at,
            conversation_turn_count=EXCLUDED.conversation_turn_count,
            entry_source=EXCLUDED.entry_source, app_version=EXCLUDED.app_version,
            consent_version=EXCLUDED.consent_version, consented_at=EXCLUDED.consented_at,
            data_source=EXCLUDED.data_source""",
            (
                session.anonymous_session_id,
                session.session_started_at,
                session.session_completed_at,
                session.conversation_turn_count,
                session.entry_source,
                session.app_version,
                session.consent_version,
                session.consented_at,
                session.data_source,
            ),
        )
        return SaveResult(saved=True)

    def save_final_requirement(self, item: FinalRequirementRecord) -> SaveResult:
        self._execute(
            """INSERT INTO final_requirements VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
            ON CONFLICT (anonymous_session_id) DO UPDATE SET
            recipient=EXCLUDED.recipient, scene=EXCLUDED.scene,
            budget_type=EXCLUDED.budget_type, budget_per_item=EXCLUDED.budget_per_item,
            total_budget=EXCLUDED.total_budget, quantity=EXCLUDED.quantity,
            style_preferences=EXCLUDED.style_preferences,
            symbolism_preferences=EXCLUDED.symbolism_preferences,
            customization_types=EXCLUDED.customization_types,
            logo_required=EXCLUDED.logo_required, destination=EXCLUDED.destination,
            required_delivery_days=EXCLUDED.required_delivery_days,
            output_language=EXCLUDED.output_language,
            user_provided_fields=EXCLUDED.user_provided_fields,
            inferred_fields=EXCLUDED.inferred_fields""",
            (
                item.anonymous_session_id,
                item.recipient,
                item.scene,
                item.budget_type,
                item.budget_per_item,
                item.total_budget,
                item.quantity,
                _json(item.style_preferences),
                _json(item.symbolism_preferences),
                _json(item.customization_types),
                item.logo_required,
                item.destination,
                item.required_delivery_days,
                item.output_language,
                _json(item.user_provided_fields),
                _json(item.inferred_fields),
            ),
        )
        return SaveResult(saved=True)

    def save_recommendation(self, event: RecommendationEvent) -> SaveResult:
        self._execute(
            """INSERT INTO recommendation_events VALUES
            (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)
            ON CONFLICT DO NOTHING""",
            (
                event.recommendation_event_id,
                event.anonymous_session_id,
                event.recommendation_signature,
                _json(event.recommended_product_ids),
                _json(event.ranking_positions),
                _json(event.match_scores),
                event.recommendation_timestamp,
            ),
        )
        return SaveResult(saved=True)

    def save_selection(self, event: SelectionEvent) -> SaveResult:
        self._execute(
            """INSERT INTO selection_events VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (selection_event_id) DO UPDATE SET
            final_action=EXCLUDED.final_action,
            whether_customization_brief_generated=EXCLUDED.whether_customization_brief_generated,
            selection_reason=EXCLUDED.selection_reason,
            rejection_reason=EXCLUDED.rejection_reason,
            satisfaction_rating=EXCLUDED.satisfaction_rating""",
            (
                event.selection_event_id,
                event.recommendation_event_id,
                event.anonymous_session_id,
                event.selected_product_id,
                event.selected_rank_position,
                event.selected_at,
                event.final_action,
                event.whether_customization_brief_generated,
                event.selection_reason,
                event.rejection_reason,
                event.satisfaction_rating,
            ),
        )
        return SaveResult(saved=True)


def _json(value: tuple[object, ...]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_psycopg_connect() -> Callable[[str], ConnectionLike]:
    try:
        from psycopg import connect
    except ImportError as exc:
        raise RuntimeError("使用 PostgreSQL 分析存储需要安装 psycopg") from exc
    return connect  # type: ignore[return-value]
