from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from heritagelink.agent_registry import GROWTH_SKILL_REGISTRY, SKILL_REGISTRY
from heritagelink.campaign_service import create_campaign_repository
from heritagelink.growth_agents import (
    analyze_market_opportunities,
    build_marketing_strategy,
    generate_campaign_assets,
    review_campaign_grounding,
)
from heritagelink.growth_models import (
    CampaignAsset,
    CampaignClaim,
    CampaignStatus,
    EvidenceStatus,
    GroundedFact,
    GrowthOutputSource,
    GrowthProductContext,
    GrowthRunRequest,
    GrowthRunStatus,
    GuardianIssue,
    GuardianReview,
    GuardianRiskLevel,
    MarketingCampaign,
    MarketOpportunity,
)
from heritagelink.growth_orchestrator import (
    run_growth_workflow,
    update_campaign_with_human_edits,
)
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.repositories.memory_campaign_repository import MemoryCampaignRepository
from heritagelink.repositories.sqlite_campaign_repository import SQLiteCampaignRepository

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


def _verified(field_name: str, value: object) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=EvidenceStatus.VERIFIED,
        source=FactSource.PUBLIC_SOURCE,
        verification_status=VerificationStatus.CONFIRMED,
        source_note="test verified fact",
    )


def _unverified(field_name: str, value: object) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=EvidenceStatus.UNVERIFIED,
        source=FactSource.UNKNOWN,
        verification_status=VerificationStatus.PENDING_REVIEW,
        source_note="test pending fact",
    )


def _context(
    *,
    publication_status: PublicationStatus = PublicationStatus.RECOMMENDABLE,
    include_customization: bool = True,
) -> GrowthProductContext:
    verified = [
        _verified("product_name", "Wuhu Iron Painting Welcome Pine"),
        _verified("craft_name", "Wuhu iron painting"),
        _verified("occasion_tags", ("business_gift", "commemoration")),
        _verified("recipient_tags", ("business_partner", "institution")),
        _verified("style_tags", ("elegant", "traditional")),
    ]
    if include_customization:
        verified.append(_verified("customization", ("inscription",)))
    return GrowthProductContext(
        artisan_id="artisan_001",
        product_id="product_001",
        product_name="Wuhu Iron Painting Welcome Pine",
        product_name_en="Wuhu Iron Painting Welcome Pine",
        craft_name="Wuhu iron painting",
        publication_status=publication_status,
        verified_facts=tuple(verified),
        unverified_facts=(
            _unverified("international_shipping", True),
            _unverified("lead_time_days", 30),
        ),
        unknown_fields=("quantity_capacity", "price_min_fen", "certification"),
        cultural_source_urls=("https://example.org/cultural-source",),
    )


def _request(
    *,
    source: GrowthOutputSource = GrowthOutputSource.DETERMINISTIC_DEMO,
    demo_guardian_scenario: bool = False,
) -> GrowthRunRequest:
    return GrowthRunRequest(
        artisan_id="artisan_001",
        product_id="product_001",
        campaign_goal="Generate qualified corporate gifting inquiries",
        target_geography="United States",
        preferred_channels=("LinkedIn", "Instagram", "Email Outreach", "Landing Page"),
        language="English",
        output_source=source,
        demo_guardian_scenario=demo_guardian_scenario,
    )


class _MalformedGrowthClient:
    def analyze_growth_market(self, payload):  # type: ignore[no-untyped-def]
        return {"opportunities": "not-a-list"}

    def build_growth_strategy(self, payload):  # type: ignore[no-untyped-def]
        return {"campaign_goal": None}

    def generate_growth_campaign(self, payload):  # type: ignore[no-untyped-def]
        return {"assets": "not-a-list"}


def test_market_intelligence_returns_structured_product_grounded_opportunities() -> None:
    analysis = analyze_market_opportunities(_context(), _request())

    assert len(analysis.opportunities) >= 3
    assert analysis.recommended_segment == "Corporate Gifts"
    assert analysis.external_evidence_used is False
    assert "not externally validated market research" in analysis.summary
    assert any("shipping" in risk.casefold() for risk in analysis.opportunities[0].risks)


def test_market_intelligence_handles_missing_optional_fields_and_unknowns() -> None:
    context = _context(include_customization=False)
    request = replace(_request(), target_geography=None, optional_target_audience=None)

    analysis = analyze_market_opportunities(context, request)

    assert analysis.opportunities
    assert any(
        "customization" in risk.casefold()
        for opportunity in analysis.opportunities
        for risk in opportunity.risks
    )


def test_market_opportunity_validates_structured_score_range() -> None:
    with pytest.raises(ValueError):
        MarketOpportunity("Invalid", 101, (), ())


