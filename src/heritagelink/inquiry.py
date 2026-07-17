"""Structured customization inquiry generation for one selected product."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from heritagelink.content import PENDING_ZH, BilingualContent
from heritagelink.models import GiftRequest, Recommendation

INQUIRY_DISCLAIMER_ZH = "MVP 演示需求单；价格、产能、交期、运输和定制可行性均需商家确认。"
INQUIRY_DISCLAIMER_EN = (
    "MVP demo inquiry; price, capacity, lead time, shipping, and customization "
    "feasibility require merchant confirmation."
)


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


@dataclass(frozen=True, slots=True)
class InquiryRequestContext:
    """Customer-stated facts used by an inquiry, preserving unknown values as null."""

    unit_budget_min_fen: int | None = None
    unit_budget_max_fen: int | None = None
    budget_total_min_fen: int | None = None
    budget_total_max_fen: int | None = None
    quantity: int | None = None
    recipient_tags: tuple[str, ...] = ()
    occasion_tags: tuple[str, ...] = ()
    style_tags: tuple[str, ...] = ()
    meaning_tags: tuple[str, ...] = ()
    customization_required: bool | None = None
    required_customization_types: tuple[str, ...] = ()
    preferred_customization_types: tuple[str, ...] = ()
    logo_required: bool | None = None
    international_shipping_required: bool | None = None
    available_lead_days: int | None = None

    def __post_init__(self) -> None:
        money_fields = (
            "unit_budget_min_fen",
            "unit_budget_max_fen",
            "budget_total_min_fen",
            "budget_total_max_fen",
        )
        for field_name in money_fields:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} 不能为负数")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity 必须大于 0 或为 null")
        if self.available_lead_days is not None and self.available_lead_days < 0:
            raise ValueError("available_lead_days 不能为负数")

    @classmethod
    def from_request(cls, request: GiftRequest) -> InquiryRequestContext:
        """Treat a normal GiftRequest as fully customer-confirmed for compatibility."""
        return cls(
            unit_budget_min_fen=request.unit_budget_min_fen,
            unit_budget_max_fen=request.unit_budget_max_fen,
            budget_total_min_fen=request.unit_budget_min_fen * request.quantity,
            budget_total_max_fen=request.unit_budget_max_fen * request.quantity,
            quantity=request.quantity,
            recipient_tags=tuple(sorted(request.recipient_tags)),
            occasion_tags=tuple(sorted(request.occasion_tags)),
            style_tags=tuple(sorted(request.style_tags)),
            meaning_tags=tuple(sorted(request.meaning_tags)),
            customization_required=request.customization_required,
            required_customization_types=tuple(sorted(request.required_types)),
            preferred_customization_types=tuple(sorted(request.preferred_customization_types)),
            logo_required=request.logo_required,
            international_shipping_required=request.international_shipping_required,
            available_lead_days=request.available_lead_days,
        )


def _provided_or_pending(value: str) -> str:
    return value.strip() or PENDING_ZH


def _open_questions(context: InquiryRequestContext, details: InquiryDetails) -> list[str]:
    questions = [
        "请确认产品当前是否可接单，并提供最终含税或未税报价。",
        "请确认真实材料、可生产数量及基础制作周期。",
    ]
    if context.unit_budget_max_fen is None:
        questions.append("客户尚未提供单件预算，请确认可接受的预算范围。")
    if context.quantity is None:
        questions.append("客户尚未提供采购数量，请确认目标数量。")
    if not context.recipient_tags:
        questions.append("客户尚未明确赠礼对象，请补充后确认适配方向。")
    if not context.occasion_tags:
        questions.append("客户尚未明确礼赠场景，请补充后确认适配方向。")
    if context.customization_required is None:
        questions.append("客户尚未说明是否需要定制，请确认定制需求。")
    elif context.customization_required:
        questions.append("请确认定制主题的可制作范围、费用和附加工期。")
        if not details.customization_theme.strip():
            questions.append("客户尚未明确定制主题，请协助确认主题方向。")
    if "inscription" in context.required_customization_types or details.inscription_text.strip():
        questions.append("请确认题字内容、字体、位置及相关权利。")
        if not details.inscription_text.strip():
            questions.append("客户尚未提供题字文字，请确认最终文字。")
    if context.logo_required is None:
        questions.append("客户尚未说明是否需要 Logo，请确认品牌定制要求。")
    elif context.logo_required:
        questions.append("请确认 Logo 文件、使用授权、尺寸、颜色和放置位置。")
    if not details.packaging_requirement.strip():
        questions.append("客户尚未明确包装要求，请提供适用包装方案。")
    if details.destination.strip():
        questions.append("请确认目的地对应的包装、运输可达性、费用和合规要求。")
    else:
        questions.append("客户尚未提供目的国家或地区，请补充后评估运输。")
    if context.international_shipping_required is None:
        questions.append("客户尚未说明是否需要国际运输，请确认运输范围。")
    if context.available_lead_days is None:
        questions.append("客户尚未提供交付期限，请确认期望交付日期。")
    else:
        questions.append(f"请确认能否在 {context.available_lead_days} 天内完成制作与交付。")
    return questions


def _pending_customer_fields(context: InquiryRequestContext) -> list[str]:
    values = {
        "unit_budget_max_fen": context.unit_budget_max_fen,
        "quantity": context.quantity,
        "recipient_tags": context.recipient_tags,
        "occasion_tags": context.occasion_tags,
        "customization_required": context.customization_required,
        "logo_required": context.logo_required,
        "international_shipping_required": context.international_shipping_required,
        "available_lead_days": context.available_lead_days,
    }
    return [name for name, value in values.items() if value is None or value == ()]


def build_customization_inquiry(
    request: GiftRequest,
    recommendation: Recommendation,
    content: BilingualContent,
    details: InquiryDetails,
    *,
    inquiry_id: str | None = None,
    created_at: datetime | None = None,
    customer_context: InquiryRequestContext | None = None,
) -> dict[str, Any]:
    """Build one complete JSON-ready inquiry without changing recommendation facts."""
    if content.product_id != recommendation.product.product_id:
        raise ValueError("双语内容与选中产品不一致")
    timestamp = created_at or datetime.now(UTC)
    generated_id = inquiry_id or f"inq_demo_{uuid4().hex[:12]}"
    context = customer_context or InquiryRequestContext.from_request(request)
    theme = _provided_or_pending(details.customization_theme)
    inscription = _provided_or_pending(details.inscription_text)
    packaging = _provided_or_pending(details.packaging_requirement)
    destination = _provided_or_pending(details.destination)
    delivery = (
        f"{context.available_lead_days} 天内"
        if context.available_lead_days is not None
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
            "unit_budget_min_fen": context.unit_budget_min_fen,
            "unit_budget_max_fen": context.unit_budget_max_fen,
            "budget_total_min_fen": context.budget_total_min_fen,
            "budget_total_max_fen": context.budget_total_max_fen,
            "quantity": context.quantity,
            "recipient_tags": list(context.recipient_tags),
            "occasion_tags": list(context.occasion_tags),
            "style_tags": list(context.style_tags),
            "meaning_tags": list(context.meaning_tags),
            "pending_fields": _pending_customer_fields(context),
        },
        "customization_brief": {
            "required": context.customization_required,
            "required_types": list(context.required_customization_types),
            "preferred_types": list(context.preferred_customization_types),
            "theme": theme,
            "inscription": inscription,
            "logo_required": context.logo_required,
            "logo_asset": (PENDING_ZH if context.logo_required is not False else "不需要"),
            "packaging": packaging,
        },
        "delivery": {
            "destination": destination,
            "international_shipping_required": context.international_shipping_required,
            "available_lead_days": context.available_lead_days,
            "delivery_requirement": delivery,
        },
        "selected_products": [
            {
                "product_id": recommendation.product.product_id,
                "merchant_id": recommendation.product.merchant_id,
                "merchant_name_zh": recommendation.product.merchant_name_zh,
                "product_name_zh": recommendation.product.product_name_zh,
                "product_name_en": recommendation.product.product_name_en,
                "quantity": context.quantity,
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
        "open_questions": _open_questions(context, details),
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
