from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from heritagelink.data_loader import build_products, load_data
from heritagelink.models import FilterReasonCode, GiftRequest, Product
from heritagelink.recommender import WEIGHTS, recommend

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "demo"


@pytest.fixture(scope="module")
def products() -> tuple[Product, ...]:
    return build_products(load_data(DATA_DIR))


def _request(**overrides: object) -> GiftRequest:
    values: dict[str, object] = {
        "request_id": "req_test",
        "unit_budget_min_fen": 0,
        "unit_budget_max_fen": 300000,
        "quantity": 5,
        "available_lead_days": 90,
    }
    values.update(overrides)
    return GiftRequest(**values)  # type: ignore[arg-type]


def _failure_for(response: object, product_id: str) -> object:
    failures = response.filter_failures  # type: ignore[attr-defined]
    return next(failure for failure in failures if failure.product_id == product_id)


def test_over_budget_products_cannot_be_recommended(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request(unit_budget_max_fen=20000))

    assert not response.has_eligible_products
    assert all(
        FilterReasonCode.OVER_BUDGET in failure.reason_codes for failure in response.filter_failures
    )


def test_quantity_below_minimum_is_filtered(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request(quantity=1))
    failure = _failure_for(response, "prod_demo_006")

    assert FilterReasonCode.BELOW_MIN_ORDER in failure.reason_codes
    assert "prod_demo_006" not in {item.product.product_id for item in response.recommendations}


def test_quantity_above_allowed_limit_is_filtered(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request(quantity=500))

    assert not response.has_eligible_products
    assert all(
        FilterReasonCode.ABOVE_MAX_ORDER in failure.reason_codes
        for failure in response.filter_failures
    )


def test_insufficient_lead_time_is_filtered(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request(available_lead_days=5))

    assert not response.has_eligible_products
    assert all(
        FilterReasonCode.LEAD_TIME_INSUFFICIENT in failure.reason_codes
        for failure in response.filter_failures
    )


def test_required_customization_without_support_is_filtered(
    products: tuple[Product, ...],
) -> None:
    response = recommend(products, _request(quantity=1, customization_required=True))
    failure = _failure_for(response, "prod_demo_007")

    assert FilterReasonCode.CUSTOMIZATION_UNSUPPORTED in failure.reason_codes


def test_required_logo_without_support_is_filtered(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request(quantity=1, logo_required=True))
    failure = _failure_for(response, "prod_demo_002")

    assert FilterReasonCode.LOGO_UNSUPPORTED in failure.reason_codes
    assert "prod_demo_002" not in {item.product.product_id for item in response.recommendations}


def test_required_international_shipping_without_support_is_filtered(
    products: tuple[Product, ...],
) -> None:
    response = recommend(
        products,
        _request(quantity=1, international_shipping_required=True),
    )

    assert (
        FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED
        in _failure_for(response, "prod_demo_004").reason_codes
    )
    assert (
        FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED
        in _failure_for(response, "prod_demo_007").reason_codes
    )


def test_eligible_product_can_score_full_100_points(products: tuple[Product, ...]) -> None:
    request = _request(
        quantity=1,
        unit_budget_min_fen=90000,
        unit_budget_max_fen=130000,
        recipient_tags=frozenset({"business_partner"}),
        occasion_tags=frozenset({"business_gift"}),
        style_tags=frozenset({"elegant"}),
        meaning_tags=frozenset({"heritage"}),
        available_lead_days=30,
    )
    result = next(
        item
        for item in recommend(products, request).recommendations
        if item.product.product_id == "prod_demo_001"
    )

    assert sum(WEIGHTS.values()) == 100
    assert result.total_score == 100.0
    assert set(result.score_breakdown) == set(WEIGHTS)
    assert all(dimension.explanation for dimension in result.score_breakdown.values())


def test_results_never_exceed_three(products: tuple[Product, ...]) -> None:
    response = recommend(products, _request())

    assert 0 < len(response.recommendations) <= 3


def test_no_eligible_products_return_conflicts_and_suggestions(
    products: tuple[Product, ...],
) -> None:
    response = recommend(products, _request(unit_budget_max_fen=1))

    assert response.recommendations == ()
    assert response.message == "没有合格产品"
    assert any("预算" in conflict for conflict in response.primary_conflicts)
    assert response.adjustment_suggestions


def test_same_input_produces_stable_results(products: tuple[Product, ...]) -> None:
    request = _request(
        recipient_tags=frozenset({"business_partner"}),
        occasion_tags=frozenset({"business_gift"}),
    )

    assert recommend(products, request) == recommend(products, request)


def test_tied_scores_sort_by_product_id(products: tuple[Product, ...]) -> None:
    first = replace(products[0], product_id="prod_demo_z_tie")
    second = replace(products[0], product_id="prod_demo_a_tie")

    response = recommend([first, second], _request(quantity=1))

    assert [item.product.product_id for item in response.recommendations] == [
        "prod_demo_a_tie",
        "prod_demo_z_tie",
    ]


def test_effective_lead_time_includes_required_customization(
    products: tuple[Product, ...],
) -> None:
    response = recommend(
        products,
        _request(
            quantity=1,
            available_lead_days=25,
            required_customization_types=frozenset({"logo"}),
        ),
    )
    failure = _failure_for(response, "prod_demo_001")

    assert FilterReasonCode.LEAD_TIME_INSUFFICIENT in failure.reason_codes
    assert any("26 天" in reason for reason in failure.reasons)


def test_evaluation_cases_are_runnable(products: tuple[Product, ...]) -> None:
    cases = json.loads((ROOT / "tests" / "evaluation_cases.json").read_text(encoding="utf-8"))

    assert len(cases) >= 10
    for case in cases:
        request_values = case["request"]
        for field in (
            "recipient_tags",
            "occasion_tags",
            "style_tags",
            "meaning_tags",
            "required_customization_types",
            "preferred_customization_types",
        ):
            request_values[field] = frozenset(request_values[field])
        response = recommend(products, GiftRequest(**request_values))
        result_ids = {item.product.product_id for item in response.recommendations}
        assert len(response.recommendations) <= 3
        assert result_ids.issuperset(case["expected_contains"]), case["case_id"]
        assert (not response.has_eligible_products) is case["expected_empty"], case["case_id"]
