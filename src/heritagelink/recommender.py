"""Deterministic hard filtering and explainable 100-point scoring."""

from __future__ import annotations

from collections import Counter
from math import ceil
from types import MappingProxyType

from heritagelink.models import (
    DimensionScore,
    FilterFailure,
    FilterReasonCode,
    GiftRequest,
    Product,
    ProductSummary,
    Recommendation,
    RecommendationResponse,
)

WEIGHTS = {
    "budget": 25,
    "recipient": 15,
    "occasion": 15,
    "style": 15,
    "cultural_meaning": 10,
    "customization": 10,
    "quantity": 5,
    "lead_time": 5,
}

CONFLICT_LABELS = {
    FilterReasonCode.INACTIVE_PRODUCT: "产品或关联商家当前未启用",
    FilterReasonCode.OVER_BUDGET: "产品最低单价超过绝对单件预算",
    FilterReasonCode.BELOW_MIN_ORDER: "采购数量低于最低起订量",
    FilterReasonCode.ABOVE_MAX_ORDER: "采购数量超过演示允许数量",
    FilterReasonCode.LEAD_TIME_INSUFFICIENT: "生产及定制周期无法满足交期",
    FilterReasonCode.CUSTOMIZATION_UNSUPPORTED: "必须定制但产品不支持定制",
    FilterReasonCode.CUSTOMIZATION_TYPE_UNSUPPORTED: "必需定制类型不受支持",
    FilterReasonCode.LOGO_UNSUPPORTED: "必须加入 Logo 但产品不支持 Logo 定制",
    FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED: ("海外运输为必要条件但产品不支持国际运输"),
}

SUGGESTIONS = {
    FilterReasonCode.OVER_BUDGET: "提高绝对单件预算，或选择更小规格/更简化的演示产品。",
    FilterReasonCode.BELOW_MIN_ORDER: "提高采购数量，或选择最低起订量更低的产品。",
    FilterReasonCode.ABOVE_MAX_ORDER: "降低数量、拆分批次，或请商家人工确认真实产能。",
    FilterReasonCode.LEAD_TIME_INSUFFICIENT: "延后交付日期，或减少会增加工期的定制要求。",
    FilterReasonCode.CUSTOMIZATION_UNSUPPORTED: "取消必须定制，或选择提供定制选项的产品。",
    FilterReasonCode.CUSTOMIZATION_TYPE_UNSUPPORTED: "调整必需定制类型，或改由商家人工评估。",
    FilterReasonCode.LOGO_UNSUPPORTED: "取消 Logo 必选条件，或选择支持 Logo 的产品。",
    FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED: (
        "改为境内交付，或选择标注支持国际运输的演示产品并向商家复核。"
    ),
    FilterReasonCode.INACTIVE_PRODUCT: "选择当前启用的产品。",
}


def _effective_lead_days(product: Product, request: GiftRequest) -> int:
    extra_days = [
        product.customization_extra_lead_days[option]
        for option in request.required_types
        if option in product.customization_extra_lead_days
    ]
    return product.lead_time_days + (max(extra_days) if extra_days else 0)


def _hard_filter(product: Product, request: GiftRequest) -> FilterFailure | None:
    codes: list[FilterReasonCode] = []
    reasons: list[str] = []

    def reject(code: FilterReasonCode, detail: str) -> None:
        codes.append(code)
        reasons.append(detail)

    if any(
        status != "active"
        for status in (product.status, product.merchant_status, product.heritage_status)
    ):
        reject(
            FilterReasonCode.INACTIVE_PRODUCT, CONFLICT_LABELS[FilterReasonCode.INACTIVE_PRODUCT]
        )
    if product.price_min_fen > request.unit_budget_max_fen:
        reject(
            FilterReasonCode.OVER_BUDGET,
            f"最低演示单价 {product.price_min_fen} 分超过预算上限 {request.unit_budget_max_fen} 分",
        )
    if request.quantity < product.min_order_qty:
        reject(
            FilterReasonCode.BELOW_MIN_ORDER,
            f"采购数量 {request.quantity} 低于演示最低起订量 {product.min_order_qty}",
        )
    if product.demo_max_order_qty is not None and request.quantity > product.demo_max_order_qty:
        reject(
            FilterReasonCode.ABOVE_MAX_ORDER,
            f"采购数量 {request.quantity} 超过演示允许数量 {product.demo_max_order_qty}",
        )

    if request.customization_required and not product.customization_options:
        reject(
            FilterReasonCode.CUSTOMIZATION_UNSUPPORTED,
            CONFLICT_LABELS[FilterReasonCode.CUSTOMIZATION_UNSUPPORTED],
        )
    unsupported_types = request.required_types - product.customization_options
    if request.logo_required and "logo" in unsupported_types:
        reject(
            FilterReasonCode.LOGO_UNSUPPORTED, CONFLICT_LABELS[FilterReasonCode.LOGO_UNSUPPORTED]
        )
        unsupported_types = unsupported_types - {"logo"}
    if unsupported_types:
        reject(
            FilterReasonCode.CUSTOMIZATION_TYPE_UNSUPPORTED,
            f"不支持必需定制类型：{', '.join(sorted(unsupported_types))}",
        )

    effective_lead_days = _effective_lead_days(product, request)
    if (
        request.available_lead_days is not None
        and request.available_lead_days < effective_lead_days
    ):
        reject(
            FilterReasonCode.LEAD_TIME_INSUFFICIENT,
            f"需要至少 {effective_lead_days} 天，但用户仅有 {request.available_lead_days} 天",
        )
    if request.international_shipping_required and not product.supports_international_shipping:
        reject(
            FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED,
            CONFLICT_LABELS[FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED],
        )

    if not codes:
        return None
    return FilterFailure(
        product_id=product.product_id,
        product_name_zh=product.product_name_zh,
        reason_codes=tuple(codes),
        reasons=tuple(reasons),
    )


