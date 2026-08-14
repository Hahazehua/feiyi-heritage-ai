"""Grounded application-layer comparison of the current formal recommendations."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, cast

from heritagelink.catalog_eligibility import is_recommendation_eligible
from heritagelink.comparison_models import (
    ApplicationExecutionTrace,
    ApplicationTraceStatus,
    ComparisonDimension,
    ComparisonEvidence,
    EvidenceState,
    ExplanationSource,
    ProductComparisonItem,
    ProductComparisonRequest,
    ProductComparisonResult,
)
from heritagelink.models import DataBundle, Product, Recommendation
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.request_parser import ParsedCustomerRequest

if TYPE_CHECKING:
    from heritagelink.agent_models import CatalogSnapshot


class ProductComparisonError(ValueError):
    """Raised when a requested comparison cannot be grounded safely."""


class ComparisonExplanationClient(Protocol):
    """Optional narrative client; it receives only a sanitized structured view."""

    def explain_comparison(self, comparison: Mapping[str, object]) -> str: ...


ComparisonExplanationCallable = Callable[[Mapping[str, object]], str]
ComparisonExplanation = ComparisonExplanationClient | ComparisonExplanationCallable

_VERIFIED_COMMERCIAL_STATUSES = frozenset({"verified_merchant_fact", "public_listing_snapshot"})
_VERIFIED_CULTURAL_STATUSES = frozenset(
    {
        "verified_merchant_fact",
        "verified_public_cultural_fact",
        "public_listing_snapshot",
    }
)
_RECIPIENT_LABELS = {
    "business_partner": "商务伙伴",
    "institution": "机构",
    "employee": "员工",
    "elder": "长辈",
    "family": "家人",
    "friend": "朋友",
    "newlywed": "新人",
    "teacher": "教授或教师",
    "collector": "收藏者",
    "universal": "多类收礼人",
}
_SCENE_LABELS = {
    "business_gift": "商务礼赠",
    "commemoration": "纪念",
    "wedding": "婚礼",
    "anniversary": "周年",
    "housewarming": "乔迁",
    "birthday": "生日",
    "festival": "节庆",
    "graduation": "毕业",
    "appreciation": "答谢",
    "collection": "收藏",
    "exhibition": "展览",
    "universal": "多类场景",
}
_STYLE_LABELS = {
    "traditional": "传统文化感",
    "modern": "现代新中式",
    "minimal": "简约",
    "grand": "庄重大气",
    "elegant": "典雅",
    "festive": "喜庆",
    "warm": "温暖",
    "universal": "风格适配面较广",
}
_SYMBOLISM_LABELS = {
    "heritage": "文化传承",
    "prosperity": "繁荣",
    "blessing": "祝福",
    "harmony": "和谐",
    "longevity": "长寿",
    "resilience": "坚韧",
    "remembrance": "纪念",
    "gratitude": "感谢",
    "union": "相伴",
    "universal": "文化表达适配面较广",
}
_CUSTOMIZATION_LABELS = {
    "logo": "Logo",
    "inscription": "题字",
    "packaging": "包装",
    "pattern": "图案",
    "size": "尺寸",
    "color": "颜色",
    "other": "其他定制",
}
_DIMENSION_ALIASES = {
    "recipient": ComparisonDimension.RECIPIENT,
    "scene": ComparisonDimension.SCENE,
    "style": ComparisonDimension.STYLE,
    "culture": ComparisonDimension.CULTURE,
    "budget": ComparisonDimension.BUDGET,
    "customization": ComparisonDimension.CUSTOMIZATION,
    "practical": ComparisonDimension.PRACTICAL,
    "shipping": ComparisonDimension.PRACTICAL,
    "quantity": ComparisonDimension.PRACTICAL,
    "lead_time": ComparisonDimension.PRACTICAL,
}
_BEST_FOR_LABELS = {
    ComparisonDimension.RECIPIENT: "适合谁",
    ComparisonDimension.SCENE: "适用场景",
    ComparisonDimension.STYLE: "风格表达",
    ComparisonDimension.CULTURE: "文化表达",
    ComparisonDimension.BUDGET: "预算适配",
    ComparisonDimension.CUSTOMIZATION: "定制方向",
    ComparisonDimension.PRACTICAL: "实用考虑",
}
_UNKNOWN_FIELD_LABELS = {
    "price": "价格",
    "recipient": "收礼人适配",
    "scene": "场景适配",
    "style": "风格适配",
    "symbolism": "文化寓意",
    "quantity": "起订量与批量能力",
    "lead_time": "制作与交付时间",
    "portability": "便携性",
    "shipping": "国际运输能力",
}


class ProductComparisonService:
    """Explain differences without recalculating or replacing recommendation rank."""

    def __init__(
        self,
        explanation: ComparisonExplanation | None = None,
        *,
        explanation_client: ComparisonExplanation | None = None,
    ) -> None:
        if explanation is not None and explanation_client is not None:
            raise ValueError("explanation 和 explanation_client 只能提供一个")
        self._explanation = explanation_client or explanation

    def compare(
        self,
        request: ProductComparisonRequest,
        recommendation_result: ProgressiveRecommendationResult,
        context: RecommendationContext,
        catalog: CatalogSnapshot,
    ) -> ProductComparisonResult:
        """Compare one to three products from the current formal recommendation only."""
        recommendations = recommendation_result.response.recommendations
        if not recommendations:
            raise ProductComparisonError("当前没有可比较的正式推荐商品")

        requested_ids = (
            tuple(item.product.product_id for item in recommendations)
            if request.product_ids is None
            else request.product_ids
        )
        if not requested_ids:
            raise ProductComparisonError("至少需要一件当前推荐商品")
        if len(requested_ids) > 3:
            raise ProductComparisonError("一次最多比较三件商品")

        current_ids = tuple(item.product.product_id for item in recommendations)
        unknown_ids = set(requested_ids) - set(current_ids)
        if unknown_ids:
            raise ProductComparisonError("只能比较当前正式推荐结果中的商品")

        # Filter by the original response rather than the caller's order.  This is
        # the central guard against comparison becoming a second ranking system.
        selected = tuple(
            (rank, recommendation)
            for rank, recommendation in enumerate(recommendations, start=1)
            if recommendation.product.product_id in set(requested_ids)
        )
        if not selected:
            raise ProductComparisonError("至少需要一件当前推荐商品")

        products_by_id = {product.product_id: product for product in catalog.products}
        grounded: list[tuple[int, Recommendation, Product]] = []
        for rank, recommendation in selected:
            product_id = recommendation.product.product_id
            product = products_by_id.get(product_id)
            if product is None:
                raise ProductComparisonError("当前推荐商品缺少完整目录记录")
            if not is_recommendation_eligible(product):
                raise ProductComparisonError("非正式推荐商品不能进入商品比较")
            grounded.append((rank, recommendation, product))

        dimensions = _comparison_dimensions(request, context)
        items = tuple(
            _comparison_item(
                rank,
                recommendation,
                product,
                request,
                context,
                catalog.bundle,
            )
            for rank, recommendation, product in grounded
        )
        best_for = _best_for(items, dimensions)
        tradeoffs = _tradeoffs(items)
        recommended = items[0]
        reason = _recommendation_reason(recommended)
        deterministic = _deterministic_summary(items, reason)
        unknown = tuple(
            dict.fromkeys(
                f"{item.product_name}：{_unknown_field_label(field_name)}待确认"
                for item in items
                for field_name in item.unknown_fields
            )
        )
        result = ProductComparisonResult(
            compared_product_ids=tuple(item.product_id for item in items),
            comparison_dimensions=dimensions,
            items=items,
            best_for=best_for,
            tradeoffs=tradeoffs,
            recommendation_for_current_user=recommended.product_id,
            recommendation_reason=reason,
            unknown_or_unverified=unknown,
            deterministic_summary=deterministic,
            ai_explanation=None,
            explanation_source=ExplanationSource.DETERMINISTIC_FALLBACK,
            original_ranking_preserved=True,
            context_summary=_context_summary(request, context),
        )
        explanation = self._grounded_explanation(result)
        if explanation is None:
            return result
        return replace(
            result,
            ai_explanation=explanation,
            explanation_source=ExplanationSource.LLM,
        )

    def compare_with_trace(
        self,
        request: ProductComparisonRequest,
        recommendation_result: ProgressiveRecommendationResult,
        context: RecommendationContext,
        catalog: CatalogSnapshot,
    ) -> tuple[ProductComparisonResult, ApplicationExecutionTrace]:
        """Return the structured result plus a separate application trace."""
        started = perf_counter()
        result = self.compare(request, recommendation_result, context, catalog)
        duration_ms = max(0.0, round((perf_counter() - started) * 1000, 3))
        return result, build_application_trace(result, duration_ms=duration_ms)

    def _grounded_explanation(self, result: ProductComparisonResult) -> str | None:
        if self._explanation is None:
            return None
        structured = _explanation_context(result)
        try:
            if hasattr(self._explanation, "explain_comparison"):
                client = cast(ComparisonExplanationClient, self._explanation)
                raw = client.explain_comparison(structured)
            else:
                callback = cast(ComparisonExplanationCallable, self._explanation)
                raw = callback(structured)
        except Exception:
            return None
        return _validated_explanation(raw, result)


def build_application_trace(
    result: ProductComparisonResult,
    *,
    duration_ms: float = 0.0,
) -> ApplicationExecutionTrace:
    """Build a privacy-safe trace that remains separate from all seven Skills."""
    source = result.explanation_source
    status = (
        ApplicationTraceStatus.SUCCESS
        if source is ExplanationSource.LLM
        else ApplicationTraceStatus.FALLBACK
    )
    return ApplicationExecutionTrace(
        action_id="product_comparison",
        status=status,
        input_summary={
            "compared_product_count": len(result.items),
            "comparison_dimensions": tuple(
                dimension.value for dimension in result.comparison_dimensions
            ),
        },
        output_summary={
            "structured_comparison": "success",
            "narrative_source": source.value,
            "original_ranking_unchanged": result.original_ranking_preserved,
            "unknown_preserved": bool(result.unknown_or_unverified),
        },
        narrative_source=source,
        safety_checks=(
            "formal_recommendations_only",
            "no_new_comparison_score",
            "original_ranking_unchanged",
            "unknown_commercial_facts_preserved",
        ),
        duration_ms=duration_ms,
    )


def _comparison_dimensions(
    request: ProductComparisonRequest,
    context: RecommendationContext,
) -> tuple[ComparisonDimension, ...]:
    if request.comparison_dimensions:
        normalized = tuple(
            _DIMENSION_ALIASES.get(str(item), item)
            if not isinstance(item, ComparisonDimension)
            else item
            for item in request.comparison_dimensions
        )
        if any(not isinstance(item, ComparisonDimension) for item in normalized):
            raise ProductComparisonError("包含不支持的比较维度")
        return tuple(dict.fromkeys(cast(tuple[ComparisonDimension, ...], normalized)))

    parsed = context.effective_request
    recipient = request.focus_recipient or parsed.recipient
    scene = request.focus_scene or parsed.scene
    international = (
        request.focus_international
        if request.focus_international is not None
        else parsed.international_shipping_required
    )
    if recipient in {"teacher", "elder"}:
        return (
            ComparisonDimension.RECIPIENT,
            ComparisonDimension.CULTURE,
            ComparisonDimension.STYLE,
            ComparisonDimension.SCENE,
            ComparisonDimension.BUDGET,
            ComparisonDimension.CUSTOMIZATION,
            ComparisonDimension.PRACTICAL,
        )
    if recipient == "business_partner" or scene in {
        "business_gift",
        "anniversary",
        "commemoration",
    }:
        return (
            ComparisonDimension.RECIPIENT,
            ComparisonDimension.SCENE,
            ComparisonDimension.CUSTOMIZATION,
            ComparisonDimension.PRACTICAL,
            ComparisonDimension.BUDGET,
            ComparisonDimension.CULTURE,
            ComparisonDimension.STYLE,
        )
    if international is True:
        return (
            ComparisonDimension.RECIPIENT,
            ComparisonDimension.CULTURE,
            ComparisonDimension.PRACTICAL,
            ComparisonDimension.STYLE,
            ComparisonDimension.BUDGET,
            ComparisonDimension.CUSTOMIZATION,
            ComparisonDimension.SCENE,
        )
    return (
        ComparisonDimension.RECIPIENT,
        ComparisonDimension.SCENE,
        ComparisonDimension.STYLE,
        ComparisonDimension.CULTURE,
        ComparisonDimension.BUDGET,
        ComparisonDimension.CUSTOMIZATION,
        ComparisonDimension.PRACTICAL,
    )


def _comparison_item(
    rank: int,
    recommendation: Recommendation,
    product: Product,
    request: ProductComparisonRequest,
    context: RecommendationContext,
    bundle: DataBundle,
) -> ProductComparisonItem:
    parsed = context.effective_request
    cultural_verified = product.cultural_data_status in _VERIFIED_CULTURAL_STATUSES
    commercial_verified = product.commercial_data_status in _VERIFIED_COMMERCIAL_STATUSES
    recipient = _tag_evidence(
        requested=(request.focus_recipient or parsed.recipient,),
        offered=product.recipient_tags,
        labels=_RECIPIENT_LABELS,
        field_label="收礼人",
        verified=cultural_verified,
        source_field="recipient_tags",
    )
    scene = _tag_evidence(
        requested=(request.focus_scene or parsed.scene,),
        offered=product.occasion_tags,
        labels=_SCENE_LABELS,
        field_label="场景",
        verified=cultural_verified,
        source_field="occasion_tags",
    )
    styles = request.focus_styles or parsed.style_preferences
    style = _tag_evidence(
        requested=styles,
        offered=product.style_tags,
        labels=_STYLE_LABELS,
        field_label="风格",
        verified=cultural_verified,
        source_field="style_tags",
    )
    symbolism = request.focus_symbolism or parsed.symbolism_preferences
    culture = _tag_evidence(
        requested=symbolism,
        offered=product.meaning_tags,
        labels=_SYMBOLISM_LABELS,
        field_label="文化寓意",
        verified=cultural_verified,
        source_field="meaning_tags",
    )
    price_display, price = _price_evidence(product, parsed.budget_per_item)
    customization = _customization_evidence(product, bundle, request, parsed)
    quantity = _quantity_evidence(product, parsed.quantity, commercial_verified)
    lead_time = _lead_time_evidence(product, parsed.required_delivery_days, commercial_verified)
    portability = _portability_evidence(product)
    international = _international_evidence(product, commercial_verified)

    named_evidence: tuple[tuple[str, ComparisonEvidence], ...] = (
        ("price", price),
        ("recipient", recipient),
        ("scene", scene),
        ("style", style),
        ("symbolism", culture),
        ("quantity", quantity),
        ("lead_time", lead_time),
        ("portability", portability),
        ("shipping", international),
        *tuple(
            (f"customization.{index}", item) for index, item in enumerate(customization, start=1)
        ),
    )
    verified_fields = tuple(
        field_name
        for field_name, evidence in named_evidence
        if evidence.state in {EvidenceState.VERIFIED_YES, EvidenceState.VERIFIED_NO}
    )
    unknown_fields = tuple(
        field_name
        for field_name, evidence in named_evidence
        if evidence.state is EvidenceState.UNKNOWN
    )
    cultural_strengths = _cultural_strengths(product, style, culture)
    practical_strengths = _practical_strengths(quantity, lead_time, international)
    limitations = tuple(
        dict.fromkeys(
            evidence.display
            for _, evidence in named_evidence
            if evidence.state in {EvidenceState.VERIFIED_NO, EvidenceState.UNKNOWN}
        )
    )
    return ProductComparisonItem(
        product_id=product.product_id,
        product_name=product.product_name_zh,
        rank_position=rank,
        price_display=price_display,
        price_fit=price,
        recipient_fit=recipient,
        scene_fit=scene,
        style_fit=style,
        symbolism_fit=culture,
        customization_summary=customization,
        quantity_fit=quantity,
        lead_time_summary=lead_time,
        portability_summary=portability,
        international_relevance=international,
        cultural_strengths=cultural_strengths,
        practical_strengths=practical_strengths,
        limitations=limitations,
        verified_fields=verified_fields,
        unknown_fields=unknown_fields,
    )


def _tag_evidence(
    *,
    requested: Sequence[str | None],
    offered: frozenset[str],
    labels: Mapping[str, str],
    field_label: str,
    verified: bool,
    source_field: str,
) -> ComparisonEvidence:
    requested_values = tuple(item for item in requested if item)
    if not verified:
        return ComparisonEvidence(
            EvidenceState.UNKNOWN,
            f"{field_label}适配暂无可靠信息",
            (source_field, "cultural_data_status"),
        )
    if not requested_values:
        offered_labels = _labels(offered, labels)
        if not offered_labels:
            return ComparisonEvidence(
                EvidenceState.UNKNOWN,
                f"{field_label}适配暂无可靠信息",
                (source_field,),
            )
        return ComparisonEvidence(
            EvidenceState.VERIFIED_YES,
            f"目录{field_label}方向：{'、'.join(offered_labels)}",
            (source_field,),
        )
    matched = tuple(item for item in requested_values if item in offered)
    if matched:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_YES,
            f"匹配当前{field_label}：{'、'.join(_labels(matched, labels))}",
            (source_field,),
        )
    if "universal" in offered:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_YES,
            f"目录标注为通用{field_label}方向，仍需结合本次需求确认",
            (source_field,),
        )
    return ComparisonEvidence(
        EvidenceState.VERIFIED_NO,
        f"当前目录{field_label}标签未直接匹配",
        (source_field,),
    )


def _price_evidence(
    product: Product,
    budget_per_item: float | None,
) -> tuple[str, ComparisonEvidence]:
    price_range = _price_range(product.price_min_fen, product.price_max_fen)
    if product.commercial_data_status not in _VERIFIED_COMMERCIAL_STATUSES:
        display = f"{price_range}（演示区间，待确认）"
        return display, ComparisonEvidence(
            EvidenceState.UNKNOWN,
            "价格待确认",
            ("price_min_fen", "price_max_fen", "commercial_data_status"),
        )
    if budget_per_item is None:
        return price_range, ComparisonEvidence(
            EvidenceState.NOT_APPLICABLE,
            "本次未提供单件预算",
            ("price_min_fen", "price_max_fen"),
        )
    budget_fen = int(Decimal(str(budget_per_item)) * 100)
    if product.price_max_fen <= budget_fen:
        display = "预算内"
        state = EvidenceState.VERIFIED_YES
    elif product.price_min_fen <= budget_fen:
        display = "接近预算"
        state = EvidenceState.VERIFIED_YES
    else:
        display = "超出预算"
        state = EvidenceState.VERIFIED_NO
    return price_range, ComparisonEvidence(
        state,
        display,
        ("price_min_fen", "price_max_fen", "budget_per_item"),
    )


def _customization_evidence(
    product: Product,
    bundle: DataBundle,
    request: ProductComparisonRequest,
    parsed: ParsedCustomerRequest,
) -> tuple[ComparisonEvidence, ...]:
    rows = _customization_rows(bundle, product.product_id)
    requested = set(request.focus_customization or parsed.customization_types)
    if parsed.logo_required is True:
        requested.add("logo")
    evidence: list[ComparisonEvidence] = []
    found: set[str] = set()
    for row in rows:
        option = str(row.get("customization_type", "")).strip()
        if not option or option in found:
            continue
        found.add(option)
        label = _CUSTOMIZATION_LABELS.get(option, option)
        status = str(row.get("commercial_data_status", "")).strip()
        if status in _VERIFIED_COMMERCIAL_STATUSES:
            evidence.append(
                ComparisonEvidence(
                    EvidenceState.VERIFIED_YES,
                    f"已确认可评估{label}",
                    ("customization_options.csv", option),
                )
            )
        else:
            evidence.append(
                ComparisonEvidence(
                    EvidenceState.UNKNOWN,
                    f"{label}：目录提供演示方向，具体能力待确认",
                    ("customization_options.csv", "commercial_data_status", option),
                )
            )
    for option in sorted(requested - found):
        label = _CUSTOMIZATION_LABELS.get(option, option)
        evidence.append(
            ComparisonEvidence(
                EvidenceState.UNKNOWN,
                f"{label}：暂无可靠能力信息",
                ("customization_options.csv", option),
            )
        )
    if not evidence:
        evidence.append(
            ComparisonEvidence(
                EvidenceState.UNKNOWN,
                "定制能力暂无可靠信息",
                ("customization_options.csv",),
            )
        )
    return tuple(evidence)


def _quantity_evidence(
    product: Product,
    quantity: int | None,
    commercial_verified: bool,
) -> ComparisonEvidence:
    if not commercial_verified:
        return ComparisonEvidence(
            EvidenceState.UNKNOWN,
            "起订量与批量能力待确认",
            (
                "min_order_qty",
                "recommended_max_qty",
                "demo_max_order_qty",
                "commercial_data_status",
            ),
        )
    if quantity is None:
        return ComparisonEvidence(
            EvidenceState.NOT_APPLICABLE,
            "本次未提供采购数量",
            ("min_order_qty", "recommended_max_qty"),
        )
    if quantity < product.min_order_qty:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_NO,
            "低于已确认最低起订量",
            ("min_order_qty", "quantity"),
        )
    if product.demo_max_order_qty is not None and quantity > product.demo_max_order_qty:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_NO,
            "高于已确认采购上限",
            ("demo_max_order_qty", "quantity"),
        )
    if product.recommended_max_qty is None:
        return ComparisonEvidence(
            EvidenceState.UNKNOWN,
            "建议批量范围待确认",
            ("recommended_max_qty",),
        )
    return ComparisonEvidence(
        EvidenceState.VERIFIED_YES,
        "当前数量处于已确认采购范围",
        ("min_order_qty", "recommended_max_qty", "quantity"),
    )


def _lead_time_evidence(
    product: Product,
    required_days: int | None,
    commercial_verified: bool,
) -> ComparisonEvidence:
    if not commercial_verified:
        return ComparisonEvidence(
            EvidenceState.UNKNOWN,
            "制作与交付时间待确认",
            ("lead_time_days", "commercial_data_status"),
        )
    if required_days is None:
        return ComparisonEvidence(
            EvidenceState.NOT_APPLICABLE,
            "本次未提供交付期限",
            ("lead_time_days",),
        )
    if product.lead_time_days <= required_days:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_YES,
            "目录制作周期可覆盖当前期限，最终交付仍需确认",
            ("lead_time_days", "required_delivery_days"),
        )
    return ComparisonEvidence(
        EvidenceState.VERIFIED_NO,
        "目录制作周期不能覆盖当前期限",
        ("lead_time_days", "required_delivery_days"),
    )


def _portability_evidence(product: Product) -> ComparisonEvidence:
    if product.merchant_fact_status in _VERIFIED_COMMERCIAL_STATUSES and product.dimensions_text:
        display = f"目录尺寸为 {product.dimensions_text}；便携性仍待确认"
    else:
        display = "便携性暂无可靠信息"
    return ComparisonEvidence(
        EvidenceState.UNKNOWN,
        display,
        ("dimensions_text", "merchant_fact_status"),
    )


def _international_evidence(
    product: Product,
    commercial_verified: bool,
) -> ComparisonEvidence:
    if not commercial_verified:
        return ComparisonEvidence(
            EvidenceState.UNKNOWN,
            "国际运输能力暂无可靠信息",
            ("supports_international_shipping", "commercial_data_status"),
        )
    if product.supports_international_shipping:
        return ComparisonEvidence(
            EvidenceState.VERIFIED_YES,
            "已确认支持国际运输，具体路线与费用仍需确认",
            ("supports_international_shipping",),
        )
    return ComparisonEvidence(
        EvidenceState.VERIFIED_NO,
        "已确认不支持国际运输",
        ("supports_international_shipping",),
    )


def _customization_rows(bundle: DataBundle, product_id: str) -> list[Mapping[str, object]]:
    frame = bundle.customization_options
    if "product_id" not in frame.columns:
        return []
    rows = frame.loc[frame["product_id"] == product_id]
    if "enabled" in rows.columns:
        rows = rows.loc[rows["enabled"].map(_truthy)]
    return [cast(Mapping[str, object], row.to_dict()) for _, row in rows.iterrows()]


def _truthy(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _labels(values: Sequence[str] | frozenset[str], labels: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(labels.get(value, value) for value in sorted(set(values)))


def _price_range(min_fen: int, max_fen: int) -> str:
    minimum = _yuan(min_fen)
    maximum = _yuan(max_fen)
    return f"¥{minimum}" if min_fen == max_fen else f"¥{minimum}–{maximum}"


def _yuan(fen: int) -> str:
    value = Decimal(fen) / Decimal(100)
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _cultural_strengths(
    product: Product,
    style: ComparisonEvidence,
    symbolism: ComparisonEvidence,
) -> tuple[str, ...]:
    strengths: list[str] = []
    if style.state is EvidenceState.VERIFIED_YES:
        strengths.append(style.display)
    if symbolism.state is EvidenceState.VERIFIED_YES:
        strengths.append(symbolism.display)
    if not strengths and product.cultural_data_status in _VERIFIED_CULTURAL_STATUSES:
        labels = _labels(product.meaning_tags, _SYMBOLISM_LABELS)
        if labels:
            strengths.append(f"目录文化方向：{'、'.join(labels)}")
    return tuple(dict.fromkeys(strengths))


def _practical_strengths(
    quantity: ComparisonEvidence,
    lead_time: ComparisonEvidence,
    international: ComparisonEvidence,
) -> tuple[str, ...]:
    return tuple(
        evidence.display
        for evidence in (quantity, lead_time, international)
        if evidence.state is EvidenceState.VERIFIED_YES
    )


def _best_for(
    items: tuple[ProductComparisonItem, ...],
    dimensions: tuple[ComparisonDimension, ...],
) -> dict[str, str]:
    best: dict[str, str] = {"当前需求": items[0].product_id}
    evidence_for = {
        ComparisonDimension.RECIPIENT: lambda item: (item.recipient_fit,),
        ComparisonDimension.SCENE: lambda item: (item.scene_fit,),
        ComparisonDimension.STYLE: lambda item: (item.style_fit,),
        ComparisonDimension.CULTURE: lambda item: (item.symbolism_fit,),
        ComparisonDimension.BUDGET: lambda item: (item.price_fit,),
        ComparisonDimension.CUSTOMIZATION: lambda item: item.customization_summary,
        ComparisonDimension.PRACTICAL: lambda item: (
            item.quantity_fit,
            item.lead_time_summary,
            item.international_relevance,
        ),
    }
    for dimension in dimensions:
        for item in items:
            evidence = evidence_for[dimension](item)
            if any(value.state is EvidenceState.VERIFIED_YES for value in evidence):
                best[_BEST_FOR_LABELS[dimension]] = item.product_id
                break
    return best


def _unknown_field_label(field_name: str) -> str:
    if field_name.startswith("customization"):
        return "定制能力"
    return _UNKNOWN_FIELD_LABELS.get(field_name, field_name)


def _context_summary(
    request: ProductComparisonRequest,
    context: RecommendationContext,
) -> tuple[str, ...]:
    """Summarize only confirmed comparison inputs for the customer-facing explainer."""
    parsed = context.effective_request
    recipient = request.focus_recipient or parsed.recipient
    scene = request.focus_scene or parsed.scene
    styles = request.focus_styles or parsed.style_preferences
    symbolism = request.focus_symbolism or parsed.symbolism_preferences
    customization = request.focus_customization or parsed.customization_types
    rows: list[str] = []
    if recipient:
        rows.append(f"收礼人：{_RECIPIENT_LABELS.get(recipient, recipient)}")
    if scene:
        rows.append(f"场景：{_SCENE_LABELS.get(scene, scene)}")
    if parsed.budget_per_item is not None:
        rows.append(f"单件预算：约 ¥{parsed.budget_per_item:,.0f}")
    if parsed.quantity is not None:
        rows.append(f"数量：{parsed.quantity} 件")
    if styles:
        rows.append(f"风格：{'、'.join(_labels(styles, _STYLE_LABELS))}")
    if symbolism:
        rows.append(f"文化方向：{'、'.join(_labels(symbolism, _SYMBOLISM_LABELS))}")
    if customization or parsed.logo_required is True:
        values = set(customization)
        if parsed.logo_required is True:
            values.add("logo")
        rows.append(f"定制关注：{'、'.join(_labels(tuple(values), _CUSTOMIZATION_LABELS))}")
    if request.focus_international is True or parsed.international_shipping_required is True:
        rows.append("礼赠方向：海外或国际礼赠")
    return tuple(rows)


def _tradeoffs(items: tuple[ProductComparisonItem, ...]) -> tuple[str, ...]:
    if len(items) == 1:
        return ("当前只查看一件商品，因此仅展示它与当前需求的依据，不形成商品间优劣结论。",)
    tradeoffs: list[str] = []
    for item in items:
        strengths = (*item.cultural_strengths, *item.practical_strengths)
        if strengths:
            line = f"{item.product_name}：{strengths[0]}。"
        else:
            line = f"{item.product_name}：当前已确认的差异信息有限。"
        if item.unknown_fields:
            line += " 未验证的商业信息继续保持待确认。"
        tradeoffs.append(line)
    return tuple(tradeoffs)


def _recommendation_reason(item: ProductComparisonItem) -> str:
    strengths = (*item.cultural_strengths, *item.practical_strengths)
    if strengths:
        return f"它保持被比较商品中原正式推荐顺序最靠前，同时{strengths[0]}。"
    return "它保持被比较商品中原正式推荐顺序最靠前；当前比较没有创建新排名。"


def _deterministic_summary(
    items: tuple[ProductComparisonItem, ...],
    reason: str,
) -> str:
    first = items[0]
    if len(items) == 1:
        opening = f"当前仅查看{first.product_name}，因此不形成商品间优劣结论。"
    else:
        opening = f"就当前已确认的需求，我会先考虑{first.product_name}。"
    pending = any(item.unknown_fields for item in items)
    pending_note = " 价格、运输、交付或定制中的未验证信息仍保持待确认。" if pending else ""
    return f"{opening}{reason}{pending_note}"


def _explanation_context(result: ProductComparisonResult) -> Mapping[str, object]:
    return {
        "instruction": (
            "只解释这些结构化差异；不得添加价格、材料、认证、运输、交付、产能或定制事实。"
        ),
        "products": tuple(
            {
                "name": item.product_name,
                "recipient_fit": item.recipient_fit.display,
                "scene_fit": item.scene_fit.display,
                "style_fit": item.style_fit.display,
                "culture_fit": item.symbolism_fit.display,
                "price_fit": item.price_fit.display,
                "strengths": (*item.cultural_strengths, *item.practical_strengths),
                "limitations": item.limitations,
            }
            for item in result.items
        ),
        "current_choice": result.items[0].product_name,
        "tradeoffs": result.tradeoffs,
        "current_context": result.context_summary,
        "deterministic_summary": result.deterministic_summary,
    }


def _validated_explanation(
    value: object,
    result: ProductComparisonResult,
) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > 600 or "http" in text.lower():
        return None
    without_names = text
    for item in result.items:
        without_names = without_names.replace(item.product_name, "")
    if re.search(r"[0-9０-９]", without_names):
        return None
    if re.search(r"(?:prod|req|trace|heritage|mer)_[a-z0-9_]+", text, re.IGNORECASE):
        return None
    if re.search(
        r"第?[一二三四五六七八九十百千万]+(?:个|件|款|元|天|位|名|分|倍|成|者)",
        without_names,
    ):
        return None
    if re.search(r"认证|国家级|省级|大师|传承人|材质|制成|产能|现货|包邮", without_names):
        return None

    unknown = {field_name for item in result.items for field_name in item.unknown_fields}
    unsafe_patterns: list[str] = []
    if "price" in unknown:
        unsafe_patterns.append(r"更便宜|价格更低|更实惠|预算内|接近预算|超出预算")
    if "shipping" in unknown:
        unsafe_patterns.append(r"支持.{0,4}(?:国际|海外)运输|可以寄|可寄|不支持.{0,4}运输")
    if any(field.startswith("customization") for field in unknown):
        unsafe_patterns.append(r"(?:支持|不支持|可以).{0,6}(?:Logo|logo|题字|包装|定制)")
    if "lead_time" in unknown:
        unsafe_patterns.append(r"交期更短|交付更快|能够按时|可以按时")
    if "quantity" in unknown:
        unsafe_patterns.append(r"适合批量|适合大批量|批量能力")
    if "portability" in unknown:
        unsafe_patterns.append(r"便携|轻便|容易携带")
    if any(re.search(pattern, without_names) for pattern in unsafe_patterns):
        return None
    return text
