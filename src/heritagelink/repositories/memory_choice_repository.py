"""In-memory repository for deterministic Skill tests."""

from __future__ import annotations

from heritagelink.analytics_models import (
    FinalRequirementRecord,
    RecommendationEvent,
    SaveResult,
    SelectionEvent,
    SessionRecord,
)


class MemoryChoiceRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sessions: dict[str, SessionRecord] = {}
        self.requirements: dict[str, FinalRequirementRecord] = {}
        self.recommendations: dict[str, RecommendationEvent] = {}
        self.selections: dict[str, SelectionEvent] = {}

    def _check(self) -> None:
        if self.fail:
            raise RuntimeError("storage unavailable")

    def save_session(self, session: SessionRecord) -> SaveResult:
        self._check()
        duplicate = self.sessions.get(session.anonymous_session_id) == session
        self.sessions[session.anonymous_session_id] = session
        return SaveResult(saved=not duplicate, duplicate=duplicate)

    def save_final_requirement(self, requirement: FinalRequirementRecord) -> SaveResult:
        self._check()
        key = requirement.anonymous_session_id
        duplicate = self.requirements.get(key) == requirement
        self.requirements[key] = requirement
        return SaveResult(saved=not duplicate, duplicate=duplicate)

    def save_recommendation(self, event: RecommendationEvent) -> SaveResult:
        self._check()
        duplicate = event.recommendation_event_id in self.recommendations
        if not duplicate:
            self.recommendations[event.recommendation_event_id] = event
        return SaveResult(saved=not duplicate, duplicate=duplicate)

    def save_selection(self, event: SelectionEvent) -> SaveResult:
        self._check()
        duplicate = self.selections.get(event.selection_event_id) == event
        self.selections[event.selection_event_id] = event
        return SaveResult(saved=not duplicate, duplicate=duplicate)