def _dimension(score_ratio: float, key: str, explanation: str) -> DimensionScore:
    max_score = WEIGHTS[key]
    return DimensionScore(
        score=round(max(0.0, min(1.0, score_ratio)) * max_score, 2),
        max_score=max_score,
        explanation=explanation,
    )


def _budget_score(product: Product, request: GiftRequest) -> DimensionScore:
    lower = request.unit_budget_min_fen
    upper = request.unit_budget_max_fen
    if product.price_min_fen >= lower and product.price_max_fen <= upper:
        return _dimension(1.0, "budget", "产品演示价格区间完全落入用户单件预算区间。")
    if product.price_max_fen >= lower and product.price_min_fen <= upper:
        return _dimension(0.8, "budget", "产品演示价格区间与用户单件预算区间有交集。")
    return _dimension(0.5, "budget", "仅产品最低演示价格可承受，最终价格需商家确认。")


def _tag_score(
    requested: frozenset[str],
    offered: frozenset[str],
    key: str,
    label: str,
) -> tuple[DimensionScore, frozenset[str]]:
    if not requested:
        return _dimension(0.5, key, f"用户未指定{label}，本维度按中性分计算。"), frozenset()
    matched = requested & offered
    ratio = len(matched) / len(requested)
    if "universal" in offered:
        ratio = max(ratio, 0.5)
    if matched:
        explanation = f"匹配{label}标签：{', '.join(sorted(matched))}。"
    elif "universal" in offered:
        explanation = f"产品标记为通用{label}，但没有精确命中用户标签。"
    else:
        explanation = f"未命中用户选择的{label}标签。"
    return _dimension(ratio, key, explanation), matched


def _customization_score(product: Product, request: GiftRequest) -> DimensionScore:
    requested = request.required_types | request.preferred_customization_types
    if not request.customization_required and not requested:
        return _dimension(1.0, "customization", "用户没有定制要求，无定制能力冲突。")
    matched = requested & product.customization_options
    if requested and matched == requested:
        return _dimension(1.0, "customization", "产品支持全部必需和偏好定制类型。")
    if matched:
        return _dimension(0.5, "customization", "产品仅支持部分偏好定制类型。")
    if request.customization_required and product.customization_options:
        return _dimension(0.5, "customization", "产品支持定制，但具体方案需商家确认。")
    return _dimension(0.0, "customization", "未匹配用户的定制偏好。")


def _quantity_score(product: Product, request: GiftRequest) -> DimensionScore:
    if product.recommended_max_qty is None:
        return _dimension(0.5, "quantity", "没有演示建议产能上限，数量需商家确认。")
    if request.quantity <= product.recommended_max_qty:
        return _dimension(1.0, "quantity", "数量处于演示建议采购范围内。")
    return _dimension(0.5, "quantity", "数量超过演示建议范围，但未超过演示允许上限。")


def _lead_time_score(product: Product, request: GiftRequest) -> DimensionScore:
    effective_days = _effective_lead_days(product, request)
    if request.available_lead_days is None:
        return _dimension(0.5, "lead_time", "用户未提供交期，实际制作周期需商家确认。")
    if request.available_lead_days >= ceil(effective_days * 1.2):
        return _dimension(1.0, "lead_time", "交付时间相对演示制作周期至少有 20% 余量。")
    return _dimension(0.7, "lead_time", "演示制作周期可满足交期，但时间余量较小。")


