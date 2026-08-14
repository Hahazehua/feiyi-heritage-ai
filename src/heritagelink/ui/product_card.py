"""Customer-facing recommendation card with details available on demand."""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.models import GiftRequest, Recommendation
from heritagelink.ui.components import badges, product_image
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
    *,
    selected: bool = False,
) -> bool:
    """Render one product card and return whether it was selected."""
    product = recommendation.product
    with st.container(border=True, key=f"recommendation_card_{product.product_id}"):
        product_image(product.image_path, product.image_alt_zh)
        reason = recommendation_reason(recommendation, participating)
        st.markdown(
            '<div class="hl-product-copy">'
            f'<span class="hl-product-rank">推荐 {rank} · '
            f'{escape(product.product_name_en)}</span>'
            f'<h3>{escape(product.product_name_zh)}</h3>'
            f'<strong class="hl-product-price">{_money(product.price_min_fen)}–'
            f'{_money(product.price_max_fen)} / 件</strong>'
            f'<p class="hl-product-reason">{escape(reason)}</p></div>',
            unsafe_allow_html=True,
        )
        matched = [DISPLAY_TAGS[tag] for tag in recommendation.matched_tags if tag in DISPLAY_TAGS]
        badge_items = [(label, "ok") for label in matched[: (2 if selected else 3)]]
        if selected:
            badge_items.append(("✓ 已选择", "ok"))
        badges(badge_items)
        with st.expander("看看为什么适合"):
            st.write(f"适合对象或场景：{'、'.join(matched[:4]) or '通用文化礼赠'}")
            meaning_text = "、".join(label for label in matched if label in MEANINGS)
            st.write(f"文化寓意：{meaning_text or '以文化内容页为准'}")
            st.write(f"可支持的定制方向：{_customization_text(recommendation)}")
            st.write(f"作品资料：{product.dimensions_text} · {product.material_text}")
            st.write(
                f"目录起订量：{product.min_order_qty} 件；基础制作周期：{product.lead_time_days} 天"
            )
            st.markdown("**推荐依据**")
            for key, dimension in recommendation.score_breakdown.items():
                if key in participating:
                    st.write(f"**{DIMENSION_LABELS[key]}**：{dimension.explanation}")
            st.caption("详细评分仅用于解释当前排序，不代表购买概率或履约承诺。")
        if selected:
            st.markdown(
                '<div class="hl-card-selected-action">已加入当前方案</div>',
                unsafe_allow_html=True,
            )
            return False
        return st.button(
            "选择这件礼物",
            key=f"select_{product.product_id}",
            type="primary" if rank == 1 else "secondary",
            width="stretch",
        )
