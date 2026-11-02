"""Run real ADK and Growth Studio rules with a synthetic, no-key demonstration."""

import asyncio
import json

from heritagelink.adk_campaign import run_adk_campaign_loop
from heritagelink.growth_agents import analyze_market_opportunities, build_marketing_strategy
from heritagelink.growth_models import GrowthProductContext, GrowthRunRequest
from heritagelink.heritage_passport_models import PublicationStatus


async def main():
    context = GrowthProductContext(
        artisan_id="synthetic_demo",
        product_id="synthetic_demo",
        product_name="Demonstration craft",
        product_name_en="Demonstration craft",
        craft_name="Demonstration craft",
        publication_status=PublicationStatus.DRAFT,
        verified_facts=(),
        unverified_facts=(),
        unknown_fields=("price_min_fen", "lead_time_days", "international_shipping"),
    )
    request = GrowthRunRequest(
        artisan_id=context.artisan_id,
        product_id=context.product_id,
        campaign_goal="Explore a draft inquiry",
        demo_guardian_scenario=True,
    )
    analysis = analyze_market_opportunities(context, request)
    strategy = build_marketing_strategy(context, request, analysis)
    result = await run_adk_campaign_loop(context, request, analysis, strategy)
    print(
        json.dumps(
            {
                "mode": "synthetic_demo_no_model_calls",
                "checks_passed": result.checks_passed,
                "requires_human_review": result.requires_human_review,
                "revision_count": result.revision_count,
                "events": result.events,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
