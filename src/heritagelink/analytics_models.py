"""Privacy-minimized analytics records for recommendation choice analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AnalyticsDataSource = Literal["consented_user", "synthetic_demo"]


@dataclass(frozen=True, slots=True)
class SessionRecord:
    anonymous_session_id: str
    session_started_at: datetime
    session_completed_at: datetime | None
    conversation_turn_count: int
    entry_source: str
    app_version: str
    consent_version: str = "analytics-consent-v1"
    consented_at: datetime | None = None
    data_source: AnalyticsDataSource = "consented_user"


@dataclass(frozen=True, slots=True)
class FinalRequirementRecord:
    anonymous_session_id: str
    recipient: str | None
    scene: str | None
    budget_type: str | None
    budget_per_item: float | None
    total_budget: float | None
    quantity: int | None
    style_preferences: tuple[str, ...]
    symbolism_preferences: tuple[str, ...]
    customization_types: tuple[str, ...]
    logo_required: bool | None
    destination: str | None
    required_delivery_days: int | None
    output_language: str | None
    user_provided_fields: tuple[str, ...]
    inferred_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecommendationEvent:
    recommendation_event_id: str
    anonymous_session_id: str
    recommendation_signature: str
    recommended_product_ids: tuple[str, ...]
    ranking_positions: tuple[int, ...]
    match_scores: tuple[float, ...]
    recommendation_timestamp: datetime


@dataclass(frozen=True, slots=True)
class SelectionEvent:
    selection_event_id: str
    recommendation_event_id: str
    anonymous_session_id: str
    selected_product_id: str
    selected_rank_position: int
    selected_at: datetime
    final_action: str
    whether_customization_brief_generated: bool
    selection_reason: str | None = None
    rejection_reason: str | None = None
    satisfaction_rating: int | None = None

    def __post_init__(self) -> None:
        if self.selected_rank_position < 1:
            raise ValueError("selected_rank_position 必须大于 0")
        if self.satisfaction_rating is not None and not 1 <= self.satisfaction_rating <= 5:
            raise ValueError("satisfaction_rating 必须在 1 到 5 之间")


@dataclass(frozen=True, slots=True)
class SaveResult:
    """Repository write result without exposing driver or SQL details."""

    saved: bool
    duplicate: bool = False
