"""Phrasing of "why this fits", and the scoreboard it falls back to."""

from __future__ import annotations

from pathlib import Path

import pytest

from heritagelink import recommendation_narrative
from heritagelink.comparison_models import ExplanationSource
from heritagelink.data_loader import build_products, load_data
from heritagelink.inference_policy import build_recommendation_context
from heritagelink.llm_client import LLMInvalidJSONError, MissingAPIKeyError
from heritagelink.progressive_recommender import recommend_progressively
from heritagelink.request_parser import demo_parse_request

ROOT = Path(__file__).parents[1]


def _recommendations():  # type: ignore[no-untyped-def]
    parsed = demo_parse_request("送给20位合作伙伴的周年礼物，每件预算1000元")
    context = build_recommendation_context(parsed)
    products = build_products(load_data(ROOT / "data" / "demo"))
    result = recommend_progressively(products, context.effective_request)
    return result.response.recommendations, frozenset(result.participating_dimensions)


class _StubClient:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def explain_recommendations(self, payload: dict[str, object]) -> dict[str, str]:
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        assert isinstance(self.response, dict)
        return self.response


def test_payload_carries_only_scored_facts() -> None:
    recommendations, participating = _recommendations()
    payload = recommendation_narrative.build_payload(
        recommendations,
        request_summary="周年礼物",
        language="zh-CN",
        participating=participating,
    )

    assert payload["language"] == "zh-CN"
    products = payload["products"]
    assert products
    for product in products:
        # Nothing beyond the scoring verdict is offered, so the model has no
        # raw price or provenance to embroider.
        assert set(product) == {
            "product_id",
            "product_name",
            "total_score",
            "matched_tags",
            "risks",
            "dimensions",
        }
        for dimension in product["dimensions"]:
            assert dimension["dimension"] in participating


def test_payload_is_capped_so_the_buyer_screen_stays_responsive() -> None:
    recommendations, participating = _recommendations()
    payload = recommendation_narrative.build_payload(
        recommendations,
        request_summary="周年礼物",
        language="zh-CN",
        participating=participating,
    )

    assert len(payload["products"]) <= recommendation_narrative.MAX_EXPLAINED


def test_explanations_are_returned_when_the_model_answers() -> None:
    recommendations, participating = _recommendations()
    first = recommendations[0].product.product_id
    # Whitespace is trimmed by DeepSeekClient.explain_recommendations, so the
    # stub hands back text that is already display-ready.
    client = _StubClient({first: "这件符合你说的商务周年场合。"})

    explanations, source = recommendation_narrative.explain(
        recommendations,
        request_summary="周年礼物",
        language="zh-CN",
        participating=participating,
        client=client,
    )

    assert source is ExplanationSource.LLM
    assert explanations[first] == "这件符合你说的商务周年场合。"
    assert len(client.calls) == 1, "every card must be covered by one call"


def test_unknown_product_ids_are_discarded() -> None:
    recommendations, participating = _recommendations()
    client = _StubClient({"not-a-real-product": "凭空捏造的解释"})

    explanations, source = recommendation_narrative.explain(
        recommendations,
        request_summary="周年礼物",
        language="zh-CN",
        participating=participating,
        client=client,
    )

    assert explanations == {}
    assert source is ExplanationSource.DETERMINISTIC_FALLBACK


@pytest.mark.parametrize(
    "error",
    [MissingAPIKeyError("no key"), LLMInvalidJSONError("bad json")],
)
def test_any_model_failure_falls_back_to_the_scoreboard(error: Exception) -> None:
    """A missing key is ordinary configuration, not something buyers should see."""
    recommendations, participating = _recommendations()
    client = _StubClient(error=error)

    explanations, source = recommendation_narrative.explain(
        recommendations,
        request_summary="周年礼物",
        language="zh-CN",
        participating=participating,
        client=client,
    )

    assert explanations == {}
    assert source is ExplanationSource.DETERMINISTIC_FALLBACK


def test_no_recommendations_needs_no_call() -> None:
    client = _StubClient({"x": "y"})

    explanations, source = recommendation_narrative.explain(
        [],
        request_summary="",
        language="zh-CN",
        participating=frozenset(),
        client=client,
    )

    assert explanations == {}
    assert source is ExplanationSource.DETERMINISTIC_FALLBACK
    assert client.calls == []
