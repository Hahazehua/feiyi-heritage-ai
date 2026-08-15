"""Stable JSON serialization for Growth Studio campaign repositories."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, cast

from heritagelink.agent_models import SafetyCheckResult, SkillExecutionTrace, SkillStatus
from heritagelink.growth_models import (
    CampaignAsset,
    CampaignClaim,
    CampaignStatus,
    EvidenceStatus,
    GrowthOutputSource,
    GuardianIssue,
    GuardianReview,
    GuardianRiskLevel,
    MarketAnalysis,
    MarketingCampaign,
    MarketingStrategy,
    MarketOpportunity,
)


def campaign_to_dict(campaign: MarketingCampaign) -> dict[str, object]:
    return cast(dict[str, object], _json_value(asdict(campaign)))


def campaign_from_dict(payload: dict[str, object]) -> MarketingCampaign:
    market = cast(dict[str, Any], payload["market_analysis"])
    strategy = cast(dict[str, Any], payload["strategy"])
    guardian = cast(dict[str, Any], payload["guardian_review"])
    return MarketingCampaign(
        campaign_id=str(payload["campaign_id"]),
        campaign_name=str(payload["campaign_name"]),
        artisan_id=str(payload["artisan_id"]),
        product_id=str(payload["product_id"]),
        goal=str(payload["goal"]),
        target_geography=(
            str(payload["target_geography"]) if payload.get("target_geography") else None
        ),
        target_segment=str(payload["target_segment"]),
        market_analysis=_market_from_dict(market),
        strategy=_strategy_from_dict(strategy),
        assets=tuple(
            _asset_from_dict(item) for item in cast(list[dict[str, Any]], payload.get("assets", []))
        ),
        guardian_review=_guardian_from_dict(guardian),
        revision_count=int(payload["revision_count"]),
        status=CampaignStatus(str(payload["status"])),
        source=GrowthOutputSource(str(payload["source"])),
        trace_events=tuple(
            _trace_from_dict(item)
            for item in cast(list[dict[str, Any]], payload.get("trace_events", []))
        ),
        human_reviewed_warnings=tuple(
            str(value) for value in payload.get("human_reviewed_warnings", [])
        ),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _market_from_dict(payload: dict[str, Any]) -> MarketAnalysis:
    return MarketAnalysis(
        opportunities=tuple(
            MarketOpportunity(
                segment=str(item["segment"]),
                fit_score=int(item["fit_score"]),
                reasons=tuple(str(value) for value in item.get("reasons", [])),
                risks=tuple(str(value) for value in item.get("risks", [])),
            )
            for item in payload.get("opportunities", [])
        ),
        recommended_segment=str(payload["recommended_segment"]),
        summary=str(payload["summary"]),
        evidence_basis=str(payload["evidence_basis"]),
        external_evidence_used=bool(payload["external_evidence_used"]),
        source=GrowthOutputSource(str(payload["source"])),
    )


def _strategy_from_dict(payload: dict[str, Any]) -> MarketingStrategy:
    return MarketingStrategy(
        campaign_goal=str(payload["campaign_goal"]),
        target_audience=tuple(str(value) for value in payload.get("target_audience", [])),
        positioning=str(payload["positioning"]),
        value_proposition=str(payload["value_proposition"]),
        key_messages=tuple(str(value) for value in payload.get("key_messages", [])),
        content_angles=tuple(str(value) for value in payload.get("content_angles", [])),
        recommended_channels=tuple(str(value) for value in payload.get("recommended_channels", [])),
        cta=str(payload["cta"]),
        risks=tuple(str(value) for value in payload.get("risks", [])),
        things_to_avoid=tuple(str(value) for value in payload.get("things_to_avoid", [])),
        reasoning_summary=str(payload["reasoning_summary"]),
        source=GrowthOutputSource(str(payload["source"])),
    )


def _asset_from_dict(payload: dict[str, Any]) -> CampaignAsset:
    return CampaignAsset(
        asset_id=str(payload["asset_id"]),
        channel=str(payload["channel"]),
        asset_type=str(payload["asset_type"]),
        content=str(payload["content"]),
        cta=str(payload["cta"]),
        claims=tuple(
            CampaignClaim(
                claim_text=str(item["claim_text"]),
                field_name=(str(item["field_name"]) if item.get("field_name") else None),
                evidence_status=EvidenceStatus(str(item["evidence_status"])),
                source_label=(str(item["source_label"]) if item.get("source_label") else None),
                source_url=str(item["source_url"]) if item.get("source_url") else None,
            )
            for item in payload.get("claims", [])
        ),
        source_references=tuple(str(value) for value in payload.get("source_references", [])),
        raw_ai_content=(str(payload["raw_ai_content"]) if payload.get("raw_ai_content") else None),
        revised_ai_content=(
            str(payload["revised_ai_content"]) if payload.get("revised_ai_content") else None
        ),
        final_human_content=(
            str(payload["final_human_content"]) if payload.get("final_human_content") else None
        ),
    )


def _guardian_from_dict(payload: dict[str, Any]) -> GuardianReview:
    return GuardianReview(
        approved=bool(payload["approved"]),
        risk_level=GuardianRiskLevel(str(payload["risk_level"])),
        issues=tuple(
            GuardianIssue(
                asset_id=str(item["asset_id"]),
                issue_type=str(item["issue_type"]),
                claim=str(item["claim"]),
                reason=str(item["reason"]),
                source=str(item["source"]) if item.get("source") else None,
                recommended_action=str(item["recommended_action"]),
            )
            for item in payload.get("issues", [])
        ),
        supported_claims=tuple(str(value) for value in payload.get("supported_claims", [])),
        revision_instructions=tuple(
            str(value) for value in payload.get("revision_instructions", [])
        ),
        reviewed_asset_ids=tuple(str(value) for value in payload.get("reviewed_asset_ids", [])),
    )


def _trace_from_dict(payload: dict[str, Any]) -> SkillExecutionTrace:
    return SkillExecutionTrace(
        trace_id=str(payload["trace_id"]),
        skill_id=str(payload["skill_id"]),
        skill_name=str(payload["skill_name"]),
        sequence_number=int(payload["sequence_number"]),
        status=SkillStatus(str(payload["status"])),
        trigger_reason=str(payload["trigger_reason"]),
        input_summary=dict(payload.get("input_summary", {})),
        output_summary=dict(payload.get("output_summary", {})),
        fallback_used=bool(payload["fallback_used"]),
        fallback_reason=(
            str(payload["fallback_reason"]) if payload.get("fallback_reason") else None
        ),
        safety_checks=tuple(
            SafetyCheckResult(
                check_id=str(item["check_id"]),
                passed=bool(item["passed"]),
                summary=str(item["summary"]),
            )
            for item in payload.get("safety_checks", [])
        ),
        duration_ms=float(payload["duration_ms"]),
        started_at=datetime.fromisoformat(str(payload["started_at"])),
        completed_at=datetime.fromisoformat(str(payload["completed_at"])),
    )


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


__all__ = ["campaign_from_dict", "campaign_to_dict"]
