"""Canonical registry for the seven formal HeritageLink Skills."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    skill_name: str
    order: int
    required: bool
    fallback: str
    execution: str = "customer_flow"


SKILL_REGISTRY = (
    SkillDefinition("understand_gift_request", "礼赠需求理解", 1, True, "deterministic_parser"),
    SkillDefinition("infer_soft_preferences", "受控软偏好推断", 2, True, "preserve_unknown"),
    SkillDefinition(
        "recommend_heritage_gifts",
        "非遗礼品硬过滤与稳定推荐",
        3,
        True,
        "no_match_response",
    ),
    SkillDefinition(
        "compose_grounded_content",
        "有事实边界的双语文化内容组织",
        4,
        False,
        "omit_unverified_content",
    ),
    SkillDefinition(
        "build_final_gift_plan", "最终礼品方案生成", 5, False, "omit_unknown_commercial_fields"
    ),
    SkillDefinition(
        "capture_consented_choice", "匿名授权选择记录", 6, False, "continue_without_storage"
    ),
    SkillDefinition(
        "analyze_gift_choice_signals",
        "匿名礼品选择信号分析",
        7,
        False,
        "insufficient_sample_report",
        "offline_on_demand",
    ),
)
SKILLS_BY_ID = {item.skill_id: item for item in SKILL_REGISTRY}

# Artisan Growth Skills are registered beside, not inserted into, the seven-skill
# buyer chain.  This preserves the published buyer manifest and its stable order.
GROWTH_SKILL_REGISTRY = (
    SkillDefinition(
        "analyze_market_opportunities",
        "Market Intelligence",
        1,
        True,
        "product_grounded_assessment",
        "artisan_growth",
    ),
    SkillDefinition(
        "build_marketing_strategy",
        "Marketing Strategist",
        2,
        True,
        "bounded_deterministic_strategy",
        "artisan_growth",
    ),
    SkillDefinition(
        "generate_campaign_assets",
        "Creative Agent",
        3,
        True,
        "grounded_campaign_templates",
        "artisan_growth",
    ),
    SkillDefinition(
        "review_campaign_grounding",
        "Cultural Guardian",
        4,
        True,
        "fail_closed_human_review",
        "artisan_growth",
    ),
    SkillDefinition(
        "revise_campaign_assets",
        "Creative Revision",
        5,
        False,
        "remove_unsupported_claims",
        "artisan_growth",
    ),
)
GROWTH_SKILLS_BY_ID = {item.skill_id: item for item in GROWTH_SKILL_REGISTRY}
ALL_SKILLS_BY_ID = {**SKILLS_BY_ID, **GROWTH_SKILLS_BY_ID}
