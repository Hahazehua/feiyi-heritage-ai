"""Executable service behind the capture-consented-choice Skill."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SelectionEvent,
    SessionRecord,
)
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.choice_repository import ChoiceRepository

LOGGER = logging.getLogger(__name__)
CaptureStatus = Literal[
    "saved",
    "skipped_no_consent",
    "skipped_no_selection",
    "duplicate_ignored",
    "storage_unavailable",
    "validation_failed",
]


@dataclass(frozen=True, slots=True)
class CaptureChoiceResult:
    status: CaptureStatus
    event_id: str | None
    saved: bool
    duplicate: bool
    storage_backend: str | None = None
    error_category: str | None = None


def capture_consented_choice(
    repository: ChoiceRepository | None,
    *,
    consent_granted: bool,
    consent_version: str,
    consented_at: datetime | None,
    session_id: str,
    session_started_at: datetime,
    conversation_turn_count: int,
    entry_source: str,
    app_version: str,
    context: RecommendationContext,
    recommendation_event: RecommendationEvent,
    selection_event: SelectionEvent | None,
) -> CaptureChoiceResult:
    """Save one anonymous choice atomically enough for a non-blocking UI workflow."""
    if not consent_granted:
        return CaptureChoiceResult("skipped_no_consent", None, False, False)
    if selection_event is None:
        return CaptureChoiceResult("skipped_no_selection", None, False, False)
    if repository is None:
        return CaptureChoiceResult(
            "storage_unavailable", selection_event.selection_event_id, False, False
        )
    if not _valid_event_chain(session_id, recommendation_event, selection_event):
        return CaptureChoiceResult(
            "validation_failed",
            selection_event.selection_event_id,
            False,
            False,
            error_category="invalid_event_chain",
        )

    parsed = context.effective_request
    session = SessionRecord(
        anonymous_session_id=session_id,
        session_started_at=session_started_at,
        session_completed_at=selection_event.selected_at,
        conversation_turn_count=max(0, conversation_turn_count),
        entry_source=entry_source,
        app_version=app_version,
        consent_version=consent_version,
        consented_at=consented_at or selection_event.selected_at,
    )
    requirement = FinalRequirementRecord(
        anonymous_session_id=session_id,
        recipient=parsed.recipient,
        scene=parsed.scene,
        budget_type=parsed.budget_type,
        budget_per_item=parsed.budget_per_item,
        total_budget=parsed.total_budget,
        quantity=parsed.quantity,
        style_preferences=parsed.style_preferences,
        symbolism_preferences=parsed.symbolism_preferences,
        customization_types=parsed.customization_types,
        logo_required=parsed.logo_required,
        destination=parsed.destination,
        required_delivery_days=parsed.required_delivery_days,
        output_language=parsed.output_language,
        user_provided_fields=tuple(sorted(context.user_provided_fields)),
        inferred_fields=tuple(sorted(context.inferred_fields)),
    )
    try:
        repository.save_session(session)
        repository.save_final_requirement(requirement)
        recommendation_result = repository.save_recommendation(recommendation_event)
        selection_result = repository.save_selection(selection_event)
    except Exception:
        LOGGER.exception("匿名推荐分析记录保存失败")
        return CaptureChoiceResult(
            "storage_unavailable",
            selection_event.selection_event_id,
            False,
            False,
            error_category="repository_error",
        )

    duplicate = bool(getattr(recommendation_result, "duplicate", False)) and bool(
        getattr(selection_result, "duplicate", False)
    )
    return CaptureChoiceResult(
        "duplicate_ignored" if duplicate else "saved",
        selection_event.selection_event_id,
        saved=not duplicate,
        duplicate=duplicate,
        storage_backend=repository.__class__.__name__,
    )


def _valid_event_chain(
    session_id: str,
    recommendation: RecommendationEvent,
    selection: SelectionEvent,
) -> bool:
    return bool(
        session_id.startswith("anon_")
        and recommendation.anonymous_session_id == session_id
        and selection.anonymous_session_id == session_id
        and selection.recommendation_event_id == recommendation.recommendation_event_id
        and selection.selected_product_id in recommendation.recommended_product_ids
    )
