from __future__ import annotations

from pathlib import Path

import pytest

from heritagelink.agent_models import RequestedAction
from heritagelink.data_loader import build_products, load_data
from heritagelink.models import GiftRequest, RecommendationResponse
from heritagelink.recommender import recommend
from heritagelink.request_parser import demo_parse_request
from heritagelink.shopping_turn_router import (
    apply_relative_refinement,
    asks_for_unspecified_lower_budget,
    route_shopping_turn,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


@pytest.fixture(scope="module")
def recommendation_response() -> RecommendationResponse:
    products = build_products(load_data(DATA_DIR))
    return recommend(
        products,
        GiftRequest(
            request_id="shopping-router",
            unit_budget_max_fen=300_000,
            quantity=5,
            recipient_tags=frozenset({"business_partner"}),
            occasion_tags=frozenset({"business_gift"}),
        ),
    )


def _ids(response: RecommendationResponse) -> tuple[str, ...]:
    return tuple(item.product.product_id for item in response.recommendations)


def test_router_compares_first_and_third_in_current_recommendation_order(
    recommendation_response: RecommendationResponse,
) -> None:
    route = route_shopping_turn(
        "第一个和第三个哪一个更适合教授？",
        recommendation_response,
    )

    current = _ids(recommendation_response)
    assert route.action is RequestedAction.COMPARE_SELECTED_PRODUCTS
    assert route.product_ids == (current[0], current[2])
    assert route.focus_dimensions == ("recipient",)
    assert route.focus_recipient == "teacher"


def test_router_compares_all_or_only_the_first_two_current_results(
    recommendation_response: RecommendationResponse,
) -> None:
    current = _ids(recommendation_response)

    compare_all = route_shopping_turn("帮我比较这三个", recommendation_response)
    compare_two = route_shopping_turn("那就只比较前两个", recommendation_response)

    assert compare_all.action is RequestedAction.COMPARE_RECOMMENDATIONS
    assert compare_all.product_ids == current
    assert compare_two.action is RequestedAction.COMPARE_SELECTED_PRODUCTS
    assert compare_two.product_ids == current[:2]


def test_router_selects_an_ordinal_only_from_the_current_results(
    recommendation_response: RecommendationResponse,
) -> None:
    current = _ids(recommendation_response)

    selected = route_shopping_turn("那我选第一个", recommendation_response)
    out_of_range = route_shopping_turn(
        "那我选第三个",
        recommend(
            build_products(load_data(DATA_DIR))[:1],
            GiftRequest(request_id="one-result", unit_budget_max_fen=300_000, quantity=1),
        ),
    )

    assert selected.action is RequestedAction.SELECT_PRODUCT
    assert selected.product_id == current[0]
    assert out_of_range.action is RequestedAction.CONTINUE_CONVERSATION
    assert out_of_range.product_id is None


@pytest.mark.parametrize(
    "text",
    (
        "再现代一点",
        "我喜欢第一件，但预算还能再低一点",
        "有没有更便宜的类似款",
    ),
)
def test_router_recognizes_post_recommendation_refinement(
    text: str,
    recommendation_response: RecommendationResponse,
) -> None:
    assert (
        route_shopping_turn(text, recommendation_response).action
        is RequestedAction.REFINE_RECOMMENDATIONS
    )


def test_router_does_not_create_a_shopping_action_without_current_results() -> None:
    route = route_shopping_turn("比较第一个和第三个", None)

    assert route.action is RequestedAction.CONTINUE_CONVERSATION
    assert route.product_ids == ()


def test_comparison_language_with_one_ordinal_routes_to_explanation(
    recommendation_response: RecommendationResponse,
) -> None:
    route = route_shopping_turn("第一个为什么更适合商务场景？", recommendation_response)

    assert route.action is RequestedAction.EXPLAIN_DIFFERENCE
    assert route.product_ids == (_ids(recommendation_response)[0],)
    assert route.focus_dimensions == ("scene",)


def test_relative_modern_refinement_replaces_prior_traditional_style() -> None:
    request = demo_parse_request("我想找一件传统礼物")

    updated, overrides = apply_relative_refinement(request, "再现代一点")

    assert updated.style_preferences == ("modern",)
    assert "traditional" not in updated.style_preferences
    assert overrides == frozenset({"style_preferences"})


def test_negative_traditional_phrase_becomes_modern_override_not_positive_traditional() -> None:
    request = demo_parse_request("我想找一件传统礼物")

    updated, overrides = apply_relative_refinement(request, "不要太传统")

    assert updated.style_preferences == ("modern",)
    assert "traditional" not in updated.style_preferences
    assert overrides == frozenset({"style_preferences"})


def test_unspecified_lower_budget_requires_follow_up_but_numeric_budget_does_not() -> None:
    assert asks_for_unspecified_lower_budget("预算再低一点")
    assert asks_for_unspecified_lower_budget("有没有更便宜的")
    assert not asks_for_unspecified_lower_budget("预算改成每件800元")
