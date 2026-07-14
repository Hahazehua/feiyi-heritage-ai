from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from heritagelink.content import PENDING_ZH, generate_bilingual_content
from heritagelink.data_loader import build_products, load_data
from heritagelink.inquiry import (
    InquiryDetails,
    build_customization_inquiry,
    inquiry_to_json,
)
from heritagelink.models import GiftRequest
from heritagelink.recommender import recommend

ROOT = Path(__file__).parents[1]


def _selected_result() -> tuple[object, object, object]:
    bundle = load_data(ROOT / "data" / "demo")
    products = build_products(bundle)
    request = GiftRequest(
        request_id="req_inquiry_test",
        unit_budget_max_fen=130000,
        quantity=10,
        recipient_tags=frozenset({"business_partner"}),
        occasion_tags=frozenset({"business_gift"}),
        style_tags=frozenset({"elegant"}),
        meaning_tags=frozenset({"heritage"}),
        customization_required=True,
        required_customization_types=frozenset({"inscription"}),
        preferred_customization_types=frozenset({"packaging"}),
        logo_required=True,
        available_lead_days=45,
    )
    recommendation = recommend(products, request).recommendations[0]
    content = generate_bilingual_content(recommendation.product, bundle.product_texts)
    return request, recommendation, content


def test_customization_inquiry_contains_complete_business_fields() -> None:
    request, recommendation, content = _selected_result()
    details = InquiryDetails(
        customer_type="企业客户",
        customization_theme="企业周年纪念",
        inscription_text="携手同行",
        packaging_requirement="商务礼盒",
        destination="中国上海",
        output_language="中英双语",
    )

    inquiry = build_customization_inquiry(
        request,  # type: ignore[arg-type]
        recommendation,  # type: ignore[arg-type]
        content,  # type: ignore[arg-type]
        details,
        inquiry_id="inq_demo_test",
        created_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert inquiry["request_snapshot"]["quantity"] == 10
    assert inquiry["request_snapshot"]["unit_budget_max_fen"] == 130000
    assert inquiry["customization_brief"]["theme"] == "企业周年纪念"
    assert inquiry["customization_brief"]["inscription"] == "携手同行"
    assert inquiry["customization_brief"]["logo_required"] is True
    assert inquiry["customization_brief"]["packaging"] == "商务礼盒"
    assert inquiry["delivery"]["destination"] == "中国上海"
    assert inquiry["delivery"]["available_lead_days"] == 45
    assert len(inquiry["selected_products"]) == 1
    assert inquiry["culture_copy"]["zh-CN"]
    assert inquiry["culture_copy"]["en"]
    assert json.loads(inquiry_to_json(inquiry))["inquiry_id"] == "inq_demo_test"


def test_missing_inquiry_information_is_marked_and_questioned() -> None:
    request, recommendation, content = _selected_result()
    details = InquiryDetails(customer_type="个人客户")

    inquiry = build_customization_inquiry(
        request,  # type: ignore[arg-type]
        recommendation,  # type: ignore[arg-type]
        content,  # type: ignore[arg-type]
        details,
    )

    assert inquiry["customization_brief"]["theme"] == PENDING_ZH
    assert inquiry["customization_brief"]["inscription"] == PENDING_ZH
    assert inquiry["customization_brief"]["packaging"] == PENDING_ZH
    assert inquiry["delivery"]["destination"] == PENDING_ZH
    assert any("尚未" in question for question in inquiry["open_questions"])
