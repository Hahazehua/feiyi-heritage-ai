"""Localized copy for the deterministic Growth Studio path.

The live-AI path passes the requested language through to the model, but the
deterministic path built its output from hardcoded English regardless — and
that path is the default. A user who picked 简体中文 got English campaign copy
and no way to change it.

Keeping the strings here rather than inline leaves the agent logic readable and
makes the language contract explicit: every user-visible sentence the
deterministic path can emit has an entry on both sides.

Segment names double as identifiers downstream, so callers compare against the
fields of the same phrase set rather than against literals.
"""

# ruff: noqa: E501  — copy tables, same convention as the i18n catalogues

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GrowthPhrases:
    """Every user-visible sentence the deterministic generator can produce."""

    # --- market analysis ---
    source_supported: str
    source_pending: str
    corporate_positioning: str
    corporate_tags: str
    corporate_customization: str
    segment_corporate: str
    segment_decor: str
    segment_institution: str
    decor_visual: str
    institution_educational: str
    institution_no_endorsement: str
    institution_endorsement_risk: str
    geography_fallback: str
    summary_template: str
    evidence_basis: str

    # --- strategy ---
    product_fallback: str
    source_message_ok: str
    source_message_pending: str
    key_present_template: str
    key_craft_template: str
    key_customization: str
    market_fallback: str
    positioning_template: str
    value_proposition: str
    angle_story: str
    angle_alternative: str
    angle_conversation: str
    cta: str
    avoid_claims: str
    avoid_promises: str
    avoid_superlatives: str
    reasoning_template: str

    # --- assets ---
    asset_product_fallback: str
    source_phrase_ok: str
    source_phrase_pending: str
    craft_phrase_template: str
    claim_source_available: str
    disclaimer: str
    linkedin_template: str
    instagram_template: str
    xiaohongshu_template: str
    email_template: str
    landing_template: str
    guardian_fixture: str

    # --- audiences ---
    audience_corporate: tuple[str, ...]
    audience_institution: tuple[str, ...]
    audience_default: tuple[str, ...]

    # --- commercial risks ---
    risk_shipping: str
    risk_lead_time: str
    risk_capacity: str
    risk_customization: str


