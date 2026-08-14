"""Typed contracts for artisan onboarding and Heritage Passport facts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any


class FactSource(StrEnum):
    ARTISAN_PROVIDED = "artisan_provided"
    ARTISAN_CONFIRMED = "artisan_confirmed"
    MERCHANT_CONFIRMED = "merchant_confirmed"
    PUBLIC_SOURCE = "public_source"
    AI_INFERRED = "ai_inferred"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    CONFIRMED = "confirmed"
    PENDING_REVIEW = "pending_review"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REFERENCE_ONLY = "reference_only"
    RECOMMENDABLE = "recommendable"
    ARCHIVED = "archived"


class FactGroup(StrEnum):
    IDENTITY = "identity"
    CULTURAL = "cultural"
    COMMERCIAL = "commercial"
    CONTENT = "content"


@dataclass(frozen=True, slots=True)
class SourceReference:
    label: str
    url: str
    source: FactSource = FactSource.PUBLIC_SOURCE
    verification_status: VerificationStatus = VerificationStatus.PENDING_REVIEW

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.url.startswith("https://"):
            raise ValueError("来源必须包含名称和完整 HTTPS 地址")


@dataclass(frozen=True, slots=True)
class ProvenancedFact:
    field_name: str
    value: Any
    group: FactGroup
    source: FactSource
    verification_status: VerificationStatus
    source_note: str | None = None
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValueError("fact field_name 不能为空")
        if (
            self.source is FactSource.AI_INFERRED
            and self.verification_status is VerificationStatus.CONFIRMED
        ):
            raise ValueError("AI inferred 字段不能自动确认为事实")
        if self.verification_status is VerificationStatus.CONFIRMED and self.source not in {
            FactSource.ARTISAN_CONFIRMED,
            FactSource.MERCHANT_CONFIRMED,
            FactSource.PUBLIC_SOURCE,
        }:
            raise ValueError("confirmed 字段必须来自人工确认或公开来源")

    def confirm_by_artisan(self, confirmed_at: datetime) -> ProvenancedFact:
        if confirmed_at.tzinfo is None:
            raise ValueError("confirmed_at 必须包含时区")
        return replace(
            self,
            source=FactSource.ARTISAN_CONFIRMED,
            verification_status=VerificationStatus.CONFIRMED,
            confirmed_at=confirmed_at,
        )


@dataclass(frozen=True, slots=True)
class FactConflict:
    field_name: str
    current_value: Any
    incoming_value: Any
    resolved_value: Any | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_value is not None


@dataclass(frozen=True, slots=True)
class BilingualProductDraft:
    overview_zh: str
    overview_en: str
    craft_background_zh: str
    craft_background_en: str
    cultural_meaning_zh: str
    cultural_meaning_en: str
    gifting_contexts_zh: str
    gifting_contexts_en: str
    customization_zh: str
    customization_en: str
    source: FactSource = FactSource.AI_INFERRED
    verification_status: VerificationStatus = VerificationStatus.PENDING_REVIEW

    def __post_init__(self) -> None:
        if (
            self.source is FactSource.AI_INFERRED
            and self.verification_status is VerificationStatus.CONFIRMED
        ):
            raise ValueError("AI 双语草稿必须由人工确认")


@dataclass(frozen=True, slots=True)
class ArtisanProductDraft:
    draft_id: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    facts: tuple[ProvenancedFact, ...]
    publication_status: PublicationStatus = PublicationStatus.DRAFT
    image_name: str | None = None
    image_bytes: bytes | None = field(default=None, repr=False, compare=False)
    bilingual_draft: BilingualProductDraft | None = None
    conflicts: tuple[FactConflict, ...] = ()
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.draft_id.strip() or not self.session_id.strip():
            raise ValueError("draft_id 和 session_id 不能为空")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("草稿时间必须包含时区")
        names = tuple(fact.field_name for fact in self.facts)
        if len(set(names)) != len(names):
            raise ValueError("草稿 facts 不能包含重复字段")
        if (
            self.publication_status is PublicationStatus.PENDING_REVIEW
            and self.submitted_at is None
        ):
            raise ValueError("pending_review 草稿必须记录提交时间")

    @property
    def facts_by_name(self) -> dict[str, ProvenancedFact]:
        return {fact.field_name: fact for fact in self.facts}


@dataclass(frozen=True, slots=True)
class HeritagePassport:
    passport_id: str
    product_id: str
    artisan_or_merchant_name: str | None
    product_name_zh: str
    product_name_en: str | None
    craft_name: str
    region: str | None
    cultural_background_zh: str | None
    cultural_background_en: str | None
    symbolism: tuple[str, ...]
    cultural_sources: tuple[SourceReference, ...]
    commercial_facts: tuple[ProvenancedFact, ...]
    cultural_verification_status: VerificationStatus
    commercial_verification_status: VerificationStatus
    publication_status: PublicationStatus
    reviewed_at: datetime | None
    bilingual_content: BilingualProductDraft | None = None

    def __post_init__(self) -> None:
        required = (
            self.passport_id,
            self.product_id,
            self.product_name_zh,
            self.craft_name,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Heritage Passport 必须包含稳定 ID、作品名和工艺")
