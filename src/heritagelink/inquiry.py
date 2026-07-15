"""Structured customization inquiry generation for one selected product."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from heritagelink.content import PENDING_ZH, BilingualContent
from heritagelink.models import GiftRequest, Recommendation

INQUIRY_DISCLAIMER_ZH = "请与商家确认最终方案。"
INQUIRY_DISCLAIMER_EN = "Please confirm the final proposal with the merchant."


@dataclass(frozen=True, slots=True)
class InquiryDetails:
    """Non-ranking customer details collected by the presentation layer."""

    customer_type: str
    customization_theme: str = ""
    inscription_text: str = ""
    packaging_requirement: str = ""
    destination: str = ""
    output_language: str = "中英双语"
    additional_notes: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "customer_type",
            "customization_theme",
            "inscription_text",
            "packaging_requirement",
            "destination",
            "output_language",
            "additional_notes",
        ):
            value = getattr(self, field_name)
            if len(value) > 500:
                raise ValueError(f"{field_name} 不能超过 500 个字符")


def _provided_or_pending(value: str) -> str:
    return value.strip() or PENDING_ZH


def _open_questions(request: GiftRequest, details: InquiryDetails) -> list[str]:
    questions = [
        "请确认产品当前是否可接单，并提供最终含税或未税报价。",
        "请确认真实材料、可生产数量及基础制作周期。",
    ]
    if request.customization_required:
        questions.append("请确认定制主题的可制作范围、费用和附加工期。")
        if not details.customization_theme.strip():
            questions.append("客户尚未明确定制主题，请协助确认主题方向。")
    if "inscription" in request.required_types or details.inscription_text.strip():
        questions.append("请确认题字内容、字体、位置及相关权利。")
        if not details.inscription_text.strip():
            questions.append("客户尚未提供题字文字，请确认最终文字。")
    if request.logo_required:
        questions.append("请确认 Logo 文件、使用授权、尺寸、颜色和放置位置。")
    if not details.packaging_requirement.strip():
        questions.append("客户尚未明确包装要求，请提供适用包装方案。")
    if details.destination.strip():
        questions.append("请确认目的地对应的包装、运输可达性、费用和合规要求。")
    else:
        questions.append("客户尚未提供目的国家或地区，请补充后评估运输。")
    if request.available_lead_days is None:
        questions.append("客户尚未提供交付期限，请确认期望交付日期。")
    else:
        questions.append(f"请确认能否在 {request.available_lead_days} 天内完成制作与交付。")
    return questions


def build_customization_inquiry(
    request: GiftRequest,
    recommendation: Recommendation,
    content: BilingualContent,
    details: InquiryDetails,
    *,
    inquiry_id: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build one complete JSON-ready inquiry without changing recommendation facts."""
    if content.product_id != recommendation.product.product_id:
        raise ValueError("双语内容与选中产品不一致")
    timestamp = created_at or datetime.now(UTC)
    generated_id = inquiry_id or f"inq_demo_{uuid4().hex[:12]}"
    theme = _provided_or_pending(details.customization_theme)
    inscription = _provided_or_pending(details.inscription_text)
    packaging = _provided_or_pending(details.packaging_requirement)
    destination = _provided_or_pending(details.destination)
    delivery = (
        f"{request.available_lead_days} 天内"
        if request.available_lead_days is not None
        else PENDING_ZH
    )

    inquiry: dict[str, Any] = {
        "schema_version": "1.0",
        "inquiry_id": generated_id,
        "created_at": timestamp.isoformat(),
        "is_demo": True,
        "disclaimer_zh": INQUIRY_DISCLAIMER_ZH,
        "disclaimer_en": INQUIRY_DISCLAIMER_EN,
        "customer_type": details.customer_type.strip() or PENDING_ZH,
        "output_language": details.output_language,
        "additional_notes": _provided_or_pending(details.additional_notes),
        "request_snapshot": {
            "request_id": request.request_id,
            "currency": "CNY",
            "unit_budget_min_fen": request.unit_budget_min_fen,
            "unit_budget_max_fen": request.unit_budget_max_fen,
            "budget_total_min_fen": request.unit_budget_min_fen * request.quantity,
            "budget_total_max_fen": request.unit_budget_max_fen * request.quantity,
            "quantity": request.quantity,
            "recipient_tags": sorted(request.recipient_tags),
            "occasion_tags": sorted(request.occasion_tags),
            "style_tags": sorted(request.style_tags),
            "meaning_tags": sorted(request.meaning_tags),
        },
        "customization_brief": {
            "required": request.customization_required,
            "required_types": sorted(request.required_types),
            "preferred_types": sorted(request.preferred_customization_types),
            "theme": theme,
            "inscription": inscription,
            "logo_required": request.logo_required,
            "logo_asset": PENDING_ZH if request.logo_required else "不需要",
            "packaging": packaging,
        },
        "delivery": {
            "destination": destination,
            "international_shipping_required": request.international_shipping_required,
            "available_lead_days": request.available_lead_days,
            "delivery_requirement": delivery,
        },
        "selected_products": [
            {
                "product_id": recommendation.product.product_id,
                "merchant_id": recommendation.product.merchant_id,
                "merchant_name_zh": recommendation.product.merchant_name_zh,
                "product_name_zh": recommendation.product.product_name_zh,
                "product_name_en": recommendation.product.product_name_en,
                "quantity": request.quantity,
                "quoted_price_min_fen": recommendation.product.price_min_fen,
                "quoted_price_max_fen": recommendation.product.price_max_fen,
                "score_at_selection": recommendation.total_score,
                "data_version": recommendation.product.data_version,
                "is_demo": recommendation.product.is_demo,
                "demo_disclaimer": recommendation.product.demo_disclaimer,
            }
        ],
        "merchant_action_items": [
            "核对需求单中的数量、预算、定制内容、目的地和交付期限。",
            "确认最终报价、材料、产能、工期、包装和运输条件。",
            "对中英文文化文案进行事实与表达审核。",
        ],
        "open_questions": _open_questions(request, details),
        "culture_copy": {
            "zh-CN": content.zh.text,
            "en": content.en.text,
            "pending_confirmations": list(content.pending_confirmations),
        },
    }
    validate_inquiry(inquiry)
    return inquiry


def validate_inquiry(inquiry: dict[str, Any]) -> None:
    """Fail fast if a generated inquiry is missing its MVP contract fields."""
    required = {
        "schema_version",
        "inquiry_id",
        "created_at",
        "is_demo",
        "disclaimer_zh",
        "disclaimer_en",
        "customer_type",
        "output_language",
        "request_snapshot",
        "customization_brief",
        "delivery",
        "selected_products",
        "merchant_action_items",
        "open_questions",
        "culture_copy",
    }
    missing = sorted(required - inquiry.keys())
    if missing:
        raise ValueError(f"定制需求单缺少字段：{', '.join(missing)}")
    if len(inquiry["selected_products"]) != 1:
        raise ValueError("MVP 定制需求单必须且只能包含一个选中产品")
    culture_copy = inquiry["culture_copy"]
    if not culture_copy.get("zh-CN") or not culture_copy.get("en"):
        raise ValueError("定制需求单必须包含中英文文化介绍")


def inquiry_to_json(inquiry: dict[str, Any]) -> str:
    """Serialize a validated inquiry as readable UTF-8 JSON text."""
    validate_inquiry(inquiry)
    return json.dumps(inquiry, ensure_ascii=False, indent=2)


def inquiry_details_as_dict(details: InquiryDetails) -> dict[str, str]:
    """Expose details for simple UI session-state serialization."""
    return asdict(details)
