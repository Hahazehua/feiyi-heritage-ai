"""State-machine orchestration for the Artisan-side HAHA Growth Team."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from heritagelink.agent_models import SkillExecutionTrace, SkillStatus
from heritagelink.agent_trace import TraceTimer, safety
from heritagelink.growth_agents import GrowthModelClient, apply_human_edits
from heritagelink.growth_models import (
    CampaignStatus,
    GrowthOutputSource,
    GrowthProductContext,
    GrowthRunRequest,
    GrowthRunState,
    GrowthRunStatus,
    MarketingCampaign,
)
from heritagelink.skills import (
    campaign_creative_skill,
    campaign_guardian_skill,
    campaign_revision_skill,
    market_intelligence_skill,
    marketing_strategy_skill,
)

MAX_AUTOMATIC_REVISIONS = 2


def run_growth_workflow(
    request: GrowthRunRequest,
    product_context: GrowthProductContext,
    *,
    client: GrowthModelClient | None = None,
    maximum_revisions: int = MAX_AUTOMATIC_REVISIONS,
    now: datetime | None = None,
) -> tuple[GrowthRunState, MarketingCampaign]:
    """Coordinate Market -> Strategy -> Creative -> Guardian with a bounded loop."""
    if request.product_id != product_context.product_id:
        raise ValueError("growth request product does not match the loaded context")
    if request.artisan_id != product_context.artisan_id:
        raise ValueError("growth request artisan does not match the loaded context")
    if not 0 <= maximum_revisions <= MAX_AUTOMATIC_REVISIONS:
        raise ValueError("maximum_revisions must be between 0 and 2")

    traces: list[SkillExecutionTrace] = []
    state = GrowthRunState(
        run_id=f"growth_{uuid4().hex}",
        request=request,
        product_context=product_context,
    )

    timer = TraceTimer(
        "analyze_market_opportunities",
        "Verified and unknown product context loaded for opportunity assessment",
    )
    analysis = market_intelligence_skill.execute(product_context, request, client=client)
    traces.append(
        timer.finish(
            _status_for_source(analysis.source),
            input_summary={
                "verified_fact_count": len(product_context.verified_facts),
                "unverified_fact_count": len(product_context.unverified_facts),
                "unknown_field_count": len(product_context.unknown_fields),
            },
            output_summary={
                "opportunity_count": len(analysis.opportunities),
                "recommended_segment": analysis.recommended_segment,
                "external_evidence_used": analysis.external_evidence_used,
                "generation_source": analysis.source.value,
            },
            fallback_reason=(
                "product_grounded_deterministic_assessment"
                if analysis.source is GrowthOutputSource.SAFE_FALLBACK
                else None
            ),
            safety_checks=(
                safety(
                    "no_fabricated_market_statistics",
                    not analysis.external_evidence_used,
                    "Output is labelled as a product-grounded assessment, not market research",
                ),
                safety(
                    "publication_boundary_preserved",
                    True,
                    "Market assessment cannot change catalogue eligibility",
                ),
            ),
        )
    )
    state = replace(state, market_analysis=analysis, trace_events=tuple(traces))

    timer = TraceTimer(
        "build_marketing_strategy",
        "Market Intelligence selected a recommended commercial scenario",
    )
    strategy = marketing_strategy_skill.execute(
        product_context,
        request,
        analysis,
        client=client,
    )
    traces.append(
        timer.finish(
            _status_for_source(strategy.source),
            input_summary={"recommended_segment": analysis.recommended_segment},
            output_summary={
                "strategy_channel_count": len(strategy.recommended_channels),
                "generation_source": strategy.source.value,
            },
            fallback_reason=(
                "bounded_deterministic_strategy"
                if strategy.source is GrowthOutputSource.SAFE_FALLBACK
                else None
            ),
            safety_checks=(
                safety(
                    "strategy_precedes_creative",
                    True,
                    "Creative receives a completed positioning and cannot rewrite it retroactively",
                ),
            ),
        )
    )
    state = replace(state, strategy=strategy, trace_events=tuple(traces))

    timer = TraceTimer(
        "generate_campaign_assets",
        "A completed strategy and verified product context are available",
    )
    assets = campaign_creative_skill.execute(
        product_context,
        request,
        analysis,
        strategy,
        client=client,
    )
    creative_source = _combined_source(request, analysis.source, strategy.source)
    traces.append(
        timer.finish(
            _status_for_source(creative_source),
            input_summary={
                "verified_fact_count": len(product_context.verified_facts),
                "strategy_channel_count": len(strategy.recommended_channels),
            },
            output_summary={
                "campaign_asset_count": len(assets),
                "generation_source": creative_source.value,
            },
            fallback_reason=(
                "grounded_campaign_templates"
                if creative_source is GrowthOutputSource.SAFE_FALLBACK
                else None
            ),
            safety_checks=(
                safety(
                    "verified_facts_only",
                    True,
                    "Creative receives verified facts separately from pending and unknown fields",
                ),
            ),
        )
    )
    state = replace(state, campaign_assets=assets, trace_events=tuple(traces))

    review = _guardian_trace(product_context, assets, traces, revision_count=0)
    revision_count = 0
    while not review.approved and revision_count < maximum_revisions:
        revision_count += 1
        timer = TraceTimer(
            "revise_campaign_assets",
            "Cultural Guardian returned structured revision instructions",
        )
        assets = campaign_revision_skill.execute(product_context, strategy, assets, review)
        traces.append(
            timer.finish(
                SkillStatus.SUCCESS,
                input_summary={
                    "guardian_issue_count": len(review.issues),
                    "revision_count": revision_count,
                },
                output_summary={
                    "campaign_asset_count": len(assets),
                    "revision_count": revision_count,
                },
                safety_checks=(
                    safety(
                        "raw_ai_version_preserved",
                        all(asset.raw_ai_content is not None for asset in assets),
                        "Revision keeps the original AI text for audit and human comparison",
                    ),
                ),
            )
        )
        review = _guardian_trace(
            product_context,
            assets,
            traces,
            revision_count=revision_count,
        )

    run_status = GrowthRunStatus.READY if review.approved else GrowthRunStatus.NEEDS_REVIEW
    campaign_status = CampaignStatus.READY if review.approved else CampaignStatus.NEEDS_REVIEW
    state = replace(
        state,
        status=run_status,
        campaign_assets=assets,
        guardian_review=review,
        revision_count=revision_count,
        trace_events=tuple(traces),
    )
    timestamp = now or datetime.now(UTC)
    source = _combined_source(request, analysis.source, strategy.source)
    campaign = MarketingCampaign(
        campaign_id=f"campaign_{uuid4().hex}",
        campaign_name=f"{analysis.recommended_segment} | {product_context.product_name}",
        artisan_id=request.artisan_id,
        product_id=request.product_id,
        goal=request.campaign_goal,
        target_geography=request.target_geography,
        target_segment=analysis.recommended_segment,
        market_analysis=analysis,
        strategy=strategy,
        assets=assets,
        guardian_review=review,
        revision_count=revision_count,
        status=campaign_status,
        source=source,
        trace_events=tuple(traces),
        created_at=timestamp,
        updated_at=timestamp,
    )
    return state, campaign


def update_campaign_with_human_edits(
    campaign: MarketingCampaign,
    edits: dict[str, str],
    *,
    reviewed_warnings: tuple[str, ...] = (),
    now: datetime | None = None,
) -> MarketingCampaign:
    """Persist human edits separately and require review if text actually changed."""
    assets = apply_human_edits(campaign.assets, edits)
    changed = any(
        asset.final_human_content
        and asset.final_human_content != (asset.revised_ai_content or asset.content)
        for asset in assets
    )
    return replace(
        campaign,
        assets=assets,
        status=CampaignStatus.NEEDS_REVIEW if changed else campaign.status,
        human_reviewed_warnings=tuple(dict.fromkeys(reviewed_warnings)),
        updated_at=now or datetime.now(UTC),
    )


def regenerate_campaign_asset(
    campaign: MarketingCampaign,
    state: GrowthRunState,
    asset_id: str,
    *,
    client: GrowthModelClient | None = None,
    now: datetime | None = None,
) -> MarketingCampaign:
    """Regenerate one channel, then rerun Guardian with the same bounded loop."""
    current = next((asset for asset in campaign.assets if asset.asset_id == asset_id), None)
    if current is None or state.market_analysis is None or state.strategy is None:
        raise ValueError("campaign asset or Growth run context is unavailable")
    one_channel_request = replace(
        state.request,
        preferred_channels=(current.channel,),
        demo_guardian_scenario=False,
    )
    timer = TraceTimer(
        "generate_campaign_assets",
        f"Human requested regeneration of the {current.channel} asset",
    )
    generated = campaign_creative_skill.execute(
        state.product_context,
        one_channel_request,
        state.market_analysis,
        state.strategy,
        client=client,
    )
    replacement = replace(generated[0], asset_id=current.asset_id)
    assets = tuple(
        replacement if asset.asset_id == asset_id else asset for asset in campaign.assets
    )
    traces = list(campaign.trace_events)
    traces.append(
        timer.finish(
            SkillStatus.SUCCESS,
            input_summary={"strategy_channel_count": 1},
            output_summary={"campaign_asset_count": 1},
            safety_checks=(
                safety(
                    "single_asset_scope",
                    True,
                    "Regeneration preserves the market analysis and campaign strategy",
                ),
            ),
        )
    )
    review = _guardian_trace(
        state.product_context,
        assets,
        traces,
        revision_count=0,
    )
    revisions = 0
    while not review.approved and revisions < MAX_AUTOMATIC_REVISIONS:
        revisions += 1
        revision_timer = TraceTimer(
            "revise_campaign_assets",
            "Guardian rejected the regenerated asset",
        )
        assets = campaign_revision_skill.execute(
            state.product_context,
            state.strategy,
            assets,
            review,
        )
        traces.append(
            revision_timer.finish(
                SkillStatus.SUCCESS,
                input_summary={
                    "guardian_issue_count": len(review.issues),
                    "revision_count": revisions,
                },
                output_summary={
                    "campaign_asset_count": len(assets),
                    "revision_count": revisions,
                },
            )
        )
        review = _guardian_trace(
            state.product_context,
            assets,
            traces,
            revision_count=revisions,
        )
    return replace(
        campaign,
        assets=assets,
        guardian_review=review,
        revision_count=campaign.revision_count + revisions,
        status=CampaignStatus.READY if review.approved else CampaignStatus.NEEDS_REVIEW,
        trace_events=tuple(traces),
        updated_at=now or datetime.now(UTC),
    )


def _guardian_trace(
    context: GrowthProductContext,
    assets,
    traces: list[SkillExecutionTrace],
    *,
    revision_count: int,
):
    timer = TraceTimer(
        "review_campaign_grounding",
        "Creative assets require factual, cultural, and commercial verification",
    )
    review = campaign_guardian_skill.execute(context, assets)
    traces.append(
        timer.finish(
            SkillStatus.SUCCESS if review.approved else SkillStatus.BLOCKED,
            input_summary={
                "campaign_asset_count": len(assets),
                "verified_fact_count": len(context.verified_facts),
                "revision_count": revision_count,
            },
            output_summary={
                "guardian_approved": review.approved,
                "guardian_issue_count": len(review.issues),
                "risk_level": review.risk_level.value,
                "requires_human_review": not review.approved,
                "revision_count": revision_count,
                "publication_eligibility_changed": False,
            },
            safety_checks=(
                safety(
                    "guardian_does_not_publish",
                    True,
                    "Campaign approval never changes product publication status",
                ),
                safety(
                    "unknown_remains_unknown",
                    True,
                    "Pending commercial and cultural facts are not upgraded by marketing output",
                ),
            ),
        )
    )
    return review


def _status_for_source(source: GrowthOutputSource) -> SkillStatus:
    return (
        SkillStatus.FALLBACK if source is GrowthOutputSource.SAFE_FALLBACK else SkillStatus.SUCCESS
    )


def _combined_source(
    request: GrowthRunRequest,
    *sources: GrowthOutputSource,
) -> GrowthOutputSource:
    if GrowthOutputSource.SAFE_FALLBACK in sources:
        return GrowthOutputSource.SAFE_FALLBACK
    if request.output_source is GrowthOutputSource.LIVE_AI and all(
        source is GrowthOutputSource.LIVE_AI for source in sources
    ):
        return GrowthOutputSource.LIVE_AI
    return GrowthOutputSource.DETERMINISTIC_DEMO


__all__ = [
    "MAX_AUTOMATIC_REVISIONS",
    "regenerate_campaign_asset",
    "run_growth_workflow",
    "update_campaign_with_human_edits",
]
