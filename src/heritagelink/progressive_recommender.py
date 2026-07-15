"""Progressive recommendation adapter built on the deterministic rule engine."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from types import MappingProxyType
from uuid import uuid4

from heritagelink.models import (
    FilterFailure,
    FilterReasonCode,
    GiftRequest,
    Product,
    Recommendation,
    RecommendationResponse,
)
from heritagelink.recommender import CONFLICT_LABELS, SUGGESTIONS, WEIGHTS, recommend
from heritagelink.request_parser import ParsedCustomerRequest


class RecommendationMode(StrEnum):
    EXPLORING = "exploring"
    GUIDED = "guided"
    CONSTRAINED = "constrained"


MODE_LABELS = {
    RecommendationMode.EXPLORING: "探索推荐",
    RecommendationMode.GUIDED: "引导推荐",
    RecommendationMode.CONSTRAINED: "约束推荐",
}

FIELD_LABELS = {
    "budget_per_item": "单件预算",
    "quantity": "采购数量",
    "recipient": "赠礼对象",
    "scene": "使用场景",
    "style_preferences": "风格偏好",
    "symbolism_preferences": "文化寓意",
    "customization_required": "定制要求",
    "required_delivery_days": "交付时间",
}

_COVERAGE_FIELDS = tuple(FIELD_LABELS)
DIMENSION_REQUEST_FIELDS = {
    "budget": "budget_per_item",
    "recipient": "recipient",
    "occasion": "scene",
    "style": "style_preferences",
    "cultural_meaning": "symbolism_preferences",
    "customization": "customization_required",
    "quantity": "quantity",
    "lead_time": "required_delivery_days",
}


@dataclass(frozen=True, slots=True)
class AlternativeRecommendation:
    recommendation: Recommendation
    conflicts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProgressiveRecommendationResult:
    mode: RecommendationMode
    information_coverage: float
    confidence_level: str
    known_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    participating_dimensions: tuple[str, ...]
    response: RecommendationResponse
    alternatives: tuple[AlternativeRecommendation, ...]
    request_by_product: Mapping[str, GiftRequest]


def recommend_progressively(
    products: tuple[Product, ...] | list[Product],
    parsed: ParsedCustomerRequest,
    *,
    limit: int = 3,
) -> ProgressiveRecommendationResult:
    """Recommend from available facts without treating unknown facts as mismatches."""
    if not 1 <= limit <= 3:
        raise ValueError("limit 必须在 1 到 3 之间")
    mode = recommendation_mode(parsed)
    known, missing = known_and_missing_fields(parsed)
    coverage = round(len(known) / len(_COVERAGE_FIELDS), 2)
    confidence = "低" if coverage < 0.4 else "中" if coverage < 0.75 else "高"

    recommendations: list[Recommendation] = []
    failures: list[FilterFailure] = []
    request_by_product: dict[str, GiftRequest] = {}
    products_by_id = {product.product_id: product for product in products}
    for product in products:
        proxy = _request_for_product(parsed, product)
        request_by_product[product.product_id] = proxy
        response = recommend([product], proxy, limit=1)
        if response.recommendations:
            recommendations.append(_normalize_score(response.recommendations[0], parsed))
        else:
            failures.extend(response.filter_failures)
    if any(item.total_score > 0 for item in recommendations):
        recommendations = [item for item in recommendations if item.total_score > 0]
    recommendations.sort(key=lambda item: (-item.total_score, item.product.product_id))

    conflicts, suggestions = _guidance(failures)
    response = RecommendationResponse(
        message="已生成当前推荐" if recommendations else "没有完全匹配产品",
        recommendations=tuple(recommendations[:limit]),
        filter_failures=tuple(failures),
        primary_conflicts=conflicts if not recommendations else (),
        adjustment_suggestions=suggestions if not recommendations else (),
    )
    alternatives = (
        _build_alternatives(products_by_id, failures, parsed, limit=limit)
        if not recommendations
        else ()
    )
    return ProgressiveRecommendationResult(
        mode=mode,
        information_coverage=coverage,
        confidence_level=confidence,
        known_fields=known,
        missing_fields=missing,
        participating_dimensions=participating_dimensions(parsed),
        response=response,
        alternatives=alternatives,
        request_by_product=MappingProxyType(request_by_product),
    )


def recommendation_mode(parsed: ParsedCustomerRequest) -> RecommendationMode:
    """Classify the current request using only facts the user actually supplied."""
    has_hard_constraint = any(
        (
            parsed.budget_per_item is not None,
            parsed.quantity is not None,
            parsed.required_delivery_days is not None,
            parsed.customization_required is True,
            parsed.logo_required is True,
            parsed.international_shipping_required is True,
        )
    )
    if has_hard_constraint:
        return RecommendationMode.CONSTRAINED
    if parsed.recipient or parsed.scene or parsed.style_preferences or parsed.symbolism_preferences:
        return RecommendationMode.GUIDED
    return RecommendationMode.EXPLORING


def known_and_missing_fields(
    parsed: ParsedCustomerRequest,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    known = tuple(
        field_name
        for field_name in _COVERAGE_FIELDS
        if not _is_missing(getattr(parsed, field_name))
    )
    missing = tuple(field_name for field_name in _COVERAGE_FIELDS if field_name not in known)
    return known, missing


def participating_dimensions(parsed: ParsedCustomerRequest) -> tuple[str, ...]:
    return tuple(
        dimension
        for dimension, field_name in DIMENSION_REQUEST_FIELDS.items()
        if not _is_missing(getattr(parsed, field_name))
    )


def _request_for_product(
    parsed: ParsedCustomerRequest,
    product: Product,
    *,
    ignore_hard_constraints: bool = False,
) -> GiftRequest:
    budget_is_hard = (
        parsed.budget_per_item is not None
        and "budget_per_item" not in parsed.uncertain_fields
        and not ignore_hard_constraints
    )
    quantity_is_hard = parsed.quantity is not None and not ignore_hard_constraints
    budget_fen = (
        int((Decimal(str(parsed.budget_per_item)) * 100).to_integral_value(rounding=ROUND_FLOOR))
        if budget_is_hard
        else product.price_max_fen
    )
    quantity = parsed.quantity if quantity_is_hard else product.min_order_qty
    assert quantity is not None
    return GiftRequest(
        request_id=f"req_progressive_{uuid4().hex[:12]}",
        unit_budget_max_fen=budget_fen,
        quantity=quantity,
        recipient_tags=frozenset({parsed.recipient}) if parsed.recipient else frozenset(),
        occasion_tags=frozenset({parsed.scene}) if parsed.scene else frozenset(),
        style_tags=frozenset(parsed.style_preferences),
        meaning_tags=frozenset(parsed.symbolism_preferences),
        customization_required=(
            bool(parsed.customization_required) if not ignore_hard_constraints else False
        ),
        required_customization_types=(
            frozenset(parsed.customization_types) - {"logo"}
            if not ignore_hard_constraints
            else frozenset()
        ),
        logo_required=bool(parsed.logo_required) if not ignore_hard_constraints else False,
        international_shipping_required=(
            bool(parsed.international_shipping_required) if not ignore_hard_constraints else False
        ),
        available_lead_days=(
            parsed.required_delivery_days if not ignore_hard_constraints else None
        ),
    )


def _normalize_score(
    recommendation: Recommendation,
    parsed: ParsedCustomerRequest,
) -> Recommendation:
    active_dimensions = participating_dimensions(parsed)
    if not active_dimensions:
        score = 50.0
    else:
        earned = sum(recommendation.score_breakdown[key].score for key in active_dimensions)
        possible = sum(WEIGHTS[key] for key in active_dimensions)
        score = round(earned / possible * 100, 2)
    return replace(recommendation, total_score=score)


def _guidance(
    failures: list[FilterFailure],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    counts = Counter(code for failure in failures for code in failure.reason_codes)
    ordered = sorted(counts, key=lambda code: (-counts[code], code.value))
    return (
        tuple(f"{CONFLICT_LABELS[code]}（影响 {counts[code]} 件产品）" for code in ordered),
        tuple(SUGGESTIONS[code] for code in ordered),
    )


def _build_alternatives(
    products_by_id: Mapping[str, Product],
    failures: list[FilterFailure],
    parsed: ParsedCustomerRequest,
    *,
    limit: int,
) -> tuple[AlternativeRecommendation, ...]:
    alternatives: list[AlternativeRecommendation] = []
    for failure in failures:
        if FilterReasonCode.INACTIVE_PRODUCT in failure.reason_codes:
            continue
        product = products_by_id[failure.product_id]
        broad_request = _request_for_product(parsed, product, ignore_hard_constraints=True)
        broad_response = recommend([product], broad_request, limit=1)
        if broad_response.recommendations:
            alternatives.append(
                AlternativeRecommendation(
                    recommendation=_normalize_score(broad_response.recommendations[0], parsed),
                    conflicts=failure.reasons,
                )
            )
    alternatives.sort(
        key=lambda item: (-item.recommendation.total_score, item.recommendation.product.product_id)
    )
    return tuple(alternatives[:limit])


def _is_missing(value: object) -> bool:
    return value is None or value == "" or value == () or value == []
