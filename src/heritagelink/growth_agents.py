"""Specialist Growth Studio capabilities with deterministic safe fallbacks."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Protocol

from heritagelink.growth_grounding import public_claim_value
from heritagelink.growth_models import (
    CampaignAsset,
    CampaignClaim,
    EvidenceStatus,
    GrowthOutputSource,
    GrowthProductContext,
    GrowthRunRequest,
    GuardianIssue,
    GuardianReview,
    GuardianRiskLevel,
    MarketAnalysis,
    MarketingStrategy,
    MarketOpportunity,
)

DEFAULT_CHANNELS = ("LinkedIn", "Instagram", "Email Outreach", "Landing Page")
SUPPORTED_CHANNELS = (
    "LinkedIn",
    "Instagram",
    "Xiaohongshu",
    "Email Outreach",
    "Landing Page",
)


class GrowthModelClient(Protocol):
    def analyze_growth_market(self, payload: dict[str, object]) -> dict[str, object]: ...

    def build_growth_strategy(self, payload: dict[str, object]) -> dict[str, object]: ...

    def generate_growth_campaign(self, payload: dict[str, object]) -> dict[str, object]: ...


def analyze_market_opportunities(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    *,
    client: GrowthModelClient | None = None,
) -> MarketAnalysis:
    """Assess product-grounded opportunities without claiming external market research."""
    if request.output_source is GrowthOutputSource.LIVE_AI and client is not None:
        try:
            payload = client.analyze_growth_market(_growth_payload(context, request))
            return _parse_market_analysis(payload, GrowthOutputSource.LIVE_AI)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return _deterministic_market_analysis(
                context,
                request,
                source=GrowthOutputSource.SAFE_FALLBACK,
            )
    source = (
        GrowthOutputSource.SAFE_FALLBACK
        if request.output_source is GrowthOutputSource.LIVE_AI
        else request.output_source
    )
    return _deterministic_market_analysis(context, request, source=source)


def build_marketing_strategy(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    analysis: MarketAnalysis,
    *,
    client: GrowthModelClient | None = None,
) -> MarketingStrategy:
    """Build strategy after market assessment; Creative cannot choose positioning."""
    if request.output_source is GrowthOutputSource.LIVE_AI and client is not None:
        try:
            payload = client.build_growth_strategy(
                {
                    **_growth_payload(context, request),
                    "market_analysis": _market_payload(analysis),
                }
            )
            return _parse_strategy(payload, GrowthOutputSource.LIVE_AI)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return _deterministic_strategy(
                context,
                request,
                analysis,
                source=GrowthOutputSource.SAFE_FALLBACK,
            )
    source = (
        GrowthOutputSource.SAFE_FALLBACK
        if request.output_source is GrowthOutputSource.LIVE_AI
        else request.output_source
    )
    return _deterministic_strategy(context, request, analysis, source=source)


def generate_campaign_assets(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    analysis: MarketAnalysis,
    strategy: MarketingStrategy,
    *,
    client: GrowthModelClient | None = None,
) -> tuple[CampaignAsset, ...]:
    """Generate one coordinated multi-channel campaign from verified evidence only."""
    if request.output_source is GrowthOutputSource.LIVE_AI and client is not None:
        try:
            payload = client.generate_growth_campaign(
                {
                    **_growth_payload(context, request),
                    "market_analysis": _market_payload(analysis),
                    "strategy": _strategy_payload(strategy),
                }
            )
            return _parse_assets(payload, context)
        except (KeyError, TypeError, ValueError, RuntimeError):
            return _deterministic_assets(
                context,
                request,
                strategy,
                source=GrowthOutputSource.SAFE_FALLBACK,
            )
    source = (
        GrowthOutputSource.SAFE_FALLBACK
        if request.output_source is GrowthOutputSource.LIVE_AI
        else request.output_source
    )
    return _deterministic_assets(context, request, strategy, source=source)


def review_campaign_grounding(
    context: GrowthProductContext,
    assets: tuple[CampaignAsset, ...],
) -> GuardianReview:
    """Reject unsupported product, artisan, cultural, and commercial claims."""
    verified_fields = set(context.verified_by_name)
    if context.cultural_source_urls:
        verified_fields.add("source_availability")
    issues: list[GuardianIssue] = []
    supported: list[str] = []
    for asset in assets:
        for claim in asset.claims:
            field_supported = claim.field_name in verified_fields if claim.field_name else False
            if claim.evidence_status is EvidenceStatus.VERIFIED and field_supported:
                supported.append(claim.claim_text)
            else:
                issues.append(
                    GuardianIssue(
                        asset_id=asset.asset_id,
                        issue_type=_unsupported_issue_type(claim.field_name),
                        claim=claim.claim_text,
                        reason=(
                            "The claim is not supported by a confirmed field in the current "
                            "Heritage Passport context."
                        ),
                        source=claim.source_url,
                        recommended_action="Remove the claim or replace it with verified wording.",
                    )
                )
        issues.extend(_scan_asset_text(asset, context, existing=issues))

    issues = _unique_issues(issues)
    if not issues:
        return GuardianReview(
            approved=True,
            risk_level=GuardianRiskLevel.NONE,
            issues=(),
            supported_claims=tuple(dict.fromkeys(supported)),
            revision_instructions=(),
            reviewed_asset_ids=tuple(asset.asset_id for asset in assets),
        )
    high_risk_types = {
        "fabricated_certification",
        "fabricated_artisan_identity",
        "fabricated_logistics_claim",
    }
    risk = (
        GuardianRiskLevel.HIGH
        if any(issue.issue_type in high_risk_types for issue in issues)
        else GuardianRiskLevel.MEDIUM
    )
    instructions = tuple(
        dict.fromkeys(
            f"{issue.asset_id}: {issue.recommended_action} Rejected claim: {issue.claim}"
            for issue in issues
        )
    )
    return GuardianReview(
        approved=False,
        risk_level=risk,
        issues=tuple(issues),
        supported_claims=tuple(dict.fromkeys(supported)),
        revision_instructions=instructions,
        reviewed_asset_ids=tuple(asset.asset_id for asset in assets),
    )


def revise_campaign_assets(
    context: GrowthProductContext,
    strategy: MarketingStrategy,
    assets: tuple[CampaignAsset, ...],
    review: GuardianReview,
) -> tuple[CampaignAsset, ...]:
    """Apply Guardian instructions while preserving the original AI version."""
    issues_by_asset: dict[str, list[GuardianIssue]] = {}
    for issue in review.issues:
        issues_by_asset.setdefault(issue.asset_id, []).append(issue)
    revised: list[CampaignAsset] = []
    for asset in assets:
        issues = issues_by_asset.get(asset.asset_id, [])
        if not issues:
            revised.append(asset)
            continue
        unsafe_claims = {issue.claim for issue in issues}
        content = _remove_unsafe_sentences(asset.content, unsafe_claims)
        if not content.strip():
            safe_name = str(public_claim_value(context, "product_name") or "This artisan product")
            content = f"Explore {safe_name}. {strategy.cta}"
        safe_claims = tuple(
            claim
            for claim in asset.claims
            if claim.claim_text not in unsafe_claims
            and claim.evidence_status is EvidenceStatus.VERIFIED
            and claim.field_name in context.verified_by_name | {"source_availability": None}
        )
        revised.append(
            replace(
                asset,
                content=content.strip(),
                claims=safe_claims,
                raw_ai_content=asset.raw_ai_content or asset.content,
                revised_ai_content=content.strip(),
            )
        )
    return tuple(revised)


def apply_human_edits(
    assets: tuple[CampaignAsset, ...],
    edits: dict[str, str],
) -> tuple[CampaignAsset, ...]:
    """Keep the AI versions and store a separate human-edited final version."""
    return tuple(
        replace(asset, final_human_content=edits[asset.asset_id].strip())
        if asset.asset_id in edits and edits[asset.asset_id].strip()
        else asset
        for asset in assets
    )


def _deterministic_market_analysis(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    *,
    source: GrowthOutputSource,
) -> MarketAnalysis:
    verified = context.verified_by_name
    occasion_tags = _values(verified.get("occasion_tags"))
    recipient_tags = _values(verified.get("recipient_tags"))
    style_tags = _values(verified.get("style_tags"))
    source_reason = (
        "A verified public cultural source supports source-aware storytelling."
        if context.cultural_source_urls
        else "Campaign wording must remain generic because cultural sources need review."
    )
    common_risks = _commercial_risks(context, request.target_geography)

    corporate_score = 68
    corporate_reasons = ["The product can be positioned as a distinctive cultural gift concept."]
    if "business_gift" in occasion_tags or "business_partner" in recipient_tags:
        corporate_score += 16
        corporate_reasons.append("Structured catalogue tags support business-gifting scenarios.")
    if public_claim_value(context, "customization"):
        corporate_score += 8
        corporate_reasons.append("Confirmed customization supports organizational gifting needs.")
    corporate_reasons.append(source_reason)

    decor_score = 66 + (8 if {"elegant", "traditional", "grand"} & set(style_tags) else 0)
    culture_score = 64 + (12 if context.cultural_source_urls else 0)
    opportunities = (
        MarketOpportunity(
            "Corporate Gifts",
            min(corporate_score, 96),
            tuple(corporate_reasons),
            common_risks,
        ),
        MarketOpportunity(
            "Cultural Home Decor",
            min(decor_score, 92),
            (
                "The object-led format can support visual storytelling and display-oriented copy.",
                source_reason,
            ),
            tuple(
                risk
                for risk in common_risks
                if "capacity" not in risk.casefold() and "quantity" not in risk.casefold()
            ),
        ),
        MarketOpportunity(
            "University / Museum Gifting",
            min(culture_score, 90),
            (
                "The source-aware narrative is suitable for educational and cultural contexts.",
                "The campaign can foreground learning and exchange without claiming endorsement.",
            ),
            (*common_risks, "No museum, university, or institutional endorsement is verified."),
        ),
    )
    recommended = max(opportunities, key=lambda item: (item.fit_score, item.segment))
    geography = request.target_geography or "the selected geography"
    return MarketAnalysis(
        opportunities=opportunities,
        recommended_segment=recommended.segment,
        summary=(
            f"{recommended.segment} is the strongest product-grounded scenario for {geography}. "
            "This is an AI opportunity assessment, not externally validated market research."
        ),
        evidence_basis="Verified product context and deterministic catalogue tags only",
        external_evidence_used=False,
        source=source,
    )


def _deterministic_strategy(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    analysis: MarketAnalysis,
    *,
    source: GrowthOutputSource,
) -> MarketingStrategy:
    segment = analysis.recommended_segment
    target_audience = (
        (request.optional_target_audience.strip(),)
        if request.optional_target_audience and request.optional_target_audience.strip()
        else _default_audience(segment)
    )
    channels = _normalize_channels(request.preferred_channels) or DEFAULT_CHANNELS
    product_name = str(public_claim_value(context, "product_name") or "the artisan product")
    craft_name = public_claim_value(context, "craft_name")
    source_message = (
        "Use source-aware cultural context and link to the available reference."
        if context.cultural_source_urls
        else "Keep cultural wording general until source review is complete."
    )
    key_messages = [f"Present {product_name} as a considered cultural gifting concept."]
    if craft_name:
        key_messages.append(f"Explain the work through its confirmed craft context: {craft_name}.")
    if public_claim_value(context, "customization"):
        key_messages.append("Invite buyers to discuss the confirmed customization options.")
    key_messages.append(source_message)
    geography = request.target_geography or "the intended market"
    risks = tuple(
        dict.fromkeys((*_commercial_risks(context, geography), *analysis.opportunities[0].risks))
    )
    return MarketingStrategy(
        campaign_goal=request.campaign_goal,
        target_audience=target_audience,
        positioning=(
            f"A source-aware artisan product for {segment.casefold()}, presented with cultural "
            "context and clear confirmation boundaries."
        ),
        value_proposition=(
            "Combine a distinctive object, understandable cultural context, and a low-friction "
            "path to a qualified inquiry without making unverified commercial promises."
        ),
        key_messages=tuple(key_messages),
        content_angles=(
            "The story behind the object",
            "A thoughtful alternative to generic gifting",
            "How to begin a customization or sourcing conversation",
        ),
        recommended_channels=channels,
        cta="Request verified product and customization details",
        risks=risks,
        things_to_avoid=(
            "Official heritage, certification, award, or master-artisan claims without evidence",
            "Exact price, inventory, capacity, lead-time, or shipping promises unless confirmed",
            "Superlatives, invented historical ages, and exoticized cultural language",
        ),
        reasoning_summary=(
            f"Strategy follows the {segment} opportunity selected before Creative generation; "
            "Creative may execute but cannot change this positioning."
        ),
        source=source,
    )


def _deterministic_assets(
    context: GrowthProductContext,
    request: GrowthRunRequest,
    strategy: MarketingStrategy,
    *,
    source: GrowthOutputSource,
) -> tuple[CampaignAsset, ...]:
    del source
    product_name = str(public_claim_value(context, "product_name") or "This artisan product")
    craft_name = public_claim_value(context, "craft_name")
    source_phrase = (
        "Its campaign story is linked to a reviewed public cultural reference."
        if context.cultural_source_urls
        else "Cultural details remain subject to source review."
    )
    craft_phrase = (
        f" It is presented through the confirmed craft context of {craft_name}."
        if craft_name
        else ""
    )
    base_claims = [
        CampaignClaim(
            product_name,
            "product_name",
            EvidenceStatus.VERIFIED,
            "canonical product identity",
        )
    ]
    if craft_name:
        base_claims.append(
            CampaignClaim(
                str(craft_name),
                "craft_name",
                EvidenceStatus.VERIFIED,
                "Heritage Passport",
                context.cultural_source_urls[0] if context.cultural_source_urls else None,
            )
        )
    if context.cultural_source_urls:
        base_claims.append(
            CampaignClaim(
                "A public cultural reference is available",
                "source_availability",
                EvidenceStatus.VERIFIED,
                "Heritage Passport source",
                context.cultural_source_urls[0],
            )
        )
    disclaimer = (
        " Draft campaign: product publication and unverified commercial details remain separate."
        if context.requires_draft_label or context.unverified_facts
        else ""
    )
    contents = {
        "LinkedIn": (
            f"Looking for a more meaningful approach to organizational gifting? {product_name} "
            f"offers a culturally grounded starting point.{craft_phrase} {source_phrase} "
            f"{strategy.cta}.{disclaimer}"
        ),
        "Instagram": (
            f"A gift can open a cultural conversation. Discover {product_name}.{craft_phrase} "
            f"{source_phrase} {strategy.cta}.{disclaimer}"
        ),
        "Xiaohongshu": (
            f"把礼物变成一次有依据的文化交流：{product_name}。{source_phrase} "
            f"如需用于海外礼赠，请先咨询并确认产品与定制细节。{disclaimer}"
        ),
        "Email Outreach": (
            f"Subject: A source-aware cultural gifting concept\n\n"
            f"Hello,\n\nWe would like to introduce {product_name} as a possible starting point "
            f"for a thoughtful gifting conversation.{craft_phrase} {source_phrase}\n\n"
            f"{strategy.cta}.\n\nCommercial details will be confirmed before any "
            f"commitment.{disclaimer}"
        ),
        "Landing Page": (
            f"{product_name}\n\nA source-aware artisan product designed for a thoughtful gifting "
            f"conversation.{craft_phrase} {source_phrase}\n\n{strategy.value_proposition}\n\n"
            f"{strategy.cta}.{disclaimer}"
        ),
    }
    channels = _normalize_channels(request.preferred_channels) or strategy.recommended_channels
    assets: list[CampaignAsset] = []
    for index, channel in enumerate(channels, start=1):
        content = contents[channel]
        claims = tuple(base_claims)
        if request.demo_guardian_scenario and index == 1:
            fixture_claim = (
                "A thousand-year-old officially certified tradition, with guaranteed "
                "international delivery."
            )
            content = f"{content} {fixture_claim}"
            claims = (
                *claims,
                CampaignClaim(
                    fixture_claim,
                    "international_shipping",
                    EvidenceStatus.UNVERIFIED,
                    "labelled Guardian revision demo fixture",
                ),
            )
        asset_id = f"{_channel_id(channel)}_{index:02d}"
        assets.append(
            CampaignAsset(
                asset_id=asset_id,
                channel=channel,
                asset_type=_asset_type(channel),
                content=content,
                cta=strategy.cta,
                claims=claims,
                source_references=context.cultural_source_urls,
                raw_ai_content=content,
            )
        )
    return tuple(assets)


def _parse_market_analysis(
    payload: dict[str, object],
    source: GrowthOutputSource,
) -> MarketAnalysis:
    raw_opportunities = payload["opportunities"]
    if not isinstance(raw_opportunities, list):
        raise ValueError("opportunities must be a list")
    opportunities = tuple(
        MarketOpportunity(
            segment=_required_text(item, "segment"),
            fit_score=int(item["fit_score"]),
            reasons=_string_tuple(item.get("reasons")),
            risks=_string_tuple(item.get("risks")),
        )
        for item in raw_opportunities
        if isinstance(item, dict)
    )
    return MarketAnalysis(
        opportunities=opportunities,
        recommended_segment=_required_text(payload, "recommended_segment"),
        summary=_required_text(payload, "summary"),
        evidence_basis="Product-grounded AI opportunity assessment; no external market research",
        external_evidence_used=False,
        source=source,
    )


def _parse_strategy(
    payload: dict[str, object],
    source: GrowthOutputSource,
) -> MarketingStrategy:
    return MarketingStrategy(
        campaign_goal=_required_text(payload, "campaign_goal"),
        target_audience=_string_tuple(payload.get("target_audience")),
        positioning=_required_text(payload, "positioning"),
        value_proposition=_required_text(payload, "value_proposition"),
        key_messages=_string_tuple(payload.get("key_messages")),
        content_angles=_string_tuple(payload.get("content_angles")),
        recommended_channels=_normalize_channels(
            _string_tuple(payload.get("recommended_channels"))
        ),
        cta=_required_text(payload, "cta"),
        risks=_string_tuple(payload.get("risks")),
        things_to_avoid=_string_tuple(payload.get("things_to_avoid")),
        reasoning_summary=_required_text(payload, "reasoning_summary"),
        source=source,
    )


def _parse_assets(
    payload: dict[str, object],
    context: GrowthProductContext,
) -> tuple[CampaignAsset, ...]:
    raw_assets = payload["assets"]
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError("assets must be a non-empty list")
    assets: list[CampaignAsset] = []
    for index, item in enumerate(raw_assets, start=1):
        if not isinstance(item, dict):
            raise ValueError("asset must be an object")
        channel = _normalize_channels((_required_text(item, "channel"),))[0]
        claims = tuple(
            CampaignClaim(
                claim_text=_required_text(claim, "claim_text"),
                field_name=(str(claim["field_name"]) if claim.get("field_name") else None),
                evidence_status=(
                    EvidenceStatus.VERIFIED
                    if claim.get("field_name") in context.verified_by_name
                    else EvidenceStatus.UNVERIFIED
                ),
                source_label="live AI claim mapped to current context",
            )
            for claim in item.get("claims", [])
            if isinstance(claim, dict)
        )
        content = _required_text(item, "content")
        assets.append(
            CampaignAsset(
                asset_id=str(item.get("asset_id") or f"{_channel_id(channel)}_{index:02d}"),
                channel=channel,
                asset_type=str(item.get("asset_type") or _asset_type(channel)),
                content=content,
                cta=str(item.get("cta") or "Request verified details"),
                claims=claims,
                source_references=context.cultural_source_urls,
                raw_ai_content=content,
            )
        )
    return tuple(assets)


def _scan_asset_text(
    asset: CampaignAsset,
    context: GrowthProductContext,
    *,
    existing: list[GuardianIssue],
) -> list[GuardianIssue]:
    patterns = (
        (
            (
                r"\b(?:officially certified|nationally certified|certified heritage|"
                r"national master|government[- ](?:endorsed|recognized))\b"
            ),
            "fabricated_certification",
            "No verified certification, master-artisan status, or government endorsement exists.",
        ),
        (
            r"\b(?:heritage inheritor|master artisan|award[- ]winning artisan)\b",
            "fabricated_artisan_identity",
            "No verified inheritor, master-artisan, award, or identity record supports this claim.",
        ),
        (
            (
                r"\b(?:guaranteed (?:international )?delivery|ships worldwide|"
                r"worldwide shipping guaranteed)\b"
            ),
            "fabricated_logistics_claim",
            "The current context does not verify a guaranteed logistics capability.",
        ),
        (
            (
                r"\b(?:thousand-year-old|thousands of years|the oldest|"
                r"\d{1,2}(?:st|nd|rd|th)[ -]century|\d{3,4}[- ]year[- ]old)\b"
            ),
            "unsupported_cultural_claim",
            "No current source supports this historical age or superlative claim.",
        ),
        (
            r"\b(?:the best|world[- ]famous|number one)\b",
            "marketing_exaggeration",
            "The superlative is unsupported by the current evidence.",
        ),
        (
            r"\b(?:exotic oriental|mystical orient|timeless eastern mystery)\b",
            "cross_cultural_risk",
            "The wording may exoticize or misrepresent Chinese cultural heritage.",
        ),
    )
    output: list[GuardianIssue] = []
    existing_keys = {(issue.asset_id, issue.claim.casefold()) for issue in existing}
    for pattern, issue_type, reason in patterns:
        match = re.search(pattern, asset.content, flags=re.IGNORECASE)
        if match is None or (asset.asset_id, match.group(0).casefold()) in existing_keys:
            continue
        output.append(
            GuardianIssue(
                asset.asset_id,
                issue_type,
                match.group(0),
                reason,
                None,
                "Remove the unsupported wording and use a bounded, source-aware statement.",
            )
        )
    if re.search(r"(?:\$|£|€|¥)\s?\d", asset.content) and not {
        "price_min_fen",
        "price_max_fen",
    } & set(context.verified_by_name):
        output.append(
            GuardianIssue(
                asset.asset_id,
                "unsupported_product_claim",
                "specific public price",
                "Price is not confirmed in the current product context.",
                None,
                "Remove the public price and invite the buyer to request verified details.",
            )
        )
    conditional_patterns = (
        (
            "materials",
            r"\b(?:made|crafted|constructed) (?:from|of|with) [a-z][a-z -]{2,40}\b",
            "unsupported_product_claim",
            "Material composition is not confirmed in the current context.",
        ),
        (
            "dimensions",
            r"\b\d+(?:\.\d+)?\s?(?:cm|mm|inches?|in\.)\b",
            "unsupported_product_claim",
            "Dimensions are not confirmed in the current context.",
        ),
        (
            "customization",
            r"\b(?:customizable|personalized|personalised|logo customization)\b",
            "unsupported_product_claim",
            "Customization capability is not confirmed in the current context.",
        ),
        (
            "quantity_capacity",
            r"\b(?:bulk orders?|up to \d+ units?|large[- ]scale production)\b",
            "unsupported_product_claim",
            "Production capacity is not confirmed in the current context.",
        ),
        (
            "lead_time_days",
            r"\b(?:ready|produced|delivered) in \d+ (?:days?|weeks?)\b",
            "fabricated_logistics_claim",
            "Lead time is not confirmed in the current context.",
        ),
        (
            "packaging",
            r"\b(?:gift box included|premium packaging included)\b",
            "unsupported_product_claim",
            "Packaging is not confirmed in the current context.",
        ),
        (
            "inventory",
            r"\b(?:in stock|available now|ready to ship)\b",
            "unsupported_product_claim",
            "Inventory availability is not confirmed in the current context.",
        ),
    )
    verified_fields = set(context.verified_by_name)
    for field_name, pattern, issue_type, reason in conditional_patterns:
        if field_name in verified_fields:
            continue
        match = re.search(pattern, asset.content, flags=re.IGNORECASE)
        if match is None:
            continue
        output.append(
            GuardianIssue(
                asset.asset_id,
                issue_type,
                match.group(0),
                reason,
                None,
                "Remove the unsupported detail or confirm it before public use.",
            )
        )
    return output


def _remove_unsafe_sentences(content: str, unsafe_claims: set[str]) -> str:
    cleaned = content
    for claim in sorted(unsafe_claims, key=len, reverse=True):
        cleaned = cleaned.replace(claim, "")
    risky = re.compile(
        r"\b(?:officially certified|national master|government[- ]endorsed|guaranteed "
        r"(?:international )?delivery|ships worldwide|thousand-year-old|thousands of years|"
        r"the oldest|the best|world[- ]famous|number one|exotic oriental|mystical orient)\b",
        re.IGNORECASE,
    )
    sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned)
    kept = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip() and not risky.search(sentence)
    ]
    return " ".join(kept)


def _commercial_risks(
    context: GrowthProductContext,
    target_geography: str | None,
) -> tuple[str, ...]:
    risks: list[str] = []
    verified = context.verified_by_name
    if target_geography and "international_shipping" not in verified:
        risks.append(
            "International shipping capability remains unverified for the target geography."
        )
    if "lead_time_days" not in verified:
        risks.append("Production lead time remains unverified.")
    if "quantity_capacity" not in verified:
        risks.append("Production capacity and quantity suitability remain unverified.")
    if "customization" not in verified:
        risks.append("Customization capability must be confirmed before promotion as a feature.")
    return tuple(risks)


def _unsupported_issue_type(field_name: str | None) -> str:
    if field_name in {"certification", "heritage_status", "award"}:
        return "fabricated_certification"
    if field_name in {"artisan_identity", "years_experience", "master_status"}:
        return "fabricated_artisan_identity"
    if field_name in {"international_shipping", "lead_time_days", "quantity_capacity"}:
        return "fabricated_logistics_claim"
    if field_name in {"cultural_history", "cultural_history_age", "symbolism"}:
        return "unsupported_cultural_claim"
    return "unsupported_product_claim"


def _unique_issues(issues: list[GuardianIssue]) -> list[GuardianIssue]:
    output: dict[tuple[str, str, str], GuardianIssue] = {}
    for issue in issues:
        key = (issue.asset_id, issue.issue_type, issue.claim.casefold())
        output[key] = issue
    return list(output.values())


def _growth_payload(
    context: GrowthProductContext,
    request: GrowthRunRequest,
) -> dict[str, object]:
    return {
        "product": {
            "product_id": context.product_id,
            "verified_facts": {fact.field_name: fact.value for fact in context.verified_facts},
            "unknown_fields": context.unknown_fields,
            "source_urls": context.cultural_source_urls,
            "publication_status": context.publication_status.value,
        },
        "campaign_goal": request.campaign_goal,
        "target_geography": request.target_geography,
        "target_audience": request.optional_target_audience,
        "preferred_channels": request.preferred_channels,
        "language": request.language,
        "user_instructions": request.user_instructions,
        "safety_boundary": (
            "Use verified_facts only. Never invent market statistics, certification, identity, "
            "price, inventory, capacity, lead time, customization, or shipping."
        ),
    }


def _market_payload(analysis: MarketAnalysis) -> dict[str, object]:
    return {
        "opportunities": [
            {
                "segment": item.segment,
                "fit_score": item.fit_score,
                "reasons": item.reasons,
                "risks": item.risks,
            }
            for item in analysis.opportunities
        ],
        "recommended_segment": analysis.recommended_segment,
        "summary": analysis.summary,
        "evidence_basis": analysis.evidence_basis,
    }


def _strategy_payload(strategy: MarketingStrategy) -> dict[str, object]:
    return {
        "campaign_goal": strategy.campaign_goal,
        "target_audience": strategy.target_audience,
        "positioning": strategy.positioning,
        "value_proposition": strategy.value_proposition,
        "key_messages": strategy.key_messages,
        "content_angles": strategy.content_angles,
        "recommended_channels": strategy.recommended_channels,
        "cta": strategy.cta,
        "risks": strategy.risks,
        "things_to_avoid": strategy.things_to_avoid,
    }


def _default_audience(segment: str) -> tuple[str, ...]:
    if segment == "Corporate Gifts":
        return ("Corporate event planners", "Executive assistants", "Procurement teams")
    if segment == "University / Museum Gifting":
        return ("University advancement teams", "Museum programme teams", "Cultural institutions")
    return ("Design-conscious gift buyers", "Cultural home decor buyers")


def _normalize_channels(channels: tuple[str, ...]) -> tuple[str, ...]:
    aliases = {
        "linkedin": "LinkedIn",
        "instagram": "Instagram",
        "xiaohongshu": "Xiaohongshu",
        "小红书": "Xiaohongshu",
        "email": "Email Outreach",
        "email outreach": "Email Outreach",
        "landing": "Landing Page",
        "landing page": "Landing Page",
        "product copy": "Landing Page",
    }
    normalized = tuple(
        dict.fromkeys(
            aliases.get(channel.strip().casefold(), channel.strip())
            for channel in channels
            if channel.strip()
        )
    )
    unsupported = set(normalized) - set(SUPPORTED_CHANNELS)
    if unsupported:
        raise ValueError(f"unsupported campaign channels: {sorted(unsupported)}")
    return normalized


def _channel_id(channel: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", channel.casefold()).strip("_")


def _asset_type(channel: str) -> str:
    return {
        "LinkedIn": "post",
        "Instagram": "caption",
        "Xiaohongshu": "post",
        "Email Outreach": "email",
        "Landing Page": "landing_copy",
    }[channel]


def _values(fact: Any) -> tuple[str, ...]:
    if fact is None:
        return ()
    value = fact.value
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value.strip()


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


__all__ = [
    "DEFAULT_CHANNELS",
    "SUPPORTED_CHANNELS",
    "GrowthModelClient",
    "analyze_market_opportunities",
    "apply_human_edits",
    "build_marketing_strategy",
    "generate_campaign_assets",
    "review_campaign_grounding",
    "revise_campaign_assets",
]
