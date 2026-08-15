"""Growth Skill: product-grounded market opportunity assessment."""

from heritagelink.growth_agents import GrowthModelClient, analyze_market_opportunities
from heritagelink.growth_models import GrowthProductContext, GrowthRunRequest, MarketAnalysis


def execute(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    *,
    client: GrowthModelClient | None = None,
) -> MarketAnalysis:
    return analyze_market_opportunities(context, request, client=client)
