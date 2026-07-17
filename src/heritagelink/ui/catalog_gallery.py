"""Streamlit gallery for source-traceable heritage reference items."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import streamlit as st

from heritagelink.catalog import HeritageReferenceItem
from heritagelink.models import Product


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _matches(item: HeritageReferenceItem, *, category: str, query: str) -> bool:
    if category != "全部工艺" and item.craft_category_zh != category:
        return False
    if not query:
        return True
    haystack = " ".join(
        (
            item.product_name_zh,
            item.product_name_en,
            item.craft_category_zh,
            item.craft_category_en,
            item.period_text,
            item.material_text,
            item.introduction_zh,
        )
    ).casefold()
    return query.casefold() in haystack


def render_catalog_gallery(
    items: tuple[HeritageReferenceItem, ...],
    *,
    products_by_id: Mapping[str, Product],
    project_root: Path,
) -> None:
    """Render searchable product cards linked to their reference sources."""
    categories = tuple(dict.fromkeys(item.craft_category_zh for item in items))
    filter_col, search_col = st.columns([1, 2])
    category = filter_col.selectbox(
        "按工艺筛选",
        ("全部工艺", *categories),
        key="reference_catalog_category",
    )
    query = search_col.text_input(
        "搜索商品",
        placeholder="输入名称、材质、年代或工艺",
        key="reference_catalog_query",
    ).strip()

    visible_items = tuple(item for item in items if _matches(item, category=category, query=query))
    st.caption(f"当前显示 {len(visible_items)} / {len(items)} 件 · 图片与资料均可追溯")
    if not visible_items:
        st.info("没有匹配的商品，请尝试清空搜索或切换工艺分类。")
        return

    for start in range(0, len(visible_items), 3):
        columns = st.columns(3)
        for column, item in zip(columns, visible_items[start : start + 3], strict=False):
            with column, st.container(border=True):
                product = products_by_id[item.demo_product_id]
                st.image(
                    str(item.image_file(project_root)),
                    caption=product.image_alt_zh,
                    width="stretch",
                )
                st.markdown(f"### {product.product_name_zh}")
                st.caption(product.product_name_en)
                st.markdown(
                    f'<span class="hl-catalog-pill">{item.craft_category_zh}</span>'
                    '<span class="hl-catalog-pill muted">可参与智能推荐</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**{_money(product.price_min_fen)}–{_money(product.price_max_fen)} / 件**"
                )
                st.caption(
                    f"起订 {product.min_order_qty} 件 · 基础制作周期 {product.lead_time_days} 天"
                )
                st.write(item.introduction_zh)
                with st.expander("商品详情与图片出处"):
                    st.write(f"方案规格：{product.dimensions_text}")
                    st.write(f"方案材料：{product.material_text}")
                    st.write(f"年代：{item.period_text}")
                    st.write(f"地区：{item.region_text}")
                    st.write(f"馆藏编号：{item.source_object_number}")
                    st.caption(f"图片许可：{item.image_license}")
                    st.link_button("查看馆藏原页", item.source_url, width="stretch")