ZH = GrowthPhrases(
    source_supported="已核验的公开文化来源可以支撑有据可查的叙述。",
    source_pending="文化来源尚待复核，文案措辞需保持笼统。",
    corporate_positioning="该产品可定位为具有辨识度的文化礼赠方案。",
    corporate_tags="结构化的目录标签支持商务礼赠场景。",
    corporate_customization="已确认的定制能力契合机构礼赠需求。",
    segment_corporate="商务礼赠",
    segment_decor="文化家居陈设",
    segment_institution="高校与博物馆礼品",
    decor_visual="以器物为主的呈现方式适合视觉叙事与陈列向文案。",
    institution_educational="有据可查的叙述适用于教育与文化场景。",
    institution_no_endorsement="文案可以突出学习与交流，而不声称获得任何背书。",
    institution_endorsement_risk="尚未核验任何博物馆、高校或机构的背书。",
    geography_fallback="所选市场",
    summary_template="在{geography}，{segment}是最有产品依据的场景。这是 AI 的机会评估，不是经外部验证的市场研究。",
    evidence_basis="仅基于已核验的产品信息与确定性目录标签",
    product_fallback="该手艺产品",
    source_message_ok="使用有据可查的文化背景，并附上可用的来源链接。",
    source_message_pending="在来源复核完成前，文化表述保持笼统。",
    key_present_template="把{product}呈现为经过考量的文化礼赠方案。",
    key_craft_template="通过已确认的工艺背景来解释这件作品：{craft}。",
    key_customization="邀请买家就已确认的定制选项进一步沟通。",
    market_fallback="目标市场",
    positioning_template="面向{segment}的有据可查的手艺产品，附文化背景与明确的确认边界。",
    value_proposition="把有辨识度的器物、可理解的文化背景，和一条低门槛的询单路径结合起来，同时不做任何未经核验的商业承诺。",
    angle_story="器物背后的故事",
    angle_alternative="通用礼品之外的一种选择",
    angle_conversation="如何开启定制或采购的沟通",
    cta="索取已核验的产品与定制信息",
    avoid_claims="无证据的官方非遗、认证、获奖或大师身份表述",
    avoid_promises="未经确认的具体价格、库存、产能、交期或物流承诺",
    avoid_superlatives="最高级形容、杜撰的历史年代，以及猎奇化的文化表述",
    reasoning_template="策略沿用创意生成之前选定的{segment}机会；创意环节可以执行，但不能改变这一定位。",
    asset_product_fallback="这件手艺产品",
    source_phrase_ok="其文案叙述关联到一份经复核的公开文化参考。",
    source_phrase_pending="文化细节仍待来源复核。",
    craft_phrase_template="作品通过已确认的{craft}工艺背景呈现。",
    claim_source_available="存在可查的公开文化参考",
    disclaimer="（草稿文案：产品发布状态与未核验的商业细节另行处理。）",
    linkedin_template=(
        "在机构礼赠上想找一种更有分量的做法？{product}提供了一个有文化依据的起点。"
        "{craft}{source} {cta}。{disclaimer}"
    ),
    instagram_template="一份礼物可以开启一场文化对话。了解{product}。{craft}{source} {cta}。{disclaimer}",
    xiaohongshu_template=(
        "把礼物变成一次有依据的文化交流：{product}。{craft}{source} "
        "如需用于海外礼赠，请先咨询并确认产品与定制细节。{disclaimer}"
    ),
    email_template=(
        "主题：一个有据可查的文化礼赠方案\n\n您好，\n\n"
        "我们想向您介绍{product}，作为一次礼赠沟通的起点。{craft}{source}\n\n"
        "{cta}。\n\n所有商业细节都会在任何承诺之前确认。{disclaimer}"
    ),
    landing_template=(
        "{product}\n\n一件有据可查的手艺产品，为深思熟虑的礼赠沟通而准备。"
        "{craft}{source}\n\n{value}\n\n{cta}。{disclaimer}"
    ),
    guardian_fixture="拥有千年官方认证的传承，并保证国际配送。",
    audience_corporate=("企业活动策划", "高管助理", "采购团队"),
    audience_institution=("高校发展办公室", "博物馆项目团队", "文化机构"),
    audience_default=("注重设计的礼品买家", "文化家居买家"),
    risk_shipping="目标市场的国际运输能力尚未核验。",
    risk_lead_time="生产交期尚未核验。",
    risk_capacity="产能与数量适配性尚未核验。",
    risk_customization="定制能力须经确认后才能作为卖点宣传。",
)


