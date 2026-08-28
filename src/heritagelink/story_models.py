"""Typed contracts for the L1 Story Core — the narrative layer that sits between a
product's grounded facts and any generated script.

The Story Core exists so that no shot list, voiceover, or subtitle is ever written
straight from a product record.  Every assertion a story makes is first entered in a
claim ledger that names the fact it rests on, or declares itself artistic licence.
Downstream layers (L2 shot list, L3 cultural review, L4 render) read that ledger
instead of re-deriving provenance, so the film's end card can be computed rather
than written by hand.

The invariants below are deliberately enforced in ``__post_init__``: a ledger entry
that claims verified grounding without naming a fact is not a bug to be caught in
review, it is a value that cannot be constructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from heritagelink.growth_models import EvidenceStatus, GrowthOutputSource, GuardianRiskLevel

#: Reserved beat id for the cultural anchor, which belongs to the story rather than
#: to any single beat.
ANCHOR_BEAT_ID = "anchor"

MIN_BEATS = 3
MAX_BEATS = 5


class NarrativeTemplate(StrEnum):
    """The three story shapes the Story Studio ships with."""

    OBJECT_RECORD = "object_record"  # 器物志 — the object leads, the craft is the subject
    ARTISAN_LIFE = "artisan_life"  # 匠人传 — the maker leads, lineage is the subject
    TIME_DIALOGUE = "time_dialogue"  # 时空对话 — a museum piece answered by a modern remake


class ClaimUse(StrEnum):
    """How a line of narration leans on the fact record."""

    GROUNDED = "grounded"  # traced to a confirmed fact; may be stated plainly
    ATTRIBUTED = "attributed"  # rests on an unconfirmed fact; must be spoken with a hedge
    ARTISTIC = "artistic"  # narrative glue with no factual backing; declared as such


class StoryPlatform(StrEnum):
    """Vertical-video publication targets supported by Story Studio."""

    XIAOHONGSHU = "xiaohongshu"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    YOUTUBE_SHORTS = "youtube_shorts"


class StorySceneKind(StrEnum):
    """A small, stable vocabulary for downstream image and video adapters."""

    HOOK = "hook"
    NARRATIVE = "narrative"
    CTA = "cta"


class StoryProjectStatus(StrEnum):
    """Approval states for a generated story package."""

    DRAFT = "draft"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"
    REJECTED = "rejected"


class StoryDecision(StrEnum):
    """Decisions a human reviewer can make after Guardian review."""

    APPROVE = "approve"
    REQUEST_REVISION = "request_revision"
    REJECT = "reject"


#: Evidence an attributed claim is allowed to rest on.  UNKNOWN is excluded on
#: purpose: a field with no value cannot support a claim, hedged or otherwise.
_ATTRIBUTABLE = frozenset({EvidenceStatus.UNVERIFIED, EvidenceStatus.USER_INSTRUCTION})


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One line of the claim ledger: a single assertion and what it rests on."""

    entry_id: str
    beat_id: str
    claim_text: str
    use: ClaimUse
    field_name: str | None = None
    evidence_status: EvidenceStatus | None = None
    source_note: str | None = None
    source_url: str | None = None
    hedge: str | None = None

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.entry_id, self.beat_id, self.claim_text)):
            raise ValueError("ledger entry requires an id, a beat, and claim text")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("ledger source_url must be an HTTPS URL")

        if self.use is ClaimUse.ARTISTIC:
            if self.field_name is not None or self.evidence_status is not None:
                raise ValueError("artistic licence cannot cite a fact")
            if self.source_url is not None:
                raise ValueError("artistic licence cannot cite a source")
            return

        if not (self.field_name or "").strip():
            raise ValueError(f"a {self.use} claim must name the fact it rests on")

        if self.use is ClaimUse.GROUNDED:
            if self.evidence_status is not EvidenceStatus.VERIFIED:
                raise ValueError("grounded claims require verified evidence")
        elif self.evidence_status not in _ATTRIBUTABLE:
            raise ValueError("attributed claims rest on unverified or user-supplied facts only")
        elif not (self.hedge or "").strip():
            raise ValueError("attributed claims must carry the hedge that will be spoken")

    @property
    def is_publicly_checkable(self) -> bool:
        """Whether a viewer could follow this claim to a source themselves."""
        return self.use is ClaimUse.GROUNDED and self.source_url is not None

    @property
    def spoken_text(self) -> str:
        """The claim as it must be narrated, hedge included."""
        if self.use is ClaimUse.ATTRIBUTED and self.hedge:
            return f"{self.hedge}{self.claim_text}"
        return self.claim_text


