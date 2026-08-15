"""Growth Skill: strategy derived from a completed market assessment."""

from heritagelink.growth_agents import GrowthModelClient, build_marketing_strategy
from heritagelink.growth_models import (
    GrowthProductContext,
    GrowthRunRequest,
    MarketAnalysis,
    MarketingStrategy,
)


def execute(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    analysis: MarketAnalysis,
    *,
    client: GrowthModelClient | None = None,
) -> MarketingStrategy:
    return build_marketing_strategy(context, request, analysis, client=client)
