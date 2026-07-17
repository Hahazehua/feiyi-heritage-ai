"""Large e-commerce-style recommendation card."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from heritagelink.models import GiftRequest, Recommendation
from heritagelink.ui.components import badges, product_image
from heritagelink.ui.requirements import MEANINGS, RECIPIENTS, SCENES, STYLES

CardAction = Literal["culture", "select"]

DIMENSION_LABELS = {
    "budget": "预算匹配",
    "recipient": "对象匹配",
    "occasion": "场景匹配",
    "style": "风格匹配",
    "cultural_meaning": "文化寓意",
    "customization": "定制能力",
    "quantity": "数量产能",
    "lead_time": "交付余量",
}
DISPLAY_TAGS = {
    **{code: label for label, code in RECIPIENTS.items()},
    **{code: label for label, code in SCENES.items()},
    **{code: label for label, code in STYLES.items()},
    **{code: label for label, code in MEANINGS.items()},
}


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _reasons(recommendation: Recommendation, participating: frozenset[str]) -> list[str]:
    reasons = [
        score.explanation
        for key, score in recommendation.score_breakdown.items()
        if key in participating and score.score > 0
    ]
    localized = []
    for reason in reasons[:4]:
        for code, label in DISPLAY_TAGS.items():
            reason = reason.replace(code, label)
        localized.append(reason)
    return localized or ["该产品通过了当前已明确的商业条件校验。"]


def _constraint_badges(
    request: GiftRequest,
    recommendation: Recommendation,
    known_customer_fields: frozenset[str],
) -> list[tuple[str, str]]:
    items = [
        ("符合预算", "ok")
        if "budget_per_item" in known_customer_fields
        else ("预算待补充", "wait"),
        ("满足数量要求", "ok") if "quantity" in known_customer_fields else ("数量待补充", "wait"),
    ]
    items.append(
        ("交期可行", "ok")
        if "required_delivery_days" in known_customer_fields
        else ("交期待补充", "wait")
    )
    if "logo_required" in known_customer_fields and request.logo_required:
        items.append(("支持 Logo", "ok"))
    elif "customization_required" in known_customer_fields and request.customization_required:
        items.append(("支持所需定制", "ok"))
    elif "customization_required" in known_customer_fields and not request.customization_required:
        items.append(("不要求定制", "ok"))
    else:
        items.append(("定制要求待确认", "wait"))
    if (
        "international_shipping_required" in known_customer_fields
        and request.international_shipping_required
    ):
        items.append(("支持国际运输评估", "ok"))
    elif "international_shipping_required" in known_customer_fields:
        items.append(("不要求国际运输", "ok"))
    else:
        items.append(("海外运输待确认", "wait"))
    return items


def render_product_card(
    rank: int,
    recommendation: Recommendation,
    request: GiftRequest,
    participating: frozenset[str],
    known_customer_fields: frozenset[str],
) -> CardAction | None:
    """Render one recommendation and return the user's selected action."""
    product = recommendation.product
    action: CardAction | None = None
    with st.container(border=True):
        visual, detail = st.columns([1, 1.7], gap="large")
        with visual:
            product_image(product.image_path, product.image_alt_zh)
            st.caption(f"{product.merchant_name_zh} · 文化礼赠")
        with detail:
            title_left, score_right = st.columns([3, 1])
            with title_left:
                st.markdown(f'<span class="hl-rank">TOP {rank}</span>', unsafe_allow_html=True)
                st.markdown(f"### {product.product_name_zh}")
                st.caption(product.product_name_en)
            with score_right:
                st.markdown(
                    f'<div class="hl-score">{recommendation.total_score:.0f}</div>'
                    '<div class="hl-muted">综合匹配 / 100</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"**{_money(product.price_min_fen)}–{_money(product.price_max_fen)} / 件**"
                f"　·　基础制作周期 {product.lead_time_days} 天"
            )
            for reason in _reasons(recommendation, participating):
                st.write(f"• {reason}")
            badges(_constraint_badges(request, recommendation, known_customer_fields))
        st.markdown("#### 匹配详情")
        score_columns = st.columns(4)
        for index, (key, dimension) in enumerate(recommendation.score_breakdown.items()):
            with score_columns[index % 4]:
                if key not in participating:
                    st.caption(f"{DIMENSION_LABELS[key]} · 待补充")
                    st.progress(0)
                else:
                    ratio = dimension.score / dimension.max_score if dimension.max_score else 0
                    st.caption(f"{DIMENSION_LABELS[key]} · {ratio:.0%}")
                    st.progress(max(0.0, min(1.0, ratio)))
        if recommendation.risks:
            with st.expander("风险与待确认事项"):
                for risk in recommendation.risks:
                    st.warning(risk)
        culture, select = st.columns(2)
        if culture.button("查看文化故事", key=f"culture_{product.product_id}", width="stretch"):
            action = "culture"
        if select.button(
            "选择此方案",
            key=f"select_{product.product_id}",
            type="primary" if rank == 1 else "secondary",
            width="stretch",
        ):
            action = "select"
    return action