@dataclass(frozen=True, slots=True)
class NarrativeBeat:
    """One movement of the story.  Beats carry no facts of their own — they are
    described by the ledger entries that point at them."""

    beat_id: str
    ordinal: int
    title: str
    intent: str
    summary: str
    emotion: str

    def __post_init__(self) -> None:
        required = (self.beat_id, self.title, self.intent, self.summary, self.emotion)
        if not all(value.strip() for value in required):
            raise ValueError("narrative beat is missing required text")
        if self.ordinal < 1:
            raise ValueError("beat ordinal is 1-based")
        if self.beat_id == ANCHOR_BEAT_ID:
            raise ValueError(f"beat id {ANCHOR_BEAT_ID!r} is reserved for the cultural anchor")


@dataclass(frozen=True, slots=True)
class ProvenanceSummary:
    """What the film's end card will say.  Computed from the ledger, never authored."""

    grounded: int
    attributed: int
    artistic: int
    checkable_sources: tuple[str, ...]

    @property
    def total_claims(self) -> int:
        return self.grounded + self.attributed + self.artistic


@dataclass(frozen=True, slots=True)
class LedgerFinding:
    """A discrepancy between a Story Core and the fact record it claims to rest on.

    Produced by a non-raising audit so the L3 cultural review can report every
    problem at once rather than failing on the first.
    """

    entry_id: str
    issue_type: str
    detail: str
    recommended_action: str

    def __post_init__(self) -> None:
        required = (self.entry_id, self.issue_type, self.detail, self.recommended_action)
        if not all(value.strip() for value in required):
            raise ValueError("ledger finding fields cannot be blank")


@dataclass(frozen=True, slots=True)
class StoryCore:
    """A story reduced to its load-bearing parts, with its evidence attached."""

    story_id: str
    artisan_id: str
    product_id: str
    template: NarrativeTemplate
    premise: str
    cultural_anchor: LedgerEntry
    beats: tuple[NarrativeBeat, ...]
    ledger: tuple[LedgerEntry, ...]
    language: str = "中文"
    source: GrowthOutputSource = GrowthOutputSource.DETERMINISTIC_DEMO
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        identity = (self.story_id, self.artisan_id, self.product_id, self.premise, self.language)
        if not all(value.strip() for value in identity):
            raise ValueError("story core requires stable identity, a premise, and a language")

        # The anchor is the thesis: a story hangs off one fact that can be checked.
        if self.cultural_anchor.use is not ClaimUse.GROUNDED:
            raise ValueError("the cultural anchor must be a grounded claim")
        if self.cultural_anchor.beat_id != ANCHOR_BEAT_ID:
            raise ValueError(f"the cultural anchor must use beat id {ANCHOR_BEAT_ID!r}")

        if not MIN_BEATS <= len(self.beats) <= MAX_BEATS:
            raise ValueError(f"a story core carries {MIN_BEATS}-{MAX_BEATS} beats")
        beat_ids = [beat.beat_id for beat in self.beats]
        if len(set(beat_ids)) != len(beat_ids):
            raise ValueError("beat ids must be unique")
        if [beat.ordinal for beat in self.beats] != list(range(1, len(self.beats) + 1)):
            raise ValueError("beat ordinals must run 1..n in order")

        if not self.ledger:
            raise ValueError("a story core requires at least one ledger entry")
        entry_ids = [self.cultural_anchor.entry_id, *(entry.entry_id for entry in self.ledger)]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("ledger entry ids must be unique, anchor included")
        orphans = sorted({entry.beat_id for entry in self.ledger} - set(beat_ids))
        if orphans:
            raise ValueError(f"ledger entries reference unknown beats: {', '.join(orphans)}")

    @property
    def beats_by_id(self) -> dict[str, NarrativeBeat]:
        return {beat.beat_id: beat for beat in self.beats}

    def entries_for(self, beat_id: str) -> tuple[LedgerEntry, ...]:
        """Every claim made in one beat, in ledger order."""
        return tuple(entry for entry in self.ledger if entry.beat_id == beat_id)

    @property
    def all_entries(self) -> tuple[LedgerEntry, ...]:
        """The anchor followed by the beat ledger — the full record for L2/L3/L4."""
        return (self.cultural_anchor, *self.ledger)

    @property
    def provenance_summary(self) -> ProvenanceSummary:
        counts = dict.fromkeys(ClaimUse, 0)
        sources: list[str] = []
        for entry in self.all_entries:
            counts[entry.use] += 1
            if entry.is_publicly_checkable and entry.source_url is not None:
                sources.append(entry.source_url)
        return ProvenanceSummary(
            grounded=counts[ClaimUse.GROUNDED],
            attributed=counts[ClaimUse.ATTRIBUTED],
            artistic=counts[ClaimUse.ARTISTIC],
            checkable_sources=tuple(sorted(set(sources))),
        )

    @property
    def grounded_field_names(self) -> frozenset[str]:
        """Fields this story states as fact — what an audit re-checks against."""
        return frozenset(
            entry.field_name
            for entry in self.all_entries
            if entry.use is ClaimUse.GROUNDED and entry.field_name is not None
        )