def test_strategy_is_downstream_and_does_not_promote_unverified_shipping() -> None:
    context = _context()
    request = replace(_request(), target_geography=None)
    analysis = analyze_market_opportunities(context, request)

    strategy = build_marketing_strategy(context, request, analysis)

    assert strategy.campaign_goal == request.campaign_goal
    assert strategy.recommended_channels == request.preferred_channels
    assert "shipping" not in " ".join(strategy.key_messages).casefold()
    assert any("shipping" in risk.casefold() for risk in strategy.risks)


def test_creative_generates_multiple_channels_from_verified_facts_only() -> None:
    context = _context(include_customization=False)
    request = _request()
    analysis = analyze_market_opportunities(context, request)
    strategy = build_marketing_strategy(context, request, analysis)

    assets = generate_campaign_assets(context, request, analysis, strategy)

    assert {asset.channel for asset in assets} == set(request.preferred_channels)
    assert all(asset.raw_ai_content for asset in assets)
    assert all(
        claim.evidence_status is EvidenceStatus.VERIFIED
        for asset in assets
        for claim in asset.claims
    )
    public_copy = " ".join(asset.content for asset in assets).casefold()
    assert "guaranteed delivery" not in public_copy
    assert "officially certified" not in public_copy


def test_malformed_live_model_output_uses_safe_deterministic_fallback() -> None:
    context = _context()
    request = _request(source=GrowthOutputSource.LIVE_AI)
    client = _MalformedGrowthClient()

    analysis = analyze_market_opportunities(context, request, client=client)
    strategy = build_marketing_strategy(context, request, analysis, client=client)
    assets = generate_campaign_assets(context, request, analysis, strategy, client=client)

    assert analysis.source is GrowthOutputSource.SAFE_FALLBACK
    assert strategy.source is GrowthOutputSource.SAFE_FALLBACK
    assert assets


def test_live_mode_without_client_has_safe_no_model_fallback() -> None:
    analysis = analyze_market_opportunities(
        _context(),
        _request(source=GrowthOutputSource.LIVE_AI),
        client=None,
    )

    assert analysis.source is GrowthOutputSource.SAFE_FALLBACK


def test_guardian_approves_supported_claims() -> None:
    asset = CampaignAsset(
        "linkedin_01",
        "LinkedIn",
        "post",
        "Discover Wuhu Iron Painting Welcome Pine.",
        "Request details",
        (
            CampaignClaim(
                "Wuhu Iron Painting Welcome Pine",
                "product_name",
                EvidenceStatus.VERIFIED,
            ),
        ),
    )

    review = review_campaign_grounding(_context(), (asset,))

    assert review.approved
    assert review.supported_claims == ("Wuhu Iron Painting Welcome Pine",)


@pytest.mark.parametrize(
    ("content", "field_name", "issue_type"),
    (
        (
            "An officially certified national master work.",
            "certification",
            "fabricated_certification",
        ),
        (
            "Guaranteed international delivery for every order.",
            "international_shipping",
            "fabricated_logistics_claim",
        ),
        (
            "A thousand-year-old tradition.",
            "cultural_history_age",
            "unsupported_cultural_claim",
        ),
        (
            "Crafted from pure iron for a premium finish.",
            "materials",
            "unsupported_product_claim",
        ),
    ),
)
def test_guardian_rejects_fabricated_and_unsupported_claims(
    content: str,
    field_name: str,
    issue_type: str,
) -> None:
    asset = CampaignAsset(
        "linkedin_01",
        "LinkedIn",
        "post",
        content,
        "Request details",
        (CampaignClaim(content, field_name, EvidenceStatus.UNVERIFIED),),
    )

    review = review_campaign_grounding(_context(), (asset,))

    assert not review.approved
    assert issue_type in {issue.issue_type for issue in review.issues}


def test_revision_loop_rejects_then_revises_then_approves() -> None:
    state, campaign = run_growth_workflow(
        _request(demo_guardian_scenario=True),
        _context(),
        now=NOW,
    )

    assert state.status is GrowthRunStatus.READY
    assert campaign.status is CampaignStatus.READY
    assert campaign.revision_count == 1
    assert campaign.guardian_review.approved
    assert any(asset.revised_ai_content for asset in campaign.assets)
    assert (
        "officially certified"
        not in " ".join(asset.content for asset in campaign.assets).casefold()
    )
    assert [trace.skill_id for trace in state.trace_events][-3:] == [
        "review_campaign_grounding",
        "revise_campaign_assets",
        "review_campaign_grounding",
    ]


