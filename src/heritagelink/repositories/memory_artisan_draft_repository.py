"""In-memory Artisan Studio draft storage, isolated from buyer analytics."""

from __future__ import annotations

from heritagelink.heritage_passport_models import ArtisanProductDraft


class MemoryArtisanDraftRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.drafts: dict[str, ArtisanProductDraft] = {}

    def save(self, draft: ArtisanProductDraft) -> None:
        if self.fail:
            raise RuntimeError("artisan draft storage unavailable")
        self.drafts[draft.draft_id] = draft

    def get(self, draft_id: str) -> ArtisanProductDraft | None:
        if self.fail:
            raise RuntimeError("artisan draft storage unavailable")
        return self.drafts.get(draft_id)

    def list_for_session(self, session_id: str) -> tuple[ArtisanProductDraft, ...]:
        if self.fail:
            raise RuntimeError("artisan draft storage unavailable")
        return tuple(
            sorted(
                (draft for draft in self.drafts.values() if draft.session_id == session_id),
                key=lambda draft: (draft.created_at, draft.draft_id),
            )
        )
