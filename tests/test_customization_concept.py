from pathlib import Path

import pytest

from heritagelink.customization_concept import (
    CONCEPT_DISCLAIMER,
    build_customization_concept,
)
from heritagelink.data_loader import build_products, load_data
from heritagelink.inquiry import InquiryDetails, InquiryRequestContext
from heritagelink.models import GiftRequest
from heritagelink.recommender import recommend

DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def _request(budget: int) -> GiftRequest:
    return GiftRequest(
        request_id="concept_test",
        unit_budget_max_fen=budget,
        quantity=20,
        recipient_tags=frozenset({"business_partner"}),
        occasion_tags=frozenset({"anniversary"}),
    )


def test_no_result_can_generate_concept_without_inventing_product() -> None:
    products = build_products(load_data(DATA_DIR))
    request = _request(10000)
    response = recommend(products, request)
    concept = build_customization_concept(
        request,
        InquiryDetails(
            customer_type="企业客户",
            customization_theme="安徽文化",
            destination="United States",
        ),
        response,
    )

    assert not response.has_eligible_products
    assert concept["is_existing_product"] is False
    assert concept["disclaimer"] == CONCEPT_DISCLAIMER
    assert "product_id" not in concept and "product_name" not in concept
    assert concept["status"] == "概念方案，待商家确认"


def test_concept_is_rejected_when_catalog_has_eligible_products() -> None:
    products = build_products(load_data(DATA_DIR))
    request = _request(300000)
    response = recommend(products, request)
    assert response.has_eligible_products
    with pytest.raises(ValueError, match="存在合格"):
        build_customization_concept(request, InquiryDetails(customer_type="企业客户"), response)


def test_concept_keeps_unstated_budget_quantity_and_boolean_requirements_unknown() -> None:
    products = build_products(load_data(DATA_DIR))
    proxy_request = _request(1)
    response = recommend(products, proxy_request)

    concept = build_customization_concept(
        proxy_request,
        InquiryDetails(customer_type="待商家确认"),
        response,
        customer_context=InquiryRequestContext(available_lead_days=1),
    )

    assert concept["target_unit_budget_fen"] is None
    assert concept["quantity"] is None
    assert concept["customization_required"] is None
    assert concept["logo_required"] is None
    assert concept["international_shipping_required"] is None
