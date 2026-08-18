from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from heritagelink.agent_models import CatalogSnapshot
from heritagelink.comparison_models import (
    ApplicationTraceStatus,
    ComparisonDimension,
    EvidenceState,
    ExplanationSource,
    ProductComparisonRequest,
)
from heritagelink.data_loader import build_products, load_data
from heritagelink.inference_policy import build_recommendation_context
from heritagelink.models import GiftRequest
from heritagelink.product_comparison import (
    ProductComparisonError,
    ProductComparisonService,
)
from heritagelink.progressive_recommender import (
    ProgressiveRecommendationResult,
    recommend_progressively,
)
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.recommender import recommend
from heritagelink.request_parser import demo_parse_request

DATA_DIR = Path(__file__).parents[1] / "data" / "demo"
PROFESSOR_REQUEST = "给美国教授选一件单件预算1000元的现代中国文化传承礼物。"
BUSINESS_REQUEST = "给30位海外合作伙伴准备企业周年礼品，每件预算1200元，需要Logo。"
UNKNOWN_REQUEST = "给收藏家准备一件展览陈设礼物，单件预算3000元。"


@pytest.fixture(scope="module")
def catalog() -> CatalogSnapshot:
    bundle = load_data(DATA_DIR)
    products = build_products(bundle)
    formal = tuple(
        product
        for product in products
        if product.catalog_role == "recommendation_demo" and product.status == "active"
    )
    references = tuple(
        product for product in products if product.catalog_role == "catalog_reference"
    )
    assert len(formal) == 21
    assert len(references) == 30
    return CatalogSnapshot(
        bundle=bundle,
        products=products,
        catalog_total=len(products),
        formally_recommendable=len(formal),
        reference_only=len(references),
    )


def _recommendation(
    catalog: CatalogSnapshot,
    text: str,
) -> tuple[ProgressiveRecommendationResult, RecommendationContext]:
    parsed = demo_parse_request(text)
    context = build_recommendation_context(parsed)
    result = recommend_progressively(catalog.products, context.effective_request)
    assert result.response.recommendations
    return result, context


def _ids(result: ProgressiveRecommendationResult) -> tuple[str, ...]:
    return tuple(item.product.product_id for item in result.response.recommendations)


def test_default_scope_compares_three_current_recommendations(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)

    comparison = ProductComparisonService().compare(
        ProductComparisonRequest(), recommendation, context, catalog
    )

    assert comparison.compared_product_ids == _ids(recommendation)
    assert tuple(item.rank_position for item in comparison.items) == (1, 2, 3)
    assert comparison.original_ranking_preserved is True
    assert comparison.recommendation_for_current_user == _ids(recommendation)[0]
    assert not hasattr(comparison, "comparison_score")
    assert not hasattr(comparison, "overall_comparison_score")


def test_explicit_scope_keeps_original_rank_not_caller_order_and_does_not_mutate_response(
    catalog: CatalogSnapshot,
) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    current = _ids(recommendation)
    original_response = recommendation.response

    comparison = ProductComparisonService().compare(
        ProductComparisonRequest(product_ids=(current[2], current[0])),
        recommendation,
        context,
        catalog,
    )

    assert comparison.compared_product_ids == (current[0], current[2])
    assert tuple(item.rank_position for item in comparison.items) == (1, 3)
    assert recommendation.response is original_response
    assert _ids(recommendation) == current


def test_single_product_scope_returns_safe_non_competitive_result(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    first = _ids(recommendation)[0]

    comparison = ProductComparisonService().compare(
        ProductComparisonRequest(product_ids=(first,)), recommendation, context, catalog
    )

    assert comparison.compared_product_ids == (first,)
    assert len(comparison.items) == 1
    assert "不形成商品间优劣结论" in comparison.tradeoffs[0]
    assert "不形成商品间优劣结论" in comparison.deterministic_summary


def test_empty_or_more_than_three_explicit_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="空集合"):
        ProductComparisonRequest(product_ids=())
    with pytest.raises(ValueError, match="最多比较三件"):
        ProductComparisonRequest(product_ids=("a", "b", "c", "d"))