@dataclass(frozen=True, slots=True)
class StoryFactReference:
    """A verified fact made available to scenes and export adapters."""

    reference_id: str
    field_name: str
    display_value: str
    source_note: str
    source_url: str | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.VERIFIED

    def __post_init__(self) -> None:
        required = (self.reference_id, self.field_name, self.display_value, self.source_note)
        if not all(value.strip() for value in required):
            raise ValueError("story fact references require identity, value, and source note")
        if self.evidence_status is not EvidenceStatus.VERIFIED:
            raise ValueError("public story fact references must be verified")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("story fact source_url must be an HTTPS URL")


@dataclass(frozen=True, slots=True)
class StoryScene:
    """One timed vertical-video scene, ready for image/video provider adapters."""

    scene_id: str
    sequence: int
    duration_seconds: int
    kind: StorySceneKind
    title: str
    visual_description: str
    camera_direction: str
    voiceover: str
    on_screen_text: str
    image_prompt: str
    video_prompt: str
    fact_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.scene_id,
            self.title,
            self.visual_description,
            self.camera_direction,
            self.voiceover,
            self.on_screen_text,
            self.image_prompt,
            self.video_prompt,
        )
        if not all(value.strip() for value in required):
            raise ValueError("story scene is missing required production text")
        if self.sequence < 1 or self.duration_seconds < 1:
            raise ValueError("story scenes require positive sequence and duration")
        if len(set(self.fact_reference_ids)) != len(self.fact_reference_ids):
            raise ValueError("scene fact references must be unique")


@dataclass(frozen=True, slots=True)
class StoryScript:
    """A platform-specific script and storyboard with a closed evidence set."""

    script_id: str
    story_core: StoryCore
    title: str
    platform: StoryPlatform
    aspect_ratio: str
    target_duration_seconds: int
    scenes: tuple[StoryScene, ...]
    fact_references: tuple[StoryFactReference, ...]
    template_version: str = "story-v1"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        required = (self.script_id, self.title, self.aspect_ratio, self.template_version)
        if not all(value.strip() for value in required):
            raise ValueError("story script requires identity and export metadata")
        if self.target_duration_seconds < 1 or not self.scenes:
            raise ValueError("story script requires a positive target and at least one scene")
        if self.created_at.tzinfo is None:
            raise ValueError("story script created_at must include timezone")

        sequences = [scene.sequence for scene in self.scenes]
        if sequences != list(range(1, len(self.scenes) + 1)):
            raise ValueError("scene sequences must run 1..n in order")
        scene_ids = [scene.scene_id for scene in self.scenes]
        if len(set(scene_ids)) != len(scene_ids):
            raise ValueError("scene ids must be unique")
        if self.total_duration_seconds != self.target_duration_seconds:
            raise ValueError("scene durations must add up to the target duration")

        reference_ids = [reference.reference_id for reference in self.fact_references]
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("story fact reference ids must be unique")
        unknown = sorted(
            {
                reference_id
                for scene in self.scenes
                for reference_id in scene.fact_reference_ids
                if reference_id not in set(reference_ids)
            }
        )
        if unknown:
            raise ValueError(f"scenes reference unknown story facts: {', '.join(unknown)}")

    @property
    def total_duration_seconds(self) -> int:
        return sum(scene.duration_seconds for scene in self.scenes)

    @property
    def fact_references_by_id(self) -> dict[str, StoryFactReference]:
        return {reference.reference_id: reference for reference in self.fact_references}


