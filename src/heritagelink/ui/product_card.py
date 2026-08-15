"""Customer-facing recommendation card with details available on demand."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from heritagelink.heritage_passport_models import HeritagePassport, VerificationStatus
from heritagelink.i18n import Language, get_language, t
from heritagelink.models import GiftRequest, Recommendation
from heritagelink.ui.components import badges, product_image
from heritagelink.ui.heritage_passport import render_heritage_passport
from heritagelink.ui.requirements import MEANINGS, RECIPIENTS, SCENES, STYLES
from heritagelink.ui.system import render_demo_badge, render_status_badge

DIMENSION_LABELS = {
    "budget": "预算匹配",
    "recipient": "对象匹配",
    "occasion": "场景匹配",
    "style": "风格匹配",
    "cultural_meaning": "文化寓意",
    "customization": "定制能力",
    "quantity": "数量条件",
    "lead_time": "交付条件",
}
DIMENSION_LABELS_EN = {
    "budget": "Budget fit",
    "recipient": "Recipient fit",
    "occasion": "Occasion fit",
    "style": "Style fit",
    "cultural_meaning": "Cultural meaning",
    "customization": "Customization",
    "quantity": "Quantity",
    "lead_time": "Lead time",
}
DISPLAY_TAGS = {
    **{code: label for label, code in RECIPIENTS.items()},
    **{code: label for label, code in SCENES.items()},
    **{code: label for label, code in STYLES.items()},
    **{code: label for label, code in MEANINGS.items()},
    "inscription": "文字题刻",
    "pattern": "纹样",
    "size": "尺寸",
    "packaging": "礼盒与包装",
    "color": "色彩",
    "logo": "品牌标识",
    "other": "其他定制",
}
DISPLAY_TAGS_EN = {
    "business_partner": "Business Partner",
    "institution": "Institution",
    "employee": "Employee",
    "elder": "Elder",
    "family": "Family",
    "friend": "Friend",
    "newlywed": "Newlyweds",
    "teacher": "Teacher",
    "collector": "Collector",
    "business_gift": "Business Gift",
    "commemoration": "Commemoration",
    "wedding": "Wedding",
    "anniversary": "Anniversary",
    "housewarming": "Housewarming",
    "birthday": "Birthday",
    "festival": "Festival",
    "graduation": "Graduation",
    "appreciation": "Appreciation",
    "collection": "Collection",
    "exhibition": "Exhibition",
    "traditional": "Traditional",
    "modern": "Modern",
    "minimal": "Minimal",
    "grand": "Grand",
    "elegant": "Elegant",
    "festive": "Festive",
    "warm": "Warm",
    "heritage": "Heritage",
    "prosperity": "Prosperity",
    "blessing": "Blessing",
    "harmony": "Harmony",
    "longevity": "Longevity",
    "resilience": "Resilience",
    "remembrance": "Remembrance",
    "gratitude": "Gratitude",
    "union": "Union",
    "inscription": "Inscription",
    "pattern": "Pattern",
    "size": "Size",
    "packaging": "Gift Packaging",
    "color": "Colour",
    "logo": "Logo",
    "other": "Other",
}


def _display_tags() -> dict[str, str]:
    return DISPLAY_TAGS_EN if get_language() == Language.EN_US else DISPLAY_TAGS


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def recommendation_reason(recommendation: Recommendation, participating: frozenset[str]) -> str:
    """Return a concise customer-facing reason grounded in score explanations."""
    reasons: list[str] = []
    display_tags = _display_tags()
    for key in ("recipient", "occasion", "style", "cultural_meaning"):
        dimension = recommendation.score_breakdown[key]
        if key in participating and dimension.score > 0:
            if get_language() == Language.EN_US:
                reasons.append(
                    t(
                        "buyer.dimension_explanation",
                        dimension=DIMENSION_LABELS_EN[key],
                        score=f"{dimension.score:g}",
                        maximum=dimension.max_score,
                    )
                )
                continue
            text = dimension.explanation
            for code, label in display_tags.items():
                text = text.replace(code, label)
            reasons.append(text.rstrip("。"))
    if not reasons:
        return t("buyer.general_fit")
    separator = ". " if get_language() == Language.EN_US else "。"
    suffix = "." if get_language() == Language.EN_US else "。"
    return separator.join(reason.rstrip("。.") for reason in reasons[:2]) + suffix


def _customization_text(recommendation: Recommendation) -> str:
    display_tags = _display_tags()
    tags = [
        display_tags.get(tag.removeprefix("customization:"), tag.removeprefix("customization:"))
        for tag in recommendation.matched_tags
        if tag.startswith("customization:")
    ]
    separator = ", " if get_language() == Language.EN_US else "、"
    return separator.join(tags) if tags else t("buyer.customization_pending")


def render_product_card(
    rank: int,
    recommendation: Recommendation,
    request: GiftRequest,
    participating: frozenset[str],
    known_customer_fields: frozenset[str],
    passport: HeritagePassport | None = None,
    ai_explanation: str | None = None,
) -> Literal["select", "compare"] | None:
    """Render one product card and return the customer's chosen card action."""
    product = recommendation.product
    display_tags = _display_tags()
    english = get_language() == Language.EN_US
    product_name = product.product_name_en if english else product.product_name_zh
    secondary_name = product.product_name_zh if english else product.product_name_en
    commercial_confirmed = (
        passport is not None
        and passport.commercial_verification_status is VerificationStatus.CONFIRMED
    )
    with st.container(border=True):
        visual, detail = st.columns([1, 1.55], gap="large")
        with visual:
            product_image(product.image_path, product.image_alt_zh)
        with detail:
            st.caption(f"{t('buyer.recommendation', rank=rank)} · {secondary_name}")
            st.markdown(f"### {product_name}")
            render_demo_badge()
            st.write(recommendation_reason(recommendation, participating))
            price = f"{_money(product.price_min_fen)}–{_money(product.price_max_fen)}"
            if commercial_confirmed:
                st.markdown(f"**{price}**")
                render_status_badge("confirmed")
            else:
                st.caption(t("buyer.demo_price", price=price))
                render_status_badge("pending_review", label=t("buyer.commercial_unverified"))
            matched = [
                display_tags[tag] for tag in recommendation.matched_tags if tag in display_tags
            ]
            if matched:
                badges([(label, "ok") for label in matched[:4]])
            st.caption(f"{t('buyer.customization')}: {_customization_text(recommendation)}")
        with st.expander(t("buyer.details")):
            separator = ", " if english else "、"
            st.write(
                f"{t('buyer.fit_scene')}: {separator.join(matched[:4]) or t('common.unknown')}"
            )
            meaning_text = separator.join(
                display_tags[tag]
                for tag in recommendation.matched_tags
                if tag in MEANINGS.values() and tag in display_tags
            )
            st.write(f"{t('buyer.cultural_meaning')}: {meaning_text or t('common.unknown')}")
            st.write(f"{t('buyer.dimensions')}: {product.dimensions_text}")
            st.write(f"{t('buyer.materials')}: {product.material_text}")
            st.write(f"{t('buyer.moq')}: {product.min_order_qty}")
            st.write(f"{t('buyer.lead_time')}: {product.lead_time_days}")
        with st.expander(t("buyer.recommendation_why")):
            # The prose reads better but the scoreboard is what is actually
            # verifiable, so both are shown and the source of each is labelled.
            if ai_explanation:
                st.markdown(f"**{t('buyer.why_ai_label')}**")
                st.write(ai_explanation)
                st.markdown(f"**{t('buyer.why_rule_label')}**")
            dimension_labels = DIMENSION_LABELS_EN if english else DIMENSION_LABELS
            for key, dimension in recommendation.score_breakdown.items():
                if key in participating:
                    explanation = (
                        t(
                            "buyer.dimension_explanation",
                            dimension=dimension_labels[key],
                            score=f"{dimension.score:g}",
                            maximum=dimension.max_score,
                        )
                        if english
                        else dimension.explanation
                    )
                    st.write(f"**{dimension_labels[key]}**: {explanation}")
            st.caption(t("buyer.ranking_note"))
        if passport is not None:
            with st.expander(t("buyer.passport")):
                render_heritage_passport(passport, audience="buyer", compact=True)
        select, compare = st.columns(2)
        if select.button(
            t("buyer.select"),
            key=f"select_{product.product_id}",
            type="primary" if rank == 1 else "secondary",
            width="stretch",
        ):
            return "select"
        if compare.button(
            t("buyer.compare"),
            key=f"compare_{product.product_id}",
            width="stretch",
        ):
            return "compare"
        return None
