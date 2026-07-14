"""Typed domain models shared by the data and recommendation layers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

import pandas as pd

DEMO_DISCLAIMER = "仅用于MVP演示，不代表飞颐铁画的真实价格、产能、材料、交期或商业承诺。"
MVP_DISCLAIMER_PREFIX = "仅用于MVP演示"


class FilterReasonCode(StrEnum):
    """Stable machine-readable hard-filter reason codes."""

    INACTIVE_PRODUCT = "inactive_product"
    OVER_BUDGET = "over_budget"
    BELOW_MIN_ORDER = "below_min_order"
    ABOVE_MAX_ORDER = "above_max_order"
    LEAD_TIME_INSUFFICIENT = "lead_time_insufficient"
    CUSTOMIZATION_UNSUPPORTED = "customization_unsupported"
    CUSTOMIZATION_TYPE_UNSUPPORTED = "customization_type_unsupported"
    LOGO_UNSUPPORTED = "logo_unsupported"
    INTERNATIONAL_SHIPPING_UNSUPPORTED = "international_shipping_unsupported"


@dataclass(frozen=True, slots=True)
class GiftRequest:
    """Normalized customer need accepted by the recommendation engine."""

    request_id: str
    unit_budget_max_fen: int
    quantity: int
    unit_budget_min_fen: int = 0
    recipient_tags: frozenset[str] = field(default_factory=frozenset)
    occasion_tags: frozenset[str] = field(default_factory=frozenset)
    style_tags: frozenset[str] = field(default_factory=frozenset)
    meaning_tags: frozenset[str] = field(default_factory=frozenset)
    customization_required: bool = False
    required_customization_types: frozenset[str] = field(default_factory=frozenset)
    preferred_customization_types: frozenset[str] = field(default_factory=frozenset)
    logo_required: bool = False
    international_shipping_required: bool = False
    available_lead_days: int | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id 不能为空")
        if self.unit_budget_min_fen < 0 or self.unit_budget_max_fen < 0:
            raise ValueError("预算金额不能为负数")
        if self.unit_budget_min_fen > self.unit_budget_max_fen:
            raise ValueError("单件预算下限不能高于上限")
        if self.quantity <= 0:
            raise ValueError("采购数量必须大于 0")
        if self.available_lead_days is not None and self.available_lead_days < 0:
            raise ValueError("可用交付天数不能为负数")

    @property
    def required_types(self) -> frozenset[str]:
        """Return all required customization types, including explicit Logo need."""
        if self.logo_required:
            return self.required_customization_types | {"logo"}
        return self.required_customization_types


@dataclass(frozen=True, slots=True)
class Product:
    """Validated product record enriched with merchant and customization data."""

    product_id: str
    merchant_id: str
    merchant_name_zh: str
    heritage_id: str
    sku: str
    product_name_zh: str
    product_name_en: str
    price_min_fen: int
    price_max_fen: int
    min_order_qty: int
    recommended_max_qty: int | None
    demo_max_order_qty: int | None
    lead_time_days: int
    dimensions_text: str
    material_text: str
    recipient_tags: frozenset[str]
    occasion_tags: frozenset[str]
    style_tags: frozenset[str]
    meaning_tags: frozenset[str]
    supports_international_shipping: bool
    shipping_note: str
    status: str
    merchant_status: str
    heritage_status: str
    data_version: str
    is_demo: bool
    demo_disclaimer: str
    customization_options: frozenset[str]
    customization_extra_lead_days: Mapping[str, int]
    content_review_statuses: frozenset[str]


@dataclass(frozen=True, slots=True)
class DataBundle:
    """Validated source tables."""

    merchants: pd.DataFrame
    heritage_items: pd.DataFrame
    products: pd.DataFrame
    product_texts: pd.DataFrame
    customization_options: pd.DataFrame


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """A weighted score and its user-facing explanation."""

    score: float
    max_score: int
    explanation: str


@dataclass(frozen=True, slots=True)
class ProductSummary:
    """Safe product information returned to a future UI."""

    product_id: str
    merchant_id: str
    merchant_name_zh: str
    heritage_id: str
    sku: str
    product_name_zh: str
    product_name_en: str
    price_min_fen: int
    price_max_fen: int
    min_order_qty: int
    demo_max_order_qty: int | None
    lead_time_days: int
    dimensions_text: str
    material_text: str
    supports_international_shipping: bool
    shipping_note: str
    data_version: str
    is_demo: bool
    demo_disclaimer: str


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One eligible, scored and explainable recommendation."""

    total_score: float
    score_breakdown: Mapping[str, DimensionScore]
    matched_tags: tuple[str, ...]
    risks: tuple[str, ...]
    product: ProductSummary


@dataclass(frozen=True, slots=True)
class FilterFailure:
    """All hard-filter failures recorded for one product."""

    product_id: str
    product_name_zh: str
    reason_codes: tuple[FilterReasonCode, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecommendationResponse:
    """Complete deterministic engine response, including no-result guidance."""

    message: str
    recommendations: tuple[Recommendation, ...]
    filter_failures: tuple[FilterFailure, ...]
    primary_conflicts: tuple[str, ...]
    adjustment_suggestions: tuple[str, ...]

    @property
    def has_eligible_products(self) -> bool:
        return bool(self.recommendations)


def readonly_mapping(values: dict[str, int]) -> Mapping[str, int]:
    """Protect enrichment mappings held by frozen dataclasses."""
    return MappingProxyType(dict(values))
