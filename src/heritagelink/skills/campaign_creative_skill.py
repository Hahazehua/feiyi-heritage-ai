"""Growth Skill: coordinated multi-channel campaign generation."""

from heritagelink.growth_agents import GrowthModelClient, generate_campaign_assets
from heritagelink.growth_models import (
    CampaignAsset,
    GrowthProductContext,
    GrowthRunRequest,
    MarketAnalysis,
    MarketingStrategy,
)


def execute(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    analysis: MarketAnalysis,
    strategy: MarketingStrategy,
    *,
    client: GrowthModelClient | None = None,
) -> tuple[CampaignAsset, ...]:
    return generate_campaign_assets(context, request, analysis, strategy, client=client)
