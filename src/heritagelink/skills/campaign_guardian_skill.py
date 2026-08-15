"""Growth Skill: cultural, factual, and commercial grounding review."""

from heritagelink.growth_agents import review_campaign_grounding
from heritagelink.growth_models import CampaignAsset, GrowthProductContext, GuardianReview


def execute(
    context: GrowthProductContext,
    assets: tuple[CampaignAsset, ...],
) -> GuardianReview:
    return review_campaign_grounding(context, assets)