def test_empty_current_recommendation_scope_fails_safely(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    empty = replace(
        recommendation,
        response=replace(recommendation.response, recommendations=()),
    )

    with pytest.raises(ProductComparisonError, match="没有可比较"):
        ProductComparisonService().compare(ProductComparisonRequest(), empty, context, catalog)


def test_active_but_non_current_product_id_cannot_be_compared(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    current = set(_ids(recommendation))
    outside = next(
        product.product_id
        for product in catalog.products
        if product.catalog_role == "recommendation_demo" and product.product_id not in current
    )

    with pytest.raises(ProductComparisonError, match="当前正式推荐"):
        ProductComparisonService().compare(
            ProductComparisonRequest(product_ids=(outside,)),
            recommendation,
            context,
            catalog,
        )


def test_forged_reference_only_recommendation_is_still_rejected(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    reference = next(
        product for product in catalog.products if product.catalog_role == "catalog_reference"
    )
    forged_active = replace(reference, status="active")
    forged_recommendation = recommend(
        [forged_active],
        GiftRequest(
            request_id="forged-reference",
            unit_budget_max_fen=1_000_000,
            quantity=1,
        ),
        limit=1,
    ).recommendations[0]
    forged_result = replace(
        recommendation,
        response=replace(
            recommendation.response,
            recommendations=(forged_recommendation,),
        ),
    )

    with pytest.raises(ProductComparisonError, match="非正式推荐商品"):
        ProductComparisonService().compare(
            ProductComparisonRequest(), forged_result, context, catalog
        )


def test_current_product_fails_if_catalog_record_has_become_inactive(
    catalog: CatalogSnapshot,
) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    current_id = _ids(recommendation)[0]
    inactive_catalog = replace(
        catalog,
        products=tuple(
            replace(product, status="inactive") if product.product_id == current_id else product
            for product in catalog.products
        ),
    )

    with pytest.raises(ProductComparisonError, match="非正式推荐商品"):
        ProductComparisonService().compare(
            ProductComparisonRequest(product_ids=(current_id,)),
            recommendation,
            context,
            inactive_catalog,
        )


def test_demo_commercial_values_remain_unknown_not_false(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, UNKNOWN_REQUEST)
    assert _ids(recommendation) == ("prod_demo_007", "prod_demo_009", "prod_demo_011")

    comparison = ProductComparisonService().compare(
        ProductComparisonRequest(), recommendation, context, catalog
    )

    for item in comparison.items:
        assert item.price_fit.state is EvidenceState.UNKNOWN
        assert item.price_fit.display == "价格待确认"
        assert item.price_display is not None and "演示区间，待确认" in item.price_display
        assert item.international_relevance.state is EvidenceState.UNKNOWN
        assert item.international_relevance.state is not EvidenceState.VERIFIED_NO
        assert item.quantity_fit.state is EvidenceState.UNKNOWN
        assert item.lead_time_summary.state is EvidenceState.UNKNOWN
        assert item.portability_summary.state is EvidenceState.UNKNOWN
        assert item.customization_summary
        assert all(
            evidence.state is EvidenceState.UNKNOWN for evidence in item.customization_summary
        )
        assert {"price", "shipping", "quantity", "lead_time", "portability"}.issubset(
            item.unknown_fields
        )
    assert comparison.unknown_or_unverified
    assert "国家级" not in comparison.customer_summary
    assert "材质" not in comparison.customer_summary


def test_verified_false_and_unverified_false_have_distinct_evidence_states(
    catalog: CatalogSnapshot,
) -> None:
    recommendation, context = _recommendation(catalog, UNKNOWN_REQUEST)
    product_id = _ids(recommendation)[0]
    unverified = ProductComparisonService().compare(
        ProductComparisonRequest(product_ids=(product_id,)),
        recommendation,
        context,
        catalog,
    )
    verified_catalog = replace(
        catalog,
        products=tuple(
            replace(
                product,
                commercial_data_status="verified_merchant_fact",
                supports_international_shipping=False,
            )
            if product.product_id == product_id
            else product
            for product in catalog.products
        ),
    )
    verified = ProductComparisonService().compare(
        ProductComparisonRequest(product_ids=(product_id,)),
        recommendation,
        context,
        verified_catalog,
    )

    assert unverified.items[0].international_relevance.state is EvidenceState.UNKNOWN
    assert verified.items[0].international_relevance.state is EvidenceState.VERIFIED_NO
    assert "已确认不支持" in verified.items[0].international_relevance.display


def test_context_changes_dimension_priority_for_professor_and_business(
    catalog: CatalogSnapshot,
) -> None:
    professor_result, professor_context = _recommendation(catalog, PROFESSOR_REQUEST)
    business_result, business_context = _recommendation(catalog, BUSINESS_REQUEST)

    professor = ProductComparisonService().compare(
        ProductComparisonRequest(), professor_result, professor_context, catalog
    )
    business = ProductComparisonService().compare(
        ProductComparisonRequest(), business_result, business_context, catalog
    )

    assert professor.comparison_dimensions[:3] == (
        ComparisonDimension.RECIPIENT,
        ComparisonDimension.CULTURE,
        ComparisonDimension.STYLE,
    )
    assert business.comparison_dimensions[:3] == (
        ComparisonDimension.RECIPIENT,
        ComparisonDimension.SCENE,
        ComparisonDimension.CUSTOMIZATION,
    )
    assert "教授或教师" in professor.items[0].recipient_fit.display
    assert "商务伙伴" in business.items[0].recipient_fit.display
    assert professor.recommendation_for_current_user == _ids(professor_result)[0]
    assert business.recommendation_for_current_user == _ids(business_result)[0]


def test_grounded_llm_success_uses_sanitized_structured_context(
    catalog: CatalogSnapshot,
) -> None:
    recommendation, context = _recommendation(catalog, PROFESSOR_REQUEST)
    captured: dict[str, object] = {}

    def explain(payload: dict[str, object]) -> str:
        captured.update(payload)
        first_name = recommendation.response.recommendations[0].product.product_name_zh
        return f"就当前需求，我会优先考虑{first_name}；文化方向更贴合，商业信息仍待确认。"

    comparison = ProductComparisonService(explain).compare(
        ProductComparisonRequest(), recommendation, context, catalog
    )

    assert comparison.explanation_source is ExplanationSource.LLM
    assert comparison.ai_explanation
    assert comparison.customer_summary == comparison.ai_explanation
    assert set(captured) == {
        "instruction",
        "products",
        "current_choice",
        "tradeoffs",
        "deterministic_summary",
        "current_context",
    }
    assert "score" not in repr(captured).lower()
    assert not any(product_id in repr(captured) for product_id in _ids(recommendation))


@pytest.mark.parametrize(
    "explanation",
    (
        lambda _payload: "这件价格更低，而且支持国际运输。",
        lambda _payload: {"unsafe": "not text"},
    ),
)
def test_invalid_llm_output_uses_deterministic_fallback(
    catalog: CatalogSnapshot,
    explanation: Any,
) -> None:
    recommendation, context = _recommendation(catalog, UNKNOWN_REQUEST)

    comparison = ProductComparisonService(explanation).compare(
        ProductComparisonRequest(), recommendation, context, catalog
    )

    assert comparison.explanation_source is ExplanationSource.DETERMINISTIC_FALLBACK
    assert comparison.ai_explanation is None
    assert comparison.customer_summary == comparison.deterministic_summary


def test_llm_exception_does_not_break_structured_comparison(catalog: CatalogSnapshot) -> None:
    recommendation, context = _recommendation(catalog, UNKNOWN_REQUEST)

    def fail(_payload: dict[str, object]) -> str:
        raise RuntimeError("provider unavailable")

    comparison, trace = ProductComparisonService(fail).compare_with_trace(
        ProductComparisonRequest(), recommendation, context, catalog
    )

    assert comparison.items
    assert comparison.explanation_source is ExplanationSource.DETERMINISTIC_FALLBACK
    assert trace.action_id == "product_comparison"
    assert trace.status is ApplicationTraceStatus.FALLBACK
    assert trace.output_summary["original_ranking_unchanged"] is True
    assert "no_new_comparison_score" in trace.safety_checks
