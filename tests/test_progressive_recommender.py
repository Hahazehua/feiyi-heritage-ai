from pathlib import Path

from heritagelink.data_loader import build_products, load_data
from heritagelink.models import FilterReasonCode
from heritagelink.progressive_recommender import (
    RecommendationMode,
    recommend_progressively,
)
from heritagelink.request_parser import demo_parse_request

DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def _products():  # type: ignore[no-untyped-def]
    return build_products(load_data(DATA_DIR))


def test_partial_request_returns_guided_recommendations() -> None:
    parsed = demo_parse_request("我想给外国朋友送一件有中国特色的礼物")
    result = recommend_progressively(_products(), parsed)

    assert result.mode == RecommendationMode.GUIDED
    assert result.response.recommendations
    assert len(result.response.recommendations) <= 3
    assert all(item.total_score > 0 for item in result.response.recommendations)
    assert "budget_per_item" in result.missing_fields
    assert "quantity" in result.missing_fields
    assert result.confidence_level in {"低", "中", "高"}


def test_unknown_fields_do_not_filter_products() -> None:
    parsed = demo_parse_request("我想看看非遗礼品")
    result = recommend_progressively(_products(), parsed)

    assert result.mode == RecommendationMode.EXPLORING
    assert result.response.recommendations
    assert result.information_coverage == 0


def test_explicit_budget_remains_a_hard_constraint() -> None:
    parsed = demo_parse_request("送给30位合作伙伴的周年礼物，每件预算100元")
    result = recommend_progressively(_products(), parsed)

    assert not result.response.recommendations
    assert result.alternatives
    assert all(
        FilterReasonCode.OVER_BUDGET in failure.reason_codes
        for failure in result.response.filter_failures
    )


def test_missing_dimensions_are_excluded_from_normalized_score() -> None:
    parsed = demo_parse_request("送给朋友的礼物")
    result = recommend_progressively(_products(), parsed)

    assert result.participating_dimensions == ("recipient",)
    assert all(0 <= item.total_score <= 100 for item in result.response.recommendations)


def test_progressive_results_are_stable() -> None:
    parsed = demo_parse_request("送给合作伙伴的周年礼物")
    first = recommend_progressively(_products(), parsed)
    second = recommend_progressively(_products(), parsed)

    assert [item.product.product_id for item in first.response.recommendations] == [
        item.product.product_id for item in second.response.recommendations
    ]
