"""Storage protocol kept independent from Streamlit."""

from __future__ import annotations

from typing import Protocol

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SaveResult,
    SelectionEvent,
    SessionRecord,
)


class ChoiceRepository(Protocol):
    def save_session(self, session: SessionRecord) -> SaveResult: ...

    def save_final_requirement(self, requirement: FinalRequirementRecord) -> SaveResult: ...

    def save_recommendation(self, event: RecommendationEvent) -> SaveResult: ...

    def save_selection(self, event: SelectionEvent) -> SaveResult: ...
