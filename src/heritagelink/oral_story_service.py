"""Deterministic oral-history intake, review, provenance, and story handoff."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import FactSource, VerificationStatus
from heritagelink.oral_story_models import (
    OralClaimCategory,
    OralClaimStatus,
    OralSourceKind,
    OralStoryClaim,
    OralStorySession,
    OralStoryStatus,
    TranscriptSegment,
)
from heritagelink.story_models import NarrativeTemplate, StoryProject
from heritagelink.story_service import create_story_project

MIN_CONFIRMED_ORAL_CLAIMS = 2

_TIMESTAMP_PREFIX = re.compile(
    r"^\s*\[(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})\]\s*"
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_RISK_CREDENTIAL = re.compile(
    r"国家级|省级|大师|传承人|认证|非遗代表性|national(?:-level)?|master|certif",
    re.IGNORECASE,
)
_RISK_COMMERCIAL = re.compile(
    r"保证|全球配送|最低价|包邮|现货|交付|guarantee|global shipping|lowest price|in stock",
    re.IGNORECASE,
)
_CATEGORY_RULES: tuple[tuple[OralClaimCategory, str, re.Pattern[str]], ...] = (
    (
        OralClaimCategory.IDENTITY,
        "maker_identity",
        re.compile(r"我叫|我的名字|我是|my name is|i am ", re.IGNORECASE),
    ),
    (
        OralClaimCategory.JOURNEY,
        "artisan_journey",
        re.compile(
            r"开始|入行|学艺|跟.*学|做了.*年|小时候|从事|started|learned|apprentice|years",
            re.IGNORECASE,
        ),
    ),
    (
        OralClaimCategory.ASPIRATION,
        "future_wish",
        re.compile(r"希望|想让|传下去|年轻人|以后|未来|hope|future|pass.*on", re.IGNORECASE),
    ),
    (
        OralClaimCategory.CHALLENGE,
        "craft_challenge",
        re.compile(r"最难|困难|失败|不容易|难点|hardest|difficult|failed", re.IGNORECASE),
    ),
    (
        OralClaimCategory.TURNING_POINT,
        "turning_point",
        re.compile(r"后来|那一次|转折|改变|差点|放弃|then|changed|almost gave up", re.IGNORECASE),
    ),
    (
        OralClaimCategory.CRAFT_PROCESS,
        "oral_craft_process",
        re.compile(
            r"工序|步骤|锻打|焊接|敲|烧|磨|剪|画稿|制作|做的时候|process|hammer|weld|make",
            re.IGNORECASE,
        ),
    ),
    (
        OralClaimCategory.PERSONAL_MEANING,
        "personal_meaning",
        re.compile(r"觉得|感到|对我|意味着|喜欢|心里|feel|means to me|love", re.IGNORECASE),
    ),
)


def create_oral_story_session(
    context: GrowthProductContext,
    transcript: str,
    *,
    source_kind: OralSourceKind = OralSourceKind.PASTED_TEXT,
    source_name: str = "pasted-transcript.txt",
    media_sha256: str | None = None,
    now: datetime | None = None,
) -> OralStorySession:
    """Create a review session without treating extracted statements as facts."""
    normalized = _normalize_transcript(transcript)
    if not normalized:
        raise ValueError("oral story transcript cannot be blank")
    segments = _segment_transcript(normalized)
    claims = _extract_claims(segments)
    created_at = now or datetime.now(UTC)
    transcript_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return OralStorySession(
        session_id=f"oral-{context.product_id}-{transcript_hash[:12]}",
        artisan_id=context.artisan_id,
        product_id=context.product_id,
        source_kind=source_kind,
        source_name=source_name.strip() or "transcript.txt",
        transcript=normalized,
        transcript_sha256=transcript_hash,
        media_sha256=media_sha256,
        segments=segments,
        claims=claims,
        created_at=created_at,
        updated_at=created_at,
    )


def review_oral_story_claims(
    session: OralStorySession,
    decisions: Mapping[str, OralClaimStatus],
    *,
    actor_id: str,
    edited_statements: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> OralStorySession:
    """Apply explicit human decisions while keeping risky external claims blocked."""
    if not actor_id.strip():
        raise ValueError("oral story review requires an actor id")
    reviewed_at = now or datetime.now(UTC)
    edits = edited_statements or {}
    reviewed: list[OralStoryClaim] = []
    known_ids = {claim.claim_id for claim in session.claims}
    if not set(decisions) <= known_ids or not set(edits) <= known_ids:
        raise ValueError("oral story review references an unknown claim")

    for claim in session.claims:
        decision = decisions.get(claim.claim_id, claim.status)
        statement = edits.get(claim.claim_id, claim.statement).strip()
        if not statement:
            raise ValueError("confirmed oral statements cannot be blank")
        if claim.requires_external_evidence and decision is OralClaimStatus.CONFIRMED:
            raise ValueError("credential and commercial claims require external evidence")
        if claim.requires_external_evidence and decision is OralClaimStatus.PENDING:
            decision = OralClaimStatus.NEEDS_EVIDENCE
        final = decision in {OralClaimStatus.CONFIRMED, OralClaimStatus.EXCLUDED}
        reviewed.append(
            replace(
                claim,
                statement=statement,
                status=decision,
                reviewer_id=actor_id if final else None,
                reviewed_at=reviewed_at if final else None,
            )
        )

    confirmed_count = sum(item.status is OralClaimStatus.CONFIRMED for item in reviewed)
    status = (
        OralStoryStatus.READY_FOR_SCRIPT
        if confirmed_count >= MIN_CONFIRMED_ORAL_CLAIMS
        else OralStoryStatus.REVIEWING
    )
    return replace(session, claims=tuple(reviewed), status=status, updated_at=reviewed_at)


def confirm_publishable_oral_claims(
    session: OralStorySession,
    *,
    actor_id: str,
    now: datetime | None = None,
) -> OralStorySession:
    """One explicit bulk decision: confirm personal testimony and exclude risky claims."""
    decisions = {
        claim.claim_id: (
            OralClaimStatus.EXCLUDED
            if claim.requires_external_evidence
            else OralClaimStatus.CONFIRMED
        )
        for claim in session.claims
    }
    return review_oral_story_claims(session, decisions, actor_id=actor_id, now=now)


def build_oral_story_context(
    base_context: GrowthProductContext,
    session: OralStorySession,
) -> GrowthProductContext:
    """Add confirmed testimony as traceable facts for the dedicated oral template."""
    if (
        session.product_id != base_context.product_id
        or session.artisan_id != base_context.artisan_id
    ):
        raise ValueError("oral story session does not match the selected product")
    if session.status is not OralStoryStatus.READY_FOR_SCRIPT:
        raise ValueError("confirm at least two oral statements before generating a script")

    grouped: dict[str, list[OralStoryClaim]] = defaultdict(list)
    for claim in session.confirmed_claims:
        grouped[claim.field_name].append(claim)

    oral_facts = tuple(
        GroundedFact(
            field_name=field_name,
            value="；".join(claim.statement for claim in claims),
            evidence_status=EvidenceStatus.VERIFIED,
            source=FactSource.ARTISAN_PROVIDED,
            verification_status=VerificationStatus.CONFIRMED,
            source_note=(
                "手艺人口述并由本人确认；来源："
                + "、".join(f"{claim.source_locator} ({claim.claim_id})" for claim in claims)
            ),
        )
        for field_name, claims in grouped.items()
    )
    oral_names = {fact.field_name for fact in oral_facts}
    retained = tuple(
        fact for fact in base_context.verified_facts if fact.field_name not in oral_names
    )
    return replace(
        base_context,
        verified_facts=(*retained, *oral_facts),
        context_label=f"oral-story:{session.session_id}",
    )


def create_project_from_oral_story(
    base_context: GrowthProductContext,
    session: OralStorySession,
    *,
    language: str = "Chinese",
    now: datetime | None = None,
) -> StoryProject:
    """Generate the existing Guardian-reviewed 60-second project from testimony."""
    context = build_oral_story_context(base_context, session)
    return create_story_project(
        context,
        NarrativeTemplate.ORAL_HISTORY,
        language,
        now=now,
    )


def export_oral_story_session(session: OralStorySession) -> bytes:
    """Export the immutable transcript, decisions, hashes, and source locators."""
    return json.dumps(
        asdict(session),
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    ).encode("utf-8")


def media_sha256(data: bytes) -> str:
    if not data:
        raise ValueError("media source cannot be empty")
    return hashlib.sha256(data).hexdigest()


def _segment_transcript(transcript: str) -> tuple[TranscriptSegment, ...]:
    parts = [part.strip() for part in _SENTENCE_BOUNDARY.split(transcript) if part.strip()]
    segments: list[TranscriptSegment] = []
    for part in parts:
        match = _TIMESTAMP_PREFIX.match(part)
        start_seconds = None
        text = part
        if match:
            start_seconds = (
                int(match.group("hours") or 0) * 3600
                + int(match.group("minutes")) * 60
                + int(match.group("seconds"))
            )
            text = part[match.end() :].strip()
        if text:
            segments.append(
                TranscriptSegment(
                    segment_id=f"segment-{len(segments) + 1:03d}",
                    ordinal=len(segments) + 1,
                    text=text,
                    start_seconds=start_seconds,
                )
            )
    if not segments:
        raise ValueError("oral story transcript contains no readable statements")
    return tuple(segments)


def _extract_claims(segments: tuple[TranscriptSegment, ...]) -> tuple[OralStoryClaim, ...]:
    claims: list[OralStoryClaim] = []
    for segment in segments:
        category, field_name, risky = _classify(segment.text)
        claims.append(
            OralStoryClaim(
                claim_id=f"claim-{len(claims) + 1:03d}",
                category=category,
                field_name=field_name,
                statement=segment.text,
                source_quote=segment.text,
                segment_id=segment.segment_id,
                source_locator=segment.locator,
                status=(OralClaimStatus.NEEDS_EVIDENCE if risky else OralClaimStatus.PENDING),
                requires_external_evidence=risky,
            )
        )
    return tuple(claims)


def _classify(text: str) -> tuple[OralClaimCategory, str, bool]:
    if _RISK_CREDENTIAL.search(text):
        return OralClaimCategory.CREDENTIAL, "credential_claim", True
    if _RISK_COMMERCIAL.search(text):
        return OralClaimCategory.COMMERCIAL, "commercial_claim", True
    for category, field_name, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return category, field_name, False
    return OralClaimCategory.MEMORY, "personal_memory", False


def _normalize_transcript(transcript: str) -> str:
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in transcript.splitlines())
    return "\n".join(line for line in lines if line).strip()


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported oral story export value: {type(value).__name__}")


__all__ = [
    "MIN_CONFIRMED_ORAL_CLAIMS",
    "build_oral_story_context",
    "confirm_publishable_oral_claims",
    "create_oral_story_session",
    "create_project_from_oral_story",
    "export_oral_story_session",
    "media_sha256",
    "review_oral_story_claims",
]
