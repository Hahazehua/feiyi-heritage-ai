"""Growth Skill: Creative revision from structured Guardian instructions."""

from heritagelink.growth_agents import revise_campaign_assets
from heritagelink.growth_models import (
    CampaignAsset,
    GrowthProductContext,
    GuardianReview,
    MarketingStrategy,
)


def execute(
    context: GrowthProductContext,
    strategy: MarketingStrategy,
    assets: tuple[CampaignAsset, ...],
    review: GuardianReview,
) -> tuple[CampaignAsset, ...]:
    return revise_campaign_assets(context, strategy, assets, review)
