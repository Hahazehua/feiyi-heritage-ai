"""Concept-only customization brief for requests with no eligible catalog product."""

from __future__ import annotations

from typing import Any

from heritagelink.inquiry import InquiryDetails, InquiryRequestContext
from heritagelink.models import GiftRequest, RecommendationResponse

CONCEPT_DISCLAIMER = "该内容为系统整理的定制需求概念，不代表现有产品、正式报价、产能或交付承诺。"


def build_customization_concept(
    request: GiftRequest,
    details: InquiryDetails,
    response: RecommendationResponse,
    *,
    customer_context: InquiryRequestContext | None = None,
) -> dict[str, Any]:
    """Build a merchant-confirmation brief without inventing a catalog product."""
    if response.has_eligible_products:
        raise ValueError("存在合格现有产品时不生成无结果定制概念")
    context = customer_context or InquiryRequestContext.from_request(request)
    questions = [
        "请商家确认可承接的非遗品类、设计方向和工艺边界。",
        "请商家确认目标单价、数量、产能和正式报价。",
        "请商家确认定制内容、知识产权、包装和额外工期。",
        "请商家确认目的地运输可行性、费用和合规要求。",
    ]
    return {
        "schema_version": "1.0",
        "concept_type": "custom_heritage_gift_concept",
        "is_existing_product": False,
        "status": "概念方案，待商家确认",
        "disclaimer": CONCEPT_DISCLAIMER,
        "suggested_heritage_category": "待商家根据需求确认",
        "target_unit_budget_fen": context.unit_budget_max_fen,
        "quantity": context.quantity,
        "theme_direction": details.customization_theme.strip() or "待商家确认",
        "cultural_requirements": list(context.meaning_tags),
        "customization_types": list(context.required_customization_types),
        "customization_required": context.customization_required,
        "logo_required": context.logo_required,
        "requested_text": details.inscription_text.strip() or "待商家确认",
        "packaging_requirement": details.packaging_requirement.strip() or "待商家确认",
        "destination": details.destination.strip() or "待商家确认",
        "international_shipping_required": context.international_shipping_required,
        "required_delivery_days": context.available_lead_days,
        "additional_notes": details.additional_notes.strip() or "待商家确认",
        "catalog_conflicts": list(response.primary_conflicts),
        "possible_adjustments": list(response.adjustment_suggestions),
        "merchant_confirmation_questions": questions,
    }
