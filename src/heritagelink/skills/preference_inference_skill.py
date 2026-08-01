"""Skill 2 wrapper: apply the existing allowlisted inference policy."""

from heritagelink.inference_policy import build_recommendation_context
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.request_parser import ParsedCustomerRequest


def execute(request: ParsedCustomerRequest) -> RecommendationContext:
    return build_recommendation_context(request)