def _score(product: Product, request: GiftRequest) -> Recommendation:
    recipient, recipient_matches = _tag_score(
        request.recipient_tags, product.recipient_tags, "recipient", "赠礼对象"
    )
    occasion, occasion_matches = _tag_score(
        request.occasion_tags, product.occasion_tags, "occasion", "使用场景"
    )
    style, style_matches = _tag_score(request.style_tags, product.style_tags, "style", "风格")
    meaning, meaning_matches = _tag_score(
        request.meaning_tags, product.meaning_tags, "cultural_meaning", "文化寓意"
    )
    dimensions = {
        "budget": _budget_score(product, request),
        "recipient": recipient,
        "occasion": occasion,
        "style": style,
        "cultural_meaning": meaning,
        "customization": _customization_score(product, request),
        "quantity": _quantity_score(product, request),
        "lead_time": _lead_time_score(product, request),
    }
    matched_tags = set().union(recipient_matches, occasion_matches, style_matches, meaning_matches)
    customization_matches = (
        request.required_types | request.preferred_customization_types
    ) & product.customization_options
    matched_tags.update(f"customization:{item}" for item in customization_matches)

    risks = [product.demo_disclaimer]
    if product.price_max_fen > request.unit_budget_max_fen:
        risks.append("产品价格区间上沿超过预算，最终规格和价格需商家确认。")
    if product.recommended_max_qty is None or (
        product.recommended_max_qty is not None and request.quantity > product.recommended_max_qty
    ):
        risks.append("批量产能仅为演示设定，需商家确认真实产能。")
    if request.available_lead_days is None:
        risks.append("用户未提供交期，制作与交付时间待商家确认。")
    if request.customization_required or request.required_types:
        risks.append("定制范围、费用和附加工期需商家确认。")
    if request.international_shipping_required:
        risks.append("国际运输支持仅为演示字段，实际可达性、费用和合规要求待确认。")
    if "draft" in product.content_review_statuses:
        risks.append("中英文文化文案为演示草稿，待商家审核。")

    summary = ProductSummary(
        product_id=product.product_id,
        merchant_id=product.merchant_id,
        merchant_name_zh=product.merchant_name_zh,
        heritage_id=product.heritage_id,
        sku=product.sku,
        product_name_zh=product.product_name_zh,
        product_name_en=product.product_name_en,
        price_min_fen=product.price_min_fen,
        price_max_fen=product.price_max_fen,
        min_order_qty=product.min_order_qty,
        demo_max_order_qty=product.demo_max_order_qty,
        lead_time_days=product.lead_time_days,
        dimensions_text=product.dimensions_text,
        material_text=product.material_text,
        image_path=product.image_path,
        image_alt_zh=product.image_alt_zh,
        reference_source_url=product.reference_source_url,
        image_license=product.image_license,
        supports_international_shipping=product.supports_international_shipping,
        shipping_note=product.shipping_note,
        data_version=product.data_version,
        is_demo=product.is_demo,
        demo_disclaimer=product.demo_disclaimer,
    )
    return Recommendation(
        total_score=round(sum(item.score for item in dimensions.values()), 2),
        score_breakdown=MappingProxyType(dimensions),
        matched_tags=tuple(sorted(matched_tags)),
        risks=tuple(risks),
        product=summary,
    )


def _no_result_guidance(
    failures: list[FilterFailure],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    counts = Counter(code for failure in failures for code in failure.reason_codes)
    ordered = sorted(counts, key=lambda code: (-counts[code], code.value))
    conflicts = tuple(f"{CONFLICT_LABELS[code]}（影响 {counts[code]} 件产品）" for code in ordered)
    suggestions = tuple(SUGGESTIONS[code] for code in ordered)
    return conflicts, suggestions


def recommend(
    products: tuple[Product, ...] | list[Product],
    request: GiftRequest,
    *,
    limit: int = 3,
) -> RecommendationResponse:
    """Filter, score and return at most three stable recommendations."""
    if not 1 <= limit <= 3:
        raise ValueError("limit 必须在 1 到 3 之间")

    failures: list[FilterFailure] = []
    eligible: list[Product] = []
    for product in products:
        failure = _hard_filter(product, request)
        if failure is None:
            eligible.append(product)
        else:
            failures.append(failure)

    scored = [_score(product, request) for product in eligible]
    scored.sort(key=lambda item: (-item.total_score, item.product.product_id))
    if scored:
        conflicts: tuple[str, ...] = ()
        suggestions: tuple[str, ...] = ()
    else:
        conflicts, suggestions = _no_result_guidance(failures)
    return RecommendationResponse(
        message="已找到合格产品" if scored else "没有合格产品",
        recommendations=tuple(scored[:limit]),
        filter_failures=tuple(failures),
        primary_conflicts=conflicts,
        adjustment_suggestions=suggestions,
    )