@dataclass(frozen=True, slots=True)
class StoryReviewIssue:
    """One actionable finding produced by the Story Guardian."""

    scene_id: str
    issue_type: str
    reason: str
    recommended_action: str

    def __post_init__(self) -> None:
        required = (self.scene_id, self.issue_type, self.reason, self.recommended_action)
        if not all(value.strip() for value in required):
            raise ValueError("story review issue fields cannot be blank")


@dataclass(frozen=True, slots=True)
class StoryGuardianReview:
    """Automated, structured review that must pass before human approval."""

    approved: bool
    risk_level: GuardianRiskLevel
    issues: tuple[StoryReviewIssue, ...]
    reviewed_scene_ids: tuple[str, ...]
    verified_reference_ids: tuple[str, ...]
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.reviewed_at.tzinfo is None:
            raise ValueError("story review timestamp must include timezone")
        if self.approved and self.issues:
            raise ValueError("approved story review cannot contain issues")
        if not self.approved and not self.issues:
            raise ValueError("failed story review requires structured issues")


@dataclass(frozen=True, slots=True)
class StoryHumanDecision:
    """The accountable human decision stored after automated review."""

    decision: StoryDecision
    actor_id: str
    note: str
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("story decision requires an actor")
        if self.decided_at.tzinfo is None:
            raise ValueError("story decision timestamp must include timezone")


@dataclass(frozen=True, slots=True)
class StoryProject:
    """The reviewable unit shown in Story Studio and later sent to renderers."""

    project_id: str
    script: StoryScript
    guardian_review: StoryGuardianReview
    status: StoryProjectStatus
    human_decision: StoryHumanDecision | None = None
    revision_count: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.project_id.strip() or self.revision_count < 0:
            raise ValueError("story project requires identity and non-negative revision count")
        if self.updated_at.tzinfo is None:
            raise ValueError("story project timestamp must include timezone")
        if self.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL and (
            not self.guardian_review.approved or self.human_decision is not None
        ):
            raise ValueError("awaiting approval requires a clean Guardian review")
        if self.status is StoryProjectStatus.APPROVED and (
            not self.guardian_review.approved
            or self.human_decision is None
            or self.human_decision.decision is not StoryDecision.APPROVE
        ):
            raise ValueError("approved story requires Guardian and human approval")
        if self.status is StoryProjectStatus.REJECTED and (
            self.human_decision is None or self.human_decision.decision is not StoryDecision.REJECT
        ):
            raise ValueError("rejected story requires a human rejection")


__all__ = [
    "ANCHOR_BEAT_ID",
    "MAX_BEATS",
    "MIN_BEATS",
    "ClaimUse",
    "LedgerEntry",
    "LedgerFinding",
    "NarrativeBeat",
    "NarrativeTemplate",
    "ProvenanceSummary",
    "StoryCore",
    "StoryDecision",
    "StoryFactReference",
    "StoryGuardianReview",
    "StoryHumanDecision",
    "StoryPlatform",
    "StoryProject",
    "StoryProjectStatus",
    "StoryReviewIssue",
    "StoryScene",
    "StorySceneKind",
    "StoryScript",
]
