"""Streamlit presentation helpers for HAHA Growth Studio."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from html import escape

import streamlit as st

from heritagelink.growth_agents import GrowthModelClient
from heritagelink.growth_models import (
    GrowthOutputSource,
    GrowthProductContext,
    GrowthRunRequest,
    GrowthRunState,
    GrowthRunStatus,
    MarketingCampaign,
    MarketingStrategy,
)
from heritagelink.growth_orchestrator import (
    regenerate_campaign_asset,
    run_growth_workflow,
    update_campaign_with_human_edits,
)
from heritagelink.i18n import Language, get_language, t
from heritagelink.repositories.campaign_repository import CampaignRepository
from heritagelink.ui.system import (
    render_demo_badge,
    render_empty_state,
    render_metric_strip,
    render_status_badge,
    status_label,
)


def render_growth_hero() -> None:
    st.markdown(
        f"""
        <section class="hl-hero hl-growth-hero">
          <div class="hl-eyebrow">{escape(t("growth.eyebrow"))}</div>
          <h1 class="hl-brand">{escape(t("growth.title"))}</h1>
          <p class="hl-copy">{escape(t("growth.subtitle"))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_demo_badge()


def _product_name(context: GrowthProductContext) -> str:
    if get_language() == Language.EN_US and context.product_name_en:
        return context.product_name_en
    return context.product_name


def render_product_context(context: GrowthProductContext) -> None:
    st.markdown(f"### 1. {t('growth.product_context')}")
    render_metric_strip(
        (
            (t("growth.verified_fields"), str(len(context.verified_facts)), None),
            (t("growth.pending_facts"), str(len(context.unverified_facts)), None),
            (t("growth.unknown_fields"), str(len(context.unknown_fields)), None),
            (t("growth.product_status"), status_label(context.publication_status), None),
        )
    )
    st.markdown(f"#### {escape(_product_name(context))}")
    st.caption(f"{context.craft_name} · {t('growth.context_source')}: {context.context_label}")
    render_status_badge(context.publication_status)
    if context.requires_draft_label:
        st.warning(t("growth.internal_draft_warning"))
    if context.verified_facts:
        with st.expander(t("growth.verified_fields")):
            for fact in context.verified_facts:
                st.write(f"✓ `{fact.field_name}`: {_display_value(fact.value)}")
    if context.unverified_facts:
        with st.expander(t("growth.pending_facts")):
            for fact in context.unverified_facts:
                st.write(f"△ `{fact.field_name}`: {_display_value(fact.value)}")
    if context.unknown_fields:
        st.caption(f"{t('common.unknown')}: " + ", ".join(context.unknown_fields))


def render_growth_trace(state: GrowthRunState) -> None:
    st.markdown(f"### {t('growth.team_title')}")
    traces_by_skill = {trace.skill_id: trace for trace in state.trace_events}
    guardian = traces_by_skill.get("review_campaign_grounding")
    steps = (
        (
            t("growth.market"),
            traces_by_skill.get("analyze_market_opportunities"),
            t(
                "growth.summary.opportunities",
                count=len(state.market_analysis.opportunities) if state.market_analysis else 0,
            ),
        ),
        (
            t("growth.strategy"),
            traces_by_skill.get("build_marketing_strategy"),
            t(
                "growth.summary.strategy",
                count=len(state.strategy.recommended_channels) if state.strategy else 0,
            ),
        ),
        (
            t("growth.creative"),
            traces_by_skill.get("generate_campaign_assets"),
            t("growth.summary.assets", count=len(state.campaign_assets)),
        ),
        (
            t("growth.guardian"),
            guardian,
            (
                t("growth.summary.guardian_ready")
                if state.guardian_review and state.guardian_review.approved
                else t(
                    "growth.summary.guardian_review",
                    count=len(state.guardian_review.issues) if state.guardian_review else 0,
                )
            ),
        ),
    )
    markup: list[str] = []
    for label, trace, summary in steps:
        completed = trace is not None and trace.status.value in {"success", "fallback"}
        warning = trace is not None and trace.status.value in {"blocked", "degraded"}
        css_class = "done" if completed else "warn" if warning else ""
        marker = "✓" if completed else "△" if warning else "○"
        markup.append(
            f'<div class="hl-agent-step {css_class}"><span>{marker}</span>'
            f"<strong>{escape(label)}</strong><small>{escape(summary)}</small></div>"
        )
    st.markdown(f'<div class="hl-agent-flow">{"".join(markup)}</div>', unsafe_allow_html=True)
    with st.expander(t("trace.title")):
        for trace in state.trace_events:
            st.write(f"**{trace.skill_name}** · {trace.status.value}")
            st.json(trace.output_summary)
            if trace.fallback_used:
                st.caption(f"{t('trace.fallback')}: {trace.fallback_reason}")


def render_market_analysis(campaign: MarketingCampaign) -> None:
    analysis = campaign.market_analysis
    st.markdown(f"### 2. {t('growth.market_title')}")
    st.markdown(
        f'<div class="hl-trust-note">{escape(t("growth.market_disclaimer"))}</div>',
        unsafe_allow_html=True,
    )
    cards: list[str] = []
    for opportunity in analysis.opportunities:
        reasons = "".join(f"<li>{escape(reason)}</li>" for reason in opportunity.reasons)
        risks = "".join(f"<li>{escape(risk)}</li>" for risk in opportunity.risks)
        primary = " primary" if opportunity.segment == analysis.recommended_segment else ""
        cards.append(
            f'<article class="hl-opportunity-card{primary}">'
            f"<h3>{escape(opportunity.segment)}</h3>"
            f'<div class="hl-opportunity-score"><strong>{opportunity.fit_score}</strong>'
            f"<span>/ 100 · {escape(t('growth.strong_fit'))}</span></div>"
            f"<h4>{escape(t('growth.why'))}</h4><ul>{reasons}</ul>"
            f"<h4>{escape(t('growth.watch'))}</h4><ul>{risks}</ul>"
            "</article>"
        )
    st.markdown(f'<div class="hl-opportunity-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_strategy(strategy: MarketingStrategy) -> None:
    st.markdown(f"### 3. {t('growth.strategy_title')}")
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{t('growth.strategy.goal')}**")
        st.write(strategy.campaign_goal)
        st.markdown(f"**{t('growth.strategy.audience')}**")
        st.write(" · ".join(strategy.target_audience))
        st.markdown(f"**{t('growth.strategy.positioning')}**")
        st.write(strategy.positioning)
    with right:
        st.markdown(f"**{t('growth.strategy.value')}**")
        st.write(strategy.value_proposition)
        st.markdown(f"**{t('growth.strategy.channels')}**")
        st.write(" · ".join(strategy.recommended_channels))
        st.markdown(f"**{t('growth.strategy.cta')}**")
        st.write(strategy.cta)
    with st.expander(t("growth.strategy.messages")):
        for message in strategy.key_messages:
            st.write(f"✓ {message}")
        for risk in strategy.risks:
            st.write(f"△ {risk}")
        st.markdown(f"**{t('growth.strategy.avoid')}**")
        for item in strategy.things_to_avoid:
            st.write(f"✕ {item}")


def render_guardian(campaign: MarketingCampaign) -> None:
    review = campaign.guardian_review
    st.markdown(f"### 4. {t('growth.guardian_title')}")
    if review.approved:
        st.success(t("growth.guardian_ready"))
    else:
        st.warning(t("growth.guardian_needs_review"))
    revised_assets = tuple(
        asset for asset in campaign.assets if asset.raw_ai_content and asset.revised_ai_content
    )
    render_metric_strip(
        (
            (t("growth.claims_count"), str(len(review.supported_claims)), None),
            (t("growth.revisions_count"), str(campaign.revision_count), None),
            (t("growth.revised_claims"), str(len(revised_assets)), None),
            (t("growth.risk"), status_label(review.risk_level), None),
        )
    )
    st.markdown(
        '<div class="hl-guardian-summary">'
        '<div class="hl-guardian-check"><strong>✓</strong>'
        f"{escape(t('growth.no_credentials'))}</div>"
        '<div class="hl-guardian-check"><strong>✓</strong>'
        f"{escape(t('growth.no_logistics'))}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    for asset in revised_assets:
        st.markdown(f"**{escape(asset.channel)}**")
        st.markdown(
            '<div class="hl-guardian-diff">'
            f"<div><label>{escape(t('growth.original'))}</label>"
            f"{escape(asset.raw_ai_content or '')}</div>"
            f"<div><label>{escape(t('growth.revised'))}</label>"
            f"{escape(asset.revised_ai_content or '')}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    if review.supported_claims:
        with st.expander(t("growth.supported_claims")):
            for claim in review.supported_claims:
                st.write(f"✓ {claim}")
    if review.issues:
        for issue in review.issues:
            with st.expander(f"{issue.asset_id} · {issue.issue_type}"):
                st.write(f"**{t('growth.original')}**: {issue.claim}")
                st.write(f"**{t('growth.flag_reason')}**: {issue.reason}")
                st.write(f"**{t('growth.revised')}**: {issue.recommended_action}")


def render_campaign_editor(campaign: MarketingCampaign) -> tuple[dict[str, str], str | None]:
    st.markdown(f"### 5. {t('growth.assets_title')}")
    edits: dict[str, str] = {}
    regenerate_asset_id: str | None = None
    tabs = st.tabs(tuple(asset.channel for asset in campaign.assets))
    for tab, asset in zip(tabs, campaign.assets, strict=True):
        with tab:
            if asset.raw_ai_content and asset.revised_ai_content:
                st.caption(t("growth.raw_preserved"))
            st.code(asset.display_content, language=None)
            edits[asset.asset_id] = st.text_area(
                t("growth.final_content", channel=asset.channel),
                value=asset.display_content,
                height=180,
                key=f"growth_asset_edit_{campaign.campaign_id}_{asset.asset_id}",
            )
            st.caption(f"{t('growth.strategy.cta')}: {asset.cta}")
            if asset.source_references:
                st.caption(f"{t('growth.sources')}: " + " · ".join(asset.source_references))
            if st.button(
                t("growth.regenerate_channel", channel=asset.channel),
                key=f"growth_regenerate_{campaign.campaign_id}_{asset.asset_id}",
            ):
                regenerate_asset_id = asset.asset_id
    return edits, regenerate_asset_id


def render_campaign_summary(campaign: MarketingCampaign) -> None:
    st.markdown(f"## {t('growth.campaign_ready')}")
    render_status_badge(campaign.status)
    render_metric_strip(
        (
            (t("growth.target"), campaign.target_segment, campaign.target_geography),
            (t("growth.assets_count"), str(len(campaign.assets)), None),
            (t("growth.claims_count"), str(len(campaign.guardian_review.supported_claims)), None),
            (
                t("growth.revisions_count"),
                str(campaign.revision_count),
                status_label(campaign.guardian_review.risk_level),
            ),
        )
    )
    st.caption(f"{escape(campaign.campaign_name)} · {campaign.source.value}")


def render_growth_studio_app(
    contexts: Mapping[str, GrowthProductContext],
    repository: CampaignRepository,
    client_factory: Callable[[GrowthOutputSource], GrowthModelClient | None],
) -> None:
    """Render the complete Growth Studio while domain work stays in services."""
    render_growth_hero()
    if not contexts:
        render_empty_state(t("growth.campaign_empty_title"), t("common.no_campaigns"))
        return
    product_ids = tuple(contexts)
    st.markdown(f"### {t('growth.select_product')}")
    selected_id = st.selectbox(
        "选择产品 / Select product",
        product_ids,
        format_func=lambda value: (
            f"{_product_name(contexts[value])} · {contexts[value].publication_status.value}"
        ),
        key="growth_selected_product_id",
        label_visibility="collapsed",
    )
    context = contexts[selected_id]
    render_product_context(context)
    _render_saved_campaigns(context, repository)
    _render_growth_request(context, client_factory)
    _render_active_campaign(context, repository, client_factory)


def _render_saved_campaigns(
    context: GrowthProductContext,
    repository: CampaignRepository,
) -> None:
    saved = repository.list_for_artisan(context.artisan_id)
    if not saved:
        render_empty_state(t("growth.campaign_empty_title"), t("common.no_campaigns"))
        return
    saved_by_id = {campaign.campaign_id: campaign for campaign in saved}
    st.markdown(f"### {t('growth.saved_campaigns')}")
    saved_id = st.selectbox(
        "Saved campaigns",
        ("", *saved_by_id),
        format_func=lambda value: (
            t("growth.select_saved")
            if not value
            else f"{saved_by_id[value].campaign_name} · {status_label(saved_by_id[value].status)}"
        ),
        key=f"growth_saved_campaign_{context.artisan_id}",
        label_visibility="collapsed",
    )
    if saved_id and st.button(t("growth.open_saved"), key="growth_open_saved"):
        campaign = saved_by_id[saved_id]
        state = _restored_growth_state(campaign, context)
        st.session_state["growth_campaign"] = campaign
        st.session_state["growth_context"] = context
        st.session_state["growth_run_state"] = state
        st.session_state["growth_execution_trace"] = state.trace_events
        st.rerun()


def _render_growth_request(
    context: GrowthProductContext,
    client_factory: Callable[[GrowthOutputSource], GrowthModelClient | None],
) -> None:
    st.markdown(f"### {t('growth.goal_title')}")
    with st.form("growth_studio_request", border=True):
        goal = st.text_area(
            t("growth.goal"),
            value=t("growth.goal_example"),
            height=100,
        )
        geography = st.text_input(t("growth.target_market"), value="United States")
        audience = st.text_input(t("growth.audience"), value="Corporate gift buyers")
        channels = st.multiselect(
            t("growth.channels"),
            ("LinkedIn", "Instagram", "Xiaohongshu", "Email Outreach", "Landing Page"),
            default=("LinkedIn", "Instagram", "Email Outreach", "Landing Page"),
        )
        language = st.selectbox(
            t("growth.campaign_language"),
            ("Chinese", "English", "Bilingual"),
            index=1,
            format_func=lambda item: {
                "Chinese": t("language.zh"),
                "English": t("language.en"),
                "Bilingual": t("language.bilingual"),
            }[item],
        )
        st.caption(t("growth.interface_language_hint"))
        output_source = st.selectbox(
            t("growth.generation_mode"),
            (
                GrowthOutputSource.DETERMINISTIC_DEMO,
                GrowthOutputSource.LIVE_AI,
                GrowthOutputSource.SAFE_FALLBACK,
            ),
            format_func=lambda item: {
                GrowthOutputSource.DETERMINISTIC_DEMO: t("growth.mode_demo"),
                GrowthOutputSource.LIVE_AI: t("growth.mode_live"),
                GrowthOutputSource.SAFE_FALLBACK: t("growth.mode_safe"),
            }[item],
        )
        instructions = st.text_area(t("growth.instructions"), height=80)
        demo_guardian = st.checkbox(
            t("growth.demo_fixture"),
            value=True,
            help=t("growth.demo_fixture_help"),
        )
        run_clicked = st.form_submit_button(
            t("growth.run"),
            type="primary",
            width="stretch",
        )
    if not run_clicked:
        return
    request = GrowthRunRequest(
        artisan_id=context.artisan_id,
        product_id=context.product_id,
        campaign_goal=goal,
        target_geography=geography or None,
        optional_target_audience=audience or None,
        preferred_channels=tuple(channels),
        language=language,
        user_instructions=instructions or None,
        output_source=output_source,
        demo_guardian_scenario=(
            demo_guardian and output_source is GrowthOutputSource.DETERMINISTIC_DEMO
        ),
    )
    try:
        with st.status(t("growth.loading.title"), expanded=True) as status:
            st.write(t("growth.loading.context"))
            st.write(t("growth.loading.market"))
            st.write(t("growth.loading.strategy"))
            st.write(t("growth.loading.creative"))
            st.write(t("growth.loading.guardian"))
            state, campaign = run_growth_workflow(
                request,
                context,
                client=client_factory(output_source),
            )
            status.update(label=t("growth.completed"), state="complete", expanded=False)
    except (RuntimeError, ValueError):
        st.info(t("common.safe_error"))
        return
    st.session_state["growth_context"] = context
    st.session_state["growth_run_state"] = state
    st.session_state["growth_campaign"] = campaign
    st.session_state["growth_execution_trace"] = state.trace_events
    if st.session_state.get("competition_demo"):
        st.session_state["competition_demo_step"] = 5
    st.rerun()


def _render_active_campaign(
    context: GrowthProductContext,
    repository: CampaignRepository,
    client_factory: Callable[[GrowthOutputSource], GrowthModelClient | None],
) -> None:
    campaign = st.session_state.get("growth_campaign")
    state = st.session_state.get("growth_run_state")
    active_context = st.session_state.get("growth_context")
    if not (
        isinstance(campaign, MarketingCampaign)
        and isinstance(state, GrowthRunState)
        and active_context == context
        and campaign.product_id == context.product_id
    ):
        return
    render_campaign_summary(campaign)
    if state.request.demo_guardian_scenario:
        st.info(t("growth.demo_fixture_active"))
    render_growth_trace(state)
    render_market_analysis(campaign)
    render_strategy(campaign.strategy)
    render_guardian(campaign)
    edits, regenerate_asset_id = render_campaign_editor(campaign)
    if regenerate_asset_id:
        try:
            campaign = regenerate_campaign_asset(
                campaign,
                state,
                regenerate_asset_id,
                client=client_factory(state.request.output_source),
            )
        except ValueError:
            st.info(t("common.safe_error"))
            return
        st.session_state["growth_campaign"] = campaign
        st.session_state["growth_execution_trace"] = campaign.trace_events
        st.rerun()
    reviewed_warnings = _render_warning_acknowledgement(campaign)
    if st.button(t("growth.save_campaign"), type="primary", key="growth_save_campaign"):
        updated = update_campaign_with_human_edits(
            campaign,
            edits,
            reviewed_warnings=reviewed_warnings,
        )
        try:
            repository.save(updated)
        except RuntimeError:
            st.info(t("growth.storage_error"))
            return
        st.session_state["growth_campaign"] = updated
        st.success(t("growth.saved"))


def _render_warning_acknowledgement(campaign: MarketingCampaign) -> tuple[str, ...]:
    if not campaign.guardian_review.issues:
        return ()
    acknowledged = st.checkbox(
        t("growth.warning_ack"),
        key=f"growth_warning_review_{campaign.campaign_id}",
    )
    if not acknowledged:
        return ()
    return tuple(
        f"{issue.asset_id}:{issue.issue_type}" for issue in campaign.guardian_review.issues
    )


def _restored_growth_state(
    campaign: MarketingCampaign,
    context: GrowthProductContext,
) -> GrowthRunState:
    request = GrowthRunRequest(
        artisan_id=campaign.artisan_id,
        product_id=campaign.product_id,
        campaign_goal=campaign.goal,
        target_geography=campaign.target_geography,
        preferred_channels=campaign.strategy.recommended_channels,
        output_source=campaign.source,
    )
    return GrowthRunState(
        run_id=f"restored_{campaign.campaign_id}",
        request=request,
        product_context=context,
        status=(
            GrowthRunStatus.READY
            if campaign.guardian_review.approved
            else GrowthRunStatus.NEEDS_REVIEW
        ),
        market_analysis=campaign.market_analysis,
        strategy=campaign.strategy,
        campaign_assets=campaign.assets,
        guardian_review=campaign.guardian_review,
        revision_count=campaign.revision_count,
        trace_events=campaign.trace_events,
    )


def _display_value(value: object) -> str:
    if isinstance(value, (tuple, list, set, frozenset)):
        return ", ".join(str(item) for item in value)
    return str(value)


__all__ = [
    "render_campaign_editor",
    "render_campaign_summary",
    "render_growth_hero",
    "render_growth_trace",
    "render_growth_studio_app",
    "render_guardian",
    "render_market_analysis",
    "render_product_context",
    "render_strategy",
]