def test_revision_loop_stops_safely_after_two_revisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejected = GuardianReview(
        approved=False,
        risk_level=GuardianRiskLevel.HIGH,
        issues=(
            GuardianIssue(
                "linkedin_01",
                "fabricated_certification",
                "officially certified",
                "No source supports this claim",
                None,
                "Remove the claim",
            ),
        ),
        supported_claims=(),
        revision_instructions=("Remove the claim",),
        reviewed_asset_ids=("linkedin_01",),
    )
    monkeypatch.setattr(
        "heritagelink.skills.campaign_guardian_skill.execute",
        lambda context, assets: rejected,
    )

    state, campaign = run_growth_workflow(_request(), _context(), now=NOW)

    assert state.status is GrowthRunStatus.NEEDS_REVIEW
    assert campaign.status is CampaignStatus.NEEDS_REVIEW
    assert campaign.revision_count == 2
    assert not campaign.guardian_review.approved
    assert sum(trace.skill_id == "review_campaign_grounding" for trace in state.trace_events) == 3


def test_campaign_memory_and_sqlite_repositories_save_load_and_update(tmp_path: Path) -> None:
    _, campaign = run_growth_workflow(_request(), _context(), now=NOW)
    updated = update_campaign_with_human_edits(
        campaign,
        {campaign.assets[0].asset_id: "Human edited final campaign copy."},
        now=NOW,
    )
    assert updated.status is CampaignStatus.NEEDS_REVIEW
    assert updated.assets[0].raw_ai_content
    assert updated.assets[0].final_human_content == "Human edited final campaign copy."

    for repository in (
        MemoryCampaignRepository(),
        SQLiteCampaignRepository(tmp_path / "growth.sqlite3"),
    ):
        repository.save(campaign)
        repository.save(updated)
        assert repository.get(campaign.campaign_id) == updated
        assert repository.list_for_artisan(campaign.artisan_id) == (updated,)


def test_campaign_repository_factory_supports_memory_and_sqlite(tmp_path: Path) -> None:
    memory = create_campaign_repository(None)
    sqlite = create_campaign_repository(f"sqlite:///{(tmp_path / 'factory.sqlite3').as_posix()}")

    assert isinstance(memory, MemoryCampaignRepository)
    assert isinstance(sqlite, SQLiteCampaignRepository)
    with pytest.raises(ValueError):
        create_campaign_repository("json:///campaigns.json")


def test_growth_campaign_does_not_change_draft_publication_boundary() -> None:
    context = _context(publication_status=PublicationStatus.PENDING_REVIEW)
    _, campaign = run_growth_workflow(_request(), context, now=NOW)

    assert context.publication_status is PublicationStatus.PENDING_REVIEW
    assert campaign.product_id == context.product_id
    assert any("Draft campaign" in asset.content for asset in campaign.assets)


def test_growth_manifest_matches_separate_registry_and_preserves_buyer_skills() -> None:
    manifest = yaml.safe_load(
        (ROOT / "docs" / "wave4" / "growth_agent_manifest.yaml").read_text(encoding="utf-8")
    )

    assert len(SKILL_REGISTRY) == 7
    assert [item["id"] for item in manifest["skills"]] == [
        item.skill_id for item in GROWTH_SKILL_REGISTRY
    ]
    assert manifest["maximum_automatic_revisions"] == 2
    assert manifest["safety"]["campaign_changes_publication_status"] is False


def test_growth_studio_streamlit_flow_runs_real_orchestrator() -> None:
    app = AppTest.from_file(ROOT / "app.py")
    app.query_params["mode"] = "artisan"
    app = app.run(timeout=30)
    [button for button in app.button if button.label == "Growth Studio"][0].click().run(timeout=30)

    assert not app.exception
    assert app.session_state["artisan_workspace"] == "growth"
    assert [item for item in app.selectbox if item.label == "选择产品 / Select product"]

    [button for button in app.button if button.label == "Run HAHA Growth Team"][0].click().run(
        timeout=30
    )

    assert not app.exception
    assert isinstance(app.session_state["growth_campaign"], MarketingCampaign)
    assert app.session_state["growth_run_state"].status is GrowthRunStatus.READY
    text = "\n".join(str(item.value) for item in (*app.markdown, *app.info, *app.success))
    assert "Market Opportunities" in text
    assert "Cultural Guardian" in text

    campaign_id = app.session_state["growth_campaign"].campaign_id
    [button for button in app.button if button.label == "Save campaign"][0].click().run(timeout=30)
    app = app.run(timeout=30)
    saved_select = [item for item in app.selectbox if item.label == "Saved campaigns"][0]
    app = saved_select.set_value(campaign_id).run(timeout=30)
    [button for button in app.button if button.label == "Open saved campaign"][0].click().run(
        timeout=30
    )

    assert not app.exception
    assert app.session_state["growth_campaign"].campaign_id == campaign_id
