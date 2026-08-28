"""Typed contracts for turning artisan testimony into a reviewable story source."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class OralSourceKind(StrEnum):
    PASTED_TEXT = "pasted_text"
    AUDIO = "audio"
    VIDEO = "video"


class OralClaimCategory(StrEnum):
    IDENTITY = "identity"
    JOURNEY = "journey"
    MEMORY = "memory"
    CRAFT_PROCESS = "craft_process"
    CHALLENGE = "challenge"
    TURNING_POINT = "turning_point"
    PERSONAL_MEANING = "personal_meaning"
    ASPIRATION = "aspiration"
    CREDENTIAL = "credential"
    COMMERCIAL = "commercial"


class OralClaimStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXCLUDED = "excluded"
    NEEDS_EVIDENCE = "needs_evidence"


class OralStoryStatus(StrEnum):
    REVIEWING = "reviewing"
    READY_FOR_SCRIPT = "ready_for_script"


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    segment_id: str
    ordinal: int
    text: str
    start_seconds: int | None = None
    end_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.segment_id.strip() or not self.text.strip():
            raise ValueError("transcript segment requires identity and text")
        if self.ordinal < 1:
            raise ValueError("transcript segment ordinal must be positive")
        if self.start_seconds is not None and self.start_seconds < 0:
            raise ValueError("transcript start time cannot be negative")
        if self.end_seconds is not None and (
            self.start_seconds is None or self.end_seconds <= self.start_seconds
        ):
            raise ValueError("transcript end time must follow its start time")

    @property
    def locator(self) -> str:
        if self.start_seconds is None:
            return self.segment_id
        minutes, seconds = divmod(self.start_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"


@dataclass(frozen=True, slots=True)
class OralStoryClaim:
    claim_id: str
    category: OralClaimCategory
    field_name: str
    statement: str
    source_quote: str
    segment_id: str
    source_locator: str
    status: OralClaimStatus
    requires_external_evidence: bool = False
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        required = (
            self.claim_id,
            self.field_name,
            self.statement,
            self.source_quote,
            self.segment_id,
            self.source_locator,
        )
        if not all(value.strip() for value in required):
            raise ValueError("oral story claim fields cannot be blank")
        if self.requires_external_evidence and self.status is OralClaimStatus.CONFIRMED:
            raise ValueError("external claims cannot be confirmed from testimony alone")
        if self.status in {
            OralClaimStatus.CONFIRMED,
            OralClaimStatus.EXCLUDED,
        } and (not (self.reviewer_id or "").strip() or self.reviewed_at is None):
            raise ValueError("final oral claim decisions require reviewer provenance")
        if self.reviewed_at is not None and self.reviewed_at.tzinfo is None:
            raise ValueError("oral claim review time must include timezone")


@dataclass(frozen=True, slots=True)
class OralStorySession:
    session_id: str
    artisan_id: str
    product_id: str
    source_kind: OralSourceKind
    source_name: str
    transcript: str
    transcript_sha256: str
    segments: tuple[TranscriptSegment, ...]
    claims: tuple[OralStoryClaim, ...]
    status: OralStoryStatus = OralStoryStatus.REVIEWING
    media_sha256: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        identity = (
            self.session_id,
            self.artisan_id,
            self.product_id,
            self.source_name,
            self.transcript,
            self.transcript_sha256,
        )
        if not all(value.strip() for value in identity):
            raise ValueError("oral story session requires source and transcript identity")
        if len(self.transcript_sha256) != 64:
            raise ValueError("transcript_sha256 must be a SHA-256 hex digest")
        if self.media_sha256 is not None and len(self.media_sha256) != 64:
            raise ValueError("media_sha256 must be a SHA-256 hex digest")
        if not self.segments or not self.claims:
            raise ValueError("oral story session requires transcript segments and claims")
        if any(value.tzinfo is None for value in (self.created_at, self.updated_at)):
            raise ValueError("oral story session timestamps must include timezone")
        segment_ids = [segment.segment_id for segment in self.segments]
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(set(segment_ids)) != len(segment_ids) or len(set(claim_ids)) != len(claim_ids):
            raise ValueError("oral story segment and claim ids must be unique")
        if not {claim.segment_id for claim in self.claims} <= set(segment_ids):
            raise ValueError("oral story claims must reference transcript segments")
        if self.status is OralStoryStatus.READY_FOR_SCRIPT and self.confirmed_count < 2:
            raise ValueError("a script-ready oral story requires two confirmed claims")

    @property
    def confirmed_claims(self) -> tuple[OralStoryClaim, ...]:
        return tuple(claim for claim in self.claims if claim.status is OralClaimStatus.CONFIRMED)

    @property
    def confirmed_count(self) -> int:
        return len(self.confirmed_claims)

    @property
    def blocked_count(self) -> int:
        return sum(claim.status is OralClaimStatus.NEEDS_EVIDENCE for claim in self.claims)


__all__ = [
    "OralClaimCategory",
    "OralClaimStatus",
    "OralSourceKind",
    "OralStoryClaim",
    "OralStorySession",
    "OralStoryStatus",
    "TranscriptSegment",
]
