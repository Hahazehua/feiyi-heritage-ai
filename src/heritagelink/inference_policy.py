"""Central allowlisted policy for inferring non-commercial soft preferences."""

from __future__ import annotations

from dataclasses import replace

from heritagelink.recommendation_context import (
    InferredPreference,
    RecommendationContext,
    is_provided,
    readonly_inferences,
)
from heritagelink.request_parser import REQUEST_FIELDS, ParsedCustomerRequest

INFERABLE_FIELDS = frozenset(
    {
        "style_preferences",
        "symbolism_preferences",
        "packaging_requirement",
        "output_language",
    }
)

FORBIDDEN_INFERENCE_FIELDS = frozenset(
    {
        "budget_type",
        "total_budget",
        "budget_per_item",
        "quantity",
        "customization_required",
        "customization_types",
        "logo_required",
        "destination",
        "international_shipping_required",
        "required_delivery_days",
    }
)


def build_recommendation_context(parsed: ParsedCustomerRequest) -> RecommendationContext:
    """Apply bounded scenario rules without changing product or commercial facts."""
    provided = frozenset(
        field_name
        for field_name in REQUEST_FIELDS
        if field_name not in parsed.uncertain_fields and is_provided(getattr(parsed, field_name))
    )
    inferred: dict[str, InferredPreference] = {}
    styles: list[str] = []
    meanings: list[str] = []
    reasons: list[str] = []

    if parsed.recipient == "business_partner" or parsed.scene in {
        "business_gift",
        "anniversary",
        "commemoration",
    }:
        styles.extend(("elegant", "grand"))
        meanings.extend(("heritage", "remembrance"))
        reasons.append("适合正式纪念与商务礼赠")
    if parsed.recipient in {"teacher", "elder"}:
        styles.extend(("elegant", "traditional"))
        meanings.extend(("heritage", "gratitude"))
        reasons.append("适合教授、教师或长辈的文化表达")
    if parsed.recipient == "newlywed" or parsed.scene == "wedding":
        styles.extend(("festive", "warm"))
        meanings.extend(("blessing", "union"))
        reasons.append("适合婚礼祝福与成双寓意")
    if parsed.international_shipping_required is True or parsed.customer_type == "overseas":
        styles.append("elegant")
        meanings.append("heritage")
        reasons.append("适合海外文化交流与介绍")

    styles = list(dict.fromkeys(styles))
    meanings = list(dict.fromkeys(meanings))
    changes: dict[str, object] = {}
    reason = "；".join(dict.fromkeys(reasons)) or "依据当前赠礼对象与场景选择通用文化方向"
    if not parsed.style_preferences and styles:
        value = tuple(styles)
        changes["style_preferences"] = value
        inferred["style_preferences"] = InferredPreference(
            "style_preferences", value, reason, 0.78, "local_scenario_policy"
        )
    if not parsed.symbolism_preferences and meanings:
        value = tuple(meanings)
        changes["symbolism_preferences"] = value
        inferred["symbolism_preferences"] = InferredPreference(
            "symbolism_preferences", value, reason, 0.76, "local_scenario_policy"
        )
    if not parsed.packaging_requirement and reasons:
        value = "与当前礼赠场景相符的稳妥包装方向"
        changes["packaging_requirement"] = value
        inferred["packaging_requirement"] = InferredPreference(
            "packaging_requirement", value, reason, 0.65, "local_scenario_policy"
        )
    if parsed.output_language is None and (
        parsed.international_shipping_required is True or parsed.customer_type == "overseas"
    ):
        changes["output_language"] = "bilingual"
        inferred["output_language"] = InferredPreference(
            "output_language",
            "bilingual",
            "海外礼赠通常需要便于介绍的中英文内容",
            0.82,
            "local_scenario_policy",
        )

    if set(changes) - INFERABLE_FIELDS:
        raise ValueError("推断策略尝试写入非软偏好字段")
    effective = replace(parsed, **changes)
    direction = _direction_summary(effective, inferred)
    return RecommendationContext(
        stated_request=parsed,
        effective_request=effective,
        user_provided_fields=provided,
        inferred_fields=readonly_inferences(inferred),
        direction_summary=direction,
    )


def _direction_summary(
    request: ParsedCustomerRequest, inferred: dict[str, InferredPreference]
) -> str:
    if not inferred:
        return "我会按照您已经确认的偏好进行匹配，您可以随时调整。"
    if request.recipient == "business_partner" or request.scene in {
        "business_gift",
        "anniversary",
    }:
        return "我会先按庄重、适合商务纪念与文化交流的方向为您匹配。"
    if request.recipient in {"teacher", "elder"}:
        return "我会先按典雅、有文化说明、不过度商业化的方向为您匹配。"
    if request.recipient == "newlywed" or request.scene == "wedding":
        return "我会先按喜庆、祝福与成双寓意的方向为您匹配。"
    return "我会先按文化辨识度较高、容易向收礼人介绍的方向为您匹配。"
