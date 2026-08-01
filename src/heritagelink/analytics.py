"""Consent-aware, failure-tolerant orchestration for choice analytics."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from heritagelink.analytics_models import (
    RecommendationEvent,
    SelectionEvent,
)
from heritagelink.analytics_service import capture_consented_choice
from heritagelink.dialogue_manager import recommendation_signature
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.choice_repository import ChoiceRepository
from heritagelink.repositories.postgres_choice_repository import PostgresChoiceRepository
from heritagelink.repositories.sqlite_choice_repository import SQLiteChoiceRepository

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalyticsSettings:
    enabled: bool = False
    database_url: str = ""
    store_raw_chat: bool = False
    app_version: str = "0.1.0"
    backend: str = "auto"
    consent_version: str = "analytics-consent-v1"

    @classmethod
    def from_env(cls) -> AnalyticsSettings:
        return cls(
            enabled=_env_bool("ANALYTICS_ENABLED", False),
            database_url=os.getenv("ANALYTICS_DATABASE_URL", "").strip(),
            # Raw-chat persistence is intentionally not implemented in this stage.
            store_raw_chat=False,
            app_version=os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0",
            backend=os.getenv("ANALYTICS_BACKEND", "auto").strip().lower() or "auto",
        )


def create_choice_repository(settings: AnalyticsSettings) -> ChoiceRepository | None:
    """Create a configured adapter, or safely disable persistence."""
    if not settings.enabled or not settings.database_url:
        return None
    if settings.backend not in {"auto", "sqlite", "postgres"}:
        raise ValueError("ANALYTICS_BACKEND 仅支持 auto、sqlite 或 postgres")
    if settings.database_url.startswith("sqlite:///"):
        if settings.backend == "postgres":
            raise ValueError("ANALYTICS_BACKEND 与数据库地址不匹配")
        path = Path(settings.database_url.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)
        return SQLiteChoiceRepository(path)
    if settings.database_url.startswith(("postgresql://", "postgres://")):
        if settings.backend == "sqlite":
            raise ValueError("ANALYTICS_BACKEND 与数据库地址不匹配")
        return PostgresChoiceRepository(settings.database_url)
    raise ValueError("ANALYTICS_DATABASE_URL 仅支持 sqlite:///、postgresql:// 或 postgres://")


def new_anonymous_session_id() -> str:
    return f"anon_{uuid4().hex}"


def build_recommendation_event(
    anonymous_session_id: str,
    context: RecommendationContext,
    result: ProgressiveRecommendationResult,
    *,
    timestamp: datetime | None = None,
) -> RecommendationEvent:
    signature = recommendation_signature(context.effective_request)
    event_id = str(uuid5(NAMESPACE_URL, f"{anonymous_session_id}:recommend:{signature}"))
    recommendations = result.response.recommendations
    return RecommendationEvent(
        recommendation_event_id=event_id,
        anonymous_session_id=anonymous_session_id,
        recommendation_signature=signature,
        recommended_product_ids=tuple(item.product.product_id for item in recommendations),
        ranking_positions=tuple(range(1, len(recommendations) + 1)),
        match_scores=tuple(item.total_score for item in recommendations),
        recommendation_timestamp=timestamp or datetime.now(UTC),
    )


def build_selection_event(
    recommendation_event: RecommendationEvent,
    selected_product_id: str,
    *,
    final_action: str = "selected",
    brief_generated: bool = False,
    timestamp: datetime | None = None,
) -> SelectionEvent:
    if selected_product_id not in recommendation_event.recommended_product_ids:
        raise ValueError("选择的产品不在本次推荐结果中")
    rank = recommendation_event.recommended_product_ids.index(selected_product_id) + 1
    event_id = str(
        uuid5(
            NAMESPACE_URL,
            f"{recommendation_event.recommendation_event_id}:select:"
            f"{selected_product_id}:{final_action}",
        )
    )
    return SelectionEvent(
        selection_event_id=event_id,
        recommendation_event_id=recommendation_event.recommendation_event_id,
        anonymous_session_id=recommendation_event.anonymous_session_id,
        selected_product_id=selected_product_id,
        selected_rank_position=rank,
        selected_at=timestamp or datetime.now(UTC),
        final_action=final_action,
        whether_customization_brief_generated=brief_generated,
    )


def persist_recommendation_choice(
    repository: ChoiceRepository | None,
    *,
    consent: bool,
    session_id: str,
    session_started_at: datetime,
    conversation_turn_count: int,
    entry_source: str,
    app_version: str,
    context: RecommendationContext,
    recommendation_event: RecommendationEvent,
    selection_event: SelectionEvent | None = None,
) -> bool:
    """Backward-compatible boolean wrapper around the capture Skill service."""
    result = capture_consented_choice(
        repository,
        consent_granted=consent,
        consent_version="analytics-consent-v1",
        consented_at=selection_event.selected_at if selection_event else None,
        session_id=session_id,
        session_started_at=session_started_at,
        conversation_turn_count=conversation_turn_count,
        entry_source=entry_source,
        app_version=app_version,
        context=context,
        recommendation_event=recommendation_event,
        selection_event=selection_event,
    )
    return result.status in {"saved", "duplicate_ignored"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