EN = GrowthPhrases(
    source_supported="A verified public cultural source supports source-aware storytelling.",
    source_pending="Campaign wording must remain generic because cultural sources need review.",
    corporate_positioning="The product can be positioned as a distinctive cultural gift concept.",
    corporate_tags="Structured catalogue tags support business-gifting scenarios.",
    corporate_customization="Confirmed customization supports organizational gifting needs.",
    segment_corporate="Corporate Gifts",
    segment_decor="Cultural Home Decor",
    segment_institution="University / Museum Gifting",
    decor_visual="The object-led format can support visual storytelling and display-oriented copy.",
    institution_educational="The source-aware narrative is suitable for educational and cultural contexts.",
    institution_no_endorsement="The campaign can foreground learning and exchange without claiming endorsement.",
    institution_endorsement_risk="No museum, university, or institutional endorsement is verified.",
    geography_fallback="the selected geography",
    summary_template=(
        "{segment} is the strongest product-grounded scenario for {geography}. "
        "This is an AI opportunity assessment, not externally validated market research."
    ),
    evidence_basis="Verified product context and deterministic catalogue tags only",
    product_fallback="the artisan product",
    source_message_ok="Use source-aware cultural context and link to the available reference.",
    source_message_pending="Keep cultural wording general until source review is complete.",
    key_present_template="Present {product} as a considered cultural gifting concept.",
    key_craft_template="Explain the work through its confirmed craft context: {craft}.",
    key_customization="Invite buyers to discuss the confirmed customization options.",
    market_fallback="the intended market",
    positioning_template=(
        "A source-aware artisan product for {segment}, presented with cultural "
        "context and clear confirmation boundaries."
    ),
    value_proposition=(
        "Combine a distinctive object, understandable cultural context, and a low-friction "
        "path to a qualified inquiry without making unverified commercial promises."
    ),
    angle_story="The story behind the object",
    angle_alternative="A thoughtful alternative to generic gifting",
    angle_conversation="How to begin a customization or sourcing conversation",
    cta="Request verified product and customization details",
    avoid_claims="Official heritage, certification, award, or master-artisan claims without evidence",
    avoid_promises="Exact price, inventory, capacity, lead-time, or shipping promises unless confirmed",
    avoid_superlatives="Superlatives, invented historical ages, and exoticized cultural language",
    reasoning_template=(
        "Strategy follows the {segment} opportunity selected before Creative generation; "
        "Creative may execute but cannot change this positioning."
    ),
    asset_product_fallback="This artisan product",
    source_phrase_ok="Its campaign story is linked to a reviewed public cultural reference.",
    source_phrase_pending="Cultural details remain subject to source review.",
    craft_phrase_template=" It is presented through the confirmed craft context of {craft}.",
    claim_source_available="A public cultural reference is available",
    disclaimer=" Draft campaign: product publication and unverified commercial details remain separate.",
    linkedin_template=(
        "Looking for a more meaningful approach to organizational gifting? {product} "
        "offers a culturally grounded starting point.{craft} {source} {cta}.{disclaimer}"
    ),
    instagram_template=(
        "A gift can open a cultural conversation. Discover {product}.{craft} "
        "{source} {cta}.{disclaimer}"
    ),
    xiaohongshu_template=(
        "把礼物变成一次有依据的文化交流：{product}。{source} "
        "如需用于海外礼赠，请先咨询并确认产品与定制细节。{disclaimer}"
    ),
    email_template=(
        "Subject: A source-aware cultural gifting concept\n\n"
        "Hello,\n\nWe would like to introduce {product} as a possible starting point "
        "for a thoughtful gifting conversation.{craft} {source}\n\n"
        "{cta}.\n\nCommercial details will be confirmed before any commitment.{disclaimer}"
    ),
    landing_template=(
        "{product}\n\nA source-aware artisan product designed for a thoughtful gifting "
        "conversation.{craft} {source}\n\n{value}\n\n{cta}.{disclaimer}"
    ),
    guardian_fixture=(
        "A thousand-year-old officially certified tradition, with guaranteed "
        "international delivery."
    ),
    audience_corporate=("Corporate event planners", "Executive assistants", "Procurement teams"),
    audience_institution=(
        "University advancement teams",
        "Museum programme teams",
        "Cultural institutions",
    ),
    audience_default=("Design-conscious gift buyers", "Cultural home decor buyers"),
    risk_shipping="International shipping capability remains unverified for the target geography.",
    risk_lead_time="Production lead time remains unverified.",
    risk_capacity="Production capacity and quantity suitability remain unverified.",
    risk_customization="Customization capability must be confirmed before promotion as a feature.",
)


def phrases_for(language: str | None) -> GrowthPhrases:
    """Pick the phrase set for a campaign language.

    Bilingual leads in Chinese; the asset copy adds its English counterpart, so
    the surrounding analysis does not need to be duplicated.
    """
    normalized = (language or "").strip().casefold()
    if normalized in {"chinese", "zh", "zh-cn", "简体中文", "中文", "bilingual", "中英双语"}:
        return ZH
    return EN


def is_bilingual(language: str | None) -> bool:
    normalized = (language or "").strip().casefold()
    return normalized in {"bilingual", "中英双语"}


__all__ = ["EN", "ZH", "GrowthPhrases", "is_bilingual", "phrases_for"]
