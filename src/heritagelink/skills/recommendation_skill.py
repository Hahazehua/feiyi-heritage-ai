"""Skill 3 wrapper: call the deterministic hard-filtered recommender."""

from heritagelink.catalog_eligibility import eligible_products
from heritagelink.models import Product
from heritagelink.progressive_recommender import (
    ProgressiveRecommendationResult,
    recommend_progressively,
)
from heritagelink.recommendation_context import RecommendationContext


def execute(
    products: tuple[Product, ...],
    context: RecommendationContext,
) -> ProgressiveRecommendationResult:
    return recommend_progressively(eligible_products(products), context.effective_request)
