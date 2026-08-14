"""Typed application-layer contracts for grounded product comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class EvidenceState(StrEnum):
    """Four-state evidence model; missing data is never treated as a negative fact."""

    VERIFIED_YES = "verified_yes"
    VERIFIED_NO = "verified_no"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ComparisonDimension(StrEnum):
    """Customer-facing dimensions supported by the comparison service."""

    RECIPIENT = "recipient"
    SCENE = "scene"
    STYLE = "style"
    CULTURE = "culture"
    BUDGET = "budget"
    CUSTOMIZATION = "customization"
    PRACTICAL = "practical"


class ExplanationSource(StrEnum):
    """Source used for the optional customer-facing comparison narrative."""

    LLM = "llm"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class ApplicationTraceStatus(StrEnum):
    """Status for an application action, deliberately separate from Skill status."""

    SUCCESS = "success"
    FALLBACK = "fallback"
    BLOCKED = "blocked"
    FAILED_SAFE = "failed_safe"


def _readonly_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class ComparisonEvidence:
    """One displayable fact together with its verification state and provenance."""

    state: EvidenceState
    display: str
    source_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.display.strip():
            raise ValueError("comparison evidence display 不能为空")
        if any(not field_name.strip() for field_name in self.source_fields):
            raise ValueError("comparison evidence source_fields 不能包含空值")


@dataclass(frozen=True, slots=True)
class ProductComparisonRequest:
    """Normalized comparison scope; ``None`` product IDs means all current results."""

    product_ids: tuple[str, ...] | None = None
    comparison_dimensions: tuple[ComparisonDimension, ...] = ()
    focus_recipient: str | None = None
    focus_scene: str | None = None
    focus_styles: tuple[str, ...] = ()
    focus_symbolism: tuple[str, ...] = ()
    focus_customization: tuple[str, ...] = ()
    focus_international: bool | None = None

    def __post_init__(self) -> None:
        if self.product_ids is not None:
            if not self.product_ids:
                raise ValueError("显式比较范围不能是空集合")
            if len(self.product_ids) > 3:
                raise ValueError("一次最多比较三件商品")
            if any(not product_id.strip() for product_id in self.product_ids):
                raise ValueError("product_ids 不能包含空值")
            if len(set(self.product_ids)) != len(self.product_ids):
                raise ValueError("product_ids 不能重复")
        if len(set(self.comparison_dimensions)) != len(self.comparison_dimensions):
            raise ValueError("comparison_dimensions 不能重复")
        for field_name, value in (
            ("focus_recipient", self.focus_recipient),
            ("focus_scene", self.focus_scene),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} 不能是空字符串")
        for field_name, values in (
            ("focus_styles", self.focus_styles),
            ("focus_symbolism", self.focus_symbolism),
            ("focus_customization", self.focus_customization),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} 不能包含空字符串")
        if self.focus_international is not None and type(self.focus_international) is not bool:
            raise ValueError("focus_international 必须是布尔值或 null")


@dataclass(frozen=True, slots=True)
class ProductComparisonItem:
    """Grounded comparison view for one product in its original recommendation rank."""

    product_id: str
    product_name: str
    rank_position: int
    price_display: str | None
    price_fit: ComparisonEvidence
    recipient_fit: ComparisonEvidence
    scene_fit: ComparisonEvidence
    style_fit: ComparisonEvidence
    symbolism_fit: ComparisonEvidence
    customization_summary: tuple[ComparisonEvidence, ...]
    quantity_fit: ComparisonEvidence
    lead_time_summary: ComparisonEvidence
    portability_summary: ComparisonEvidence
    international_relevance: ComparisonEvidence
    cultural_strengths: tuple[str, ...]
    practical_strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    verified_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.product_id.strip() or not self.product_name.strip():
            raise ValueError("comparison item 的产品 ID 和名称不能为空")
        if self.rank_position < 1:
            raise ValueError("rank_position 必须从 1 开始")
        if len(set(self.verified_fields)) != len(self.verified_fields):
            raise ValueError("verified_fields 不能重复")
        if len(set(self.unknown_fields)) != len(self.unknown_fields):
            raise ValueError("unknown_fields 不能重复")


@dataclass(frozen=True, slots=True)
class ProductComparisonResult:
    """Structured comparison result that never replaces the formal recommendation rank."""

    compared_product_ids: tuple[str, ...]
    comparison_dimensions: tuple[ComparisonDimension, ...]
    items: tuple[ProductComparisonItem, ...]
    best_for: Mapping[str, str]
    tradeoffs: tuple[str, ...]
    recommendation_for_current_user: str | None
    recommendation_reason: str | None
    unknown_or_unverified: tuple[str, ...]
    deterministic_summary: str
    ai_explanation: str | None
    explanation_source: ExplanationSource
    original_ranking_preserved: bool = True
    context_summary: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.items or len(self.items) > 3:
            raise ValueError("comparison result 必须包含一至三件商品")
        item_ids = tuple(item.product_id for item in self.items)
        if self.compared_product_ids != item_ids:
            raise ValueError("compared_product_ids 必须与 items 的顺序一致")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("comparison result 不能包含重复商品")
        if not self.comparison_dimensions:
            raise ValueError("comparison result 必须包含至少一个比较维度")
        if not self.deterministic_summary.strip():
            raise ValueError("deterministic_summary 不能为空")
        if any(not item.strip() for item in self.context_summary):
            raise ValueError("context_summary 不能包含空值")
        if self.recommendation_for_current_user not in {None, *item_ids}:
            raise ValueError("recommendation_for_current_user 必须来自被比较商品")
        unknown_best_for = set(self.best_for.values()) - set(item_ids)
        if unknown_best_for:
            raise ValueError("best_for 只能引用被比较商品")
        if self.explanation_source is ExplanationSource.LLM and not self.ai_explanation:
            raise ValueError("LLM explanation source 必须包含 ai_explanation")
        if (
            self.explanation_source is ExplanationSource.DETERMINISTIC_FALLBACK
            and self.ai_explanation is not None
        ):
            raise ValueError("deterministic fallback 不应包含 ai_explanation")
        object.__setattr__(self, "best_for", _readonly_mapping(self.best_for))

    @property
    def customer_summary(self) -> str:
        """Return the optional grounded narrative or the deterministic fallback."""
        return self.ai_explanation or self.deterministic_summary


@dataclass(frozen=True, slots=True)
class ApplicationExecutionTrace:
    """Review-only trace for an application action, never a pseudo eighth Skill."""

    action_id: str
    status: ApplicationTraceStatus
    input_summary: Mapping[str, object] = field(default_factory=dict)
    output_summary: Mapping[str, object] = field(default_factory=dict)
    narrative_source: ExplanationSource = ExplanationSource.DETERMINISTIC_FALLBACK
    safety_checks: tuple[str, ...] = ()
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("application trace action_id 不能为空")
        if self.duration_ms < 0:
            raise ValueError("application trace duration_ms 不能为负数")
        if any(not check.strip() for check in self.safety_checks):
            raise ValueError("application trace safety_checks 不能包含空值")
        object.__setattr__(self, "input_summary", _readonly_mapping(self.input_summary))
        object.__setattr__(self, "output_summary", _readonly_mapping(self.output_summary))
