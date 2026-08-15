"""Typed contracts for the Artisan-side HAHA Growth Studio.

The buyer Agent keeps its existing session state and seven formal Skills.  These
models describe a separate, bounded Artisan workflow whose outputs never change
catalogue eligibility or deterministic recommendation ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from heritagelink.agent_models import SkillExecutionTrace
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"
    USER_INSTRUCTION = "user_instruction"


class GrowthOutputSource(StrEnum):
    LIVE_AI = "live_ai"
    DETERMINISTIC_DEMO = "deterministic_demo"
    SAFE_FALLBACK = "safe_fallback"


class GrowthRunStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    FAILED_SAFE = "failed_safe"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    ARCHIVED = "archived"


class GuardianRiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class GroundedFact:
    field_name: str
    value: Any
    evidence_status: EvidenceStatus
    source: FactSource
    verification_status: VerificationStatus
    source_note: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValueError("field_name cannot be blank")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("source_url must be an HTTPS URL")
        if self.evidence_status is EvidenceStatus.VERIFIED and (
            self.verification_status is not VerificationStatus.CONFIRMED
        ):
            raise ValueError("verified evidence requires confirmed verification status")


@dataclass(frozen=True, slots=True)
class GrowthProductContext:
    artisan_id: str
    product_id: str
    product_name: str
    product_name_en: str | None
    craft_name: str
    publication_status: PublicationStatus
    verified_facts: tuple[GroundedFact, ...]
    unverified_facts: tuple[GroundedFact, ...]
    unknown_fields: tuple[str, ...]
    cultural_source_urls: tuple[str, ...] = ()
    context_label: str = "product-grounded context"

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.artisan_id, self.product_id, self.product_name, self.craft_name)
        ):
            raise ValueError("growth context requires stable artisan/product identity")
        verified_names = {fact.field_name for fact in self.verified_facts}
        unverified_names = {fact.field_name for fact in self.unverified_facts}
        if verified_names & unverified_names:
            raise ValueError("a fact cannot be both verified and unverified")

    @property
    def verified_by_name(self) -> dict[str, GroundedFact]:
        return {fact.field_name: fact for fact in self.verified_facts}

    @property
    def unverified_by_name(self) -> dict[str, GroundedFact]:
        return {fact.field_name: fact for fact in self.unverified_facts}

    @property
    def requires_draft_label(self) -> bool:
        return self.publication_status is not PublicationStatus.RECOMMENDABLE


@dataclass(frozen=True, slots=True)
class MarketOpportunity:
    segment: str
    fit_score: int
    reasons: tuple[str, ...]
    risks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.segment.strip() or not 0 <= self.fit_score <= 100:
            raise ValueError("market opportunity requires a segment and 0-100 fit score")


@dataclass(frozen=True, slots=True)
class MarketAnalysis:
    opportunities: tuple[MarketOpportunity, ...]
    recommended_segment: str
    summary: str
    evidence_basis: str
    external_evidence_used: bool
    source: GrowthOutputSource

    def __post_init__(self) -> None:
        if not self.opportunities:
            raise ValueError("market analysis requires at least one opportunity")
        if self.recommended_segment not in {item.segment for item in self.opportunities}:
            raise ValueError("recommended_segment must reference an opportunity")
        if self.external_evidence_used:
            raise ValueError("Growth Studio MVP does not accept unsourced external market evidence")


@dataclass(frozen=True, slots=True)
class MarketingStrategy:
    campaign_goal: str
    target_audience: tuple[str, ...]
    positioning: str
    value_proposition: str
    key_messages: tuple[str, ...]
    content_angles: tuple[str, ...]
    recommended_channels: tuple[str, ...]
    cta: str
    risks: tuple[str, ...]
    things_to_avoid: tuple[str, ...]
    reasoning_summary: str
    source: GrowthOutputSource

    def __post_init__(self) -> None:
        required = (self.campaign_goal, self.positioning, self.value_proposition, self.cta)
        if not all(value.strip() for value in required):
            raise ValueError("marketing strategy is missing required content")
        if not self.target_audience or not self.recommended_channels:
            raise ValueError("strategy requires an audience and at least one channel")


@dataclass(frozen=True, slots=True)
class CampaignClaim:
    claim_text: str
    field_name: str | None
    evidence_status: EvidenceStatus
    source_label: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_text.strip():
            raise ValueError("campaign claim cannot be blank")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("claim source_url must be HTTPS")


@dataclass(frozen=True, slots=True)
class CampaignAsset:
    asset_id: str
    channel: str
    asset_type: str
    content: str
    cta: str
    claims: tuple[CampaignClaim, ...]
    source_references: tuple[str, ...] = ()
    raw_ai_content: str | None = None
    revised_ai_content: str | None = None
    final_human_content: str | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip() for value in (self.asset_id, self.channel, self.asset_type, self.content)
        ):
            raise ValueError("campaign asset requires id, channel, type, and content")

    @property
    def display_content(self) -> str:
        return self.final_human_content or self.revised_ai_content or self.content


@dataclass(frozen=True, slots=True)
class GuardianIssue:
    asset_id: str
    issue_type: str
    claim: str
    reason: str
    source: str | None
    recommended_action: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.asset_id,
                self.issue_type,
                self.claim,
                self.reason,
                self.recommended_action,
            )
        ):
            raise ValueError("guardian issue fields cannot be blank")


@dataclass(frozen=True, slots=True)
class GuardianReview:
    approved: bool
    risk_level: GuardianRiskLevel
    issues: tuple[GuardianIssue, ...]
    supported_claims: tuple[str, ...]
    revision_instructions: tuple[str, ...]
    reviewed_asset_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.approved and self.issues:
            raise ValueError("approved guardian review cannot contain unresolved issues")
        if not self.approved and not self.issues:
            raise ValueError("rejected guardian review requires structured issues")


@dataclass(frozen=True, slots=True)
class GrowthRunRequest:
    artisan_id: str
    product_id: str
    campaign_goal: str
    target_geography: str | None = None
    optional_target_audience: str | None = None
    preferred_channels: tuple[str, ...] = ()
    language: str = "English"
    user_instructions: str | None = None
    output_source: GrowthOutputSource = GrowthOutputSource.DETERMINISTIC_DEMO
    demo_guardian_scenario: bool = False

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.artisan_id, self.product_id, self.campaign_goal, self.language)
        ):
            raise ValueError("growth request is missing required identity or goal")


@dataclass(frozen=True, slots=True)
class GrowthRunState:
    run_id: str
    request: GrowthRunRequest
    product_context: GrowthProductContext
    status: GrowthRunStatus = GrowthRunStatus.GENERATING
    market_analysis: MarketAnalysis | None = None
    strategy: MarketingStrategy | None = None
    campaign_assets: tuple[CampaignAsset, ...] = ()
    guardian_review: GuardianReview | None = None
    revision_count: int = 0
    trace_events: tuple[SkillExecutionTrace, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id.strip() or self.revision_count < 0:
            raise ValueError("growth run requires a stable id and non-negative revision count")


@dataclass(frozen=True, slots=True)
class MarketingCampaign:
    campaign_id: str
    campaign_name: str
    artisan_id: str
    product_id: str
    goal: str
    target_geography: str | None
    target_segment: str
    market_analysis: MarketAnalysis
    strategy: MarketingStrategy
    assets: tuple[CampaignAsset, ...]
    guardian_review: GuardianReview
    revision_count: int
    status: CampaignStatus
    source: GrowthOutputSource
    trace_events: tuple[SkillExecutionTrace, ...]
    human_reviewed_warnings: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.campaign_id,
                self.campaign_name,
                self.artisan_id,
                self.product_id,
                self.goal,
                self.target_segment,
            )
        ):
            raise ValueError("campaign identity and goal fields cannot be blank")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("campaign timestamps must include timezone")
        if self.revision_count < 0:
            raise ValueError("revision_count cannot be negative")


__all__ = [
    "CampaignAsset",
    "CampaignClaim",
    "CampaignStatus",
    "EvidenceStatus",
    "GroundedFact",
    "GrowthOutputSource",
    "GrowthProductContext",
    "GrowthRunRequest",
    "GrowthRunState",
    "GrowthRunStatus",
    "GuardianIssue",
    "GuardianReview",
    "GuardianRiskLevel",
    "MarketAnalysis",
    "MarketOpportunity",
    "MarketingCampaign",
    "MarketingStrategy",
]
