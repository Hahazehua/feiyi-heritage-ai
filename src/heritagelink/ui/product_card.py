"""Customer-facing recommendation card with details available on demand."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from heritagelink.heritage_passport_models import HeritagePassport
from heritagelink.models import GiftRequest, Recommendation
from heritagelink.ui.components import badges, product_image
from heritagelink.ui.heritage_passport import render_heritage_passport
from heritagelink.ui.requirements import MEANINGS, RECIPIENTS, SCENES, STYLES

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


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def recommendation_reason(recommendation: Recommendation, participating: frozenset[str]) -> str:
    """Return a concise customer-facing reason grounded in score explanations."""
    reasons: list[str] = []
    for key in ("recipient", "occasion", "style", "cultural_meaning"):
        dimension = recommendation.score_breakdown[key]
        if key in participating and dimension.score > 0:
            text = dimension.explanation
            for code, label in DISPLAY_TAGS.items():
                text = text.replace(code, label)
            reasons.append(text.rstrip("。"))
    if not reasons:
        return "这件作品符合您目前已经明确的条件，可以作为进一步比较的起点。"
    return "。".join(reasons[:2]) + "。"


def _customization_text(recommendation: Recommendation) -> str:
    tags = [
        DISPLAY_TAGS.get(tag.removeprefix("customization:"), tag.removeprefix("customization:"))
        for tag in recommendation.matched_tags
        if tag.startswith("customization:")
    ]
    return "、".join(tags) if tags else "可用定制方式以产品详情和最终方案为准"


def render_product_card(
    rank: int,
    recommendation: Recommendation,
    request: GiftRequest,
    participating: frozenset[str],
    known_customer_fields: frozenset[str],
    passport: HeritagePassport | None = None,
) -> Literal["select", "compare"] | None:
    """Render one product card and return the customer's chosen card action."""
    product = recommendation.product
    with st.container(border=True):
        visual, detail = st.columns([1, 1.55], gap="large")
        with visual:
            product_image(product.image_path, product.image_alt_zh)
        with detail:
            st.caption(f"推荐 {rank} · {product.product_name_en}")
            st.markdown(f"### {product.product_name_zh}")
            st.write(recommendation_reason(recommendation, participating))
            st.markdown(f"**{_money(product.price_min_fen)}–{_money(product.price_max_fen)} / 件**")
            matched = [
                DISPLAY_TAGS[tag] for tag in recommendation.matched_tags if tag in DISPLAY_TAGS
            ]
            if matched:
                badges([(label, "ok") for label in matched[:4]])
            st.caption(f"可支持的定制方向：{_customization_text(recommendation)}")
        with st.expander("查看详情"):
            st.write(f"适合对象或场景：{'、'.join(matched[:4]) or '通用文化礼赠'}")
            meaning_text = "、".join(label for label in matched if label in MEANINGS)
            st.write(f"文化寓意：{meaning_text or '以文化内容页为准'}")
            st.write(f"尺寸：{product.dimensions_text}")
            st.write(f"材料：{product.material_text}")
            st.write(f"目录起订量：{product.min_order_qty} 件")
            st.write(f"目录基础制作周期：{product.lead_time_days} 天")
        with st.expander("为什么推荐给我？"):
            for key, dimension in recommendation.score_breakdown.items():
                if key in participating:
                    st.write(f"**{DIMENSION_LABELS[key]}**：{dimension.explanation}")
            st.caption("详细评分仅用于解释当前排序，不代表购买概率或履约承诺。")
        if passport is not None:
            with st.expander("文化护照"):
                render_heritage_passport(passport, audience="buyer", compact=True)
        select, compare = st.columns(2)
        if select.button(
            "选择这件礼品",
            key=f"select_{product.product_id}",
            type="primary" if rank == 1 else "secondary",
            width="stretch",
        ):
            return "select"
        if compare.button(
            "和其他商品比较",
            key=f"compare_{product.product_id}",
            width="stretch",
        ):
            return "compare"
        return None
