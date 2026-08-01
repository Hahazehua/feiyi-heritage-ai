"""Skill 5 wrapper: build the existing customization inquiry JSON."""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from heritagelink.content import BilingualContent
from heritagelink.inquiry import InquiryRequestContext, build_customization_inquiry
from heritagelink.models import GiftRequest, Recommendation
from heritagelink.request_parser import ParsedCustomerRequest, to_inquiry_details


def _yuan_to_fen(value: float) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_FLOOR))


def _request_context(parsed: ParsedCustomerRequest, request: GiftRequest) -> InquiryRequestContext:
    def known(name: str) -> bool:
        return name not in parsed.uncertain_fields

    budget = (
        _yuan_to_fen(parsed.budget_per_item)
        if parsed.budget_per_item is not None and known("budget_per_item")
        else None
    )
    total = (
        _yuan_to_fen(parsed.total_budget)
        if parsed.total_budget is not None and known("total_budget")
        else budget * parsed.quantity
        if budget is not None and parsed.quantity is not None and known("quantity")
        else None
    )
    return InquiryRequestContext(
        unit_budget_max_fen=budget,
        budget_total_max_fen=total,
        quantity=parsed.quantity if known("quantity") else None,
        recipient_tags=((parsed.recipient,) if parsed.recipient and known("recipient") else ()),
        occasion_tags=((parsed.scene,) if parsed.scene and known("scene") else ()),
        style_tags=parsed.style_preferences if known("style_preferences") else (),
        meaning_tags=parsed.symbolism_preferences if known("symbolism_preferences") else (),
        customization_required=(
            parsed.customization_required if known("customization_required") else None
        ),
        required_customization_types=(
            parsed.customization_types if known("customization_types") else ()
        ),
        logo_required=parsed.logo_required if known("logo_required") else None,
        international_shipping_required=(
            parsed.international_shipping_required
            if known("international_shipping_required")
            else None
        ),
        available_lead_days=(
            parsed.required_delivery_days if known("required_delivery_days") else None
        ),
    )


def execute(
    request: GiftRequest,
    recommendation: Recommendation,
    content: BilingualContent,
    parsed: ParsedCustomerRequest,
) -> dict[str, object]:
    return build_customization_inquiry(
        request,
        recommendation,
        content,
        to_inquiry_details(parsed),
        customer_context=_request_context(parsed, request),
    )
