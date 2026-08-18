"""Streamlit gallery for source-traceable heritage reference items."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from heritagelink.catalog import HeritageReferenceItem
from heritagelink.catalog_eligibility import is_recommendation_eligible
from heritagelink.i18n import Language, get_language, t
from heritagelink.models import Product
from heritagelink.ui.components import product_image

ALL_CATEGORIES = "__all_categories__"


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _matches(item: HeritageReferenceItem, *, category: str, query: str) -> bool:
    if category != ALL_CATEGORIES and item.craft_category_zh != category:
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
            item.introduction_en,
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
    language = get_language()
    categories = tuple(dict.fromkeys(item.craft_category_zh for item in items))
    category_labels_en = {
        item.craft_category_zh: item.craft_category_en for item in items if item.craft_category_en
    }
    category_values = (ALL_CATEGORIES, *categories)
    category_labels = tuple(
        t("catalog.all_categories")
        if value == ALL_CATEGORIES
        else category_labels_en.get(value, value)
        if language == Language.EN_US
        else value
        for value in category_values
    )
    category_by_label = dict(zip(category_labels, category_values, strict=True))
    filter_col, search_col = st.columns([1, 2])
    selected_category = filter_col.selectbox(
        t("catalog.filter"),
        category_labels,
        key=f"reference_catalog_category_{language.value}",
    )
    category = category_by_label[selected_category]
    query = search_col.text_input(
        t("catalog.search"),
        placeholder=t("catalog.search_placeholder"),
        key="reference_catalog_query",
    ).strip()

    visible_items = tuple(item for item in items if _matches(item, category=category, query=query))
    st.caption(t("catalog.showing", visible=len(visible_items), total=len(items)))
    if not visible_items:
        st.info(t("catalog.empty"))
        return

    for start in range(0, len(visible_items), 3):
        columns = st.columns(3)
        for column, item in zip(columns, visible_items[start : start + 3], strict=False):
            with column, st.container(border=True):
                product = products_by_id[item.demo_product_id]
                recommendable = is_recommendation_eligible(product)
                st.image(
                    str(item.image_file(project_root)),
                    caption=product.image_alt_zh,
                    width="stretch",
                )
                product_name = (
                    product.product_name_en
                    if language == Language.EN_US
                    else product.product_name_zh
                )
                secondary_name = (
                    product.product_name_zh
                    if language == Language.EN_US
                    else product.product_name_en
                )
                category_name = (
                    item.craft_category_en if language == Language.EN_US else item.craft_category_zh
                )
                introduction = (
                    item.introduction_en if language == Language.EN_US else item.introduction_zh
                )
                st.markdown(f"### {product_name}")
                st.caption(secondary_name)
                status = (
                    t("catalog.recommendable_demo")
                    if recommendable
                    else t("catalog.reference_only")
                )
                st.markdown(
                    f'<span class="hl-catalog-pill">{category_name}</span>'
                    f'<span class="hl-catalog-pill muted">{status}</span>',
                    unsafe_allow_html=True,
                )
                if recommendable:
                    price = f"{_money(product.price_min_fen)}–{_money(product.price_max_fen)}"
                    st.markdown(f"**{t('catalog.price_per_item', price=price)}**")
                    st.caption(t("catalog.demo_price_note"))
                    st.caption(
                        t(
                            "catalog.commercial_summary",
                            moq=product.min_order_qty,
                            days=product.lead_time_days,
                        )
                    )
                else:
                    st.caption(t("catalog.reference_note"))
                st.write(introduction)
                with st.expander(t("catalog.details")):
                    if recommendable:
                        st.write(f"{t('catalog.dimensions')}: {product.dimensions_text}")
                        st.write(f"{t('catalog.materials')}: {product.material_text}")
                    else:
                        st.write(f"{t('catalog.reference_materials')}: {item.material_text}")
                    st.write(f"{t('catalog.period')}: {item.period_text}")
                    st.write(f"{t('catalog.region')}: {item.region_text}")
                    st.write(f"{t('catalog.object_number')}: {item.source_object_number}")
                    st.caption(f"{t('catalog.image_license')}: {item.image_license}")
                    st.caption(t("catalog.source_note"))
                    st.link_button(t("catalog.open_source"), item.source_url, width="stretch")


def render_partner_works(
    products: tuple[Product, ...],
    product_texts: pd.DataFrame,
    museum_backed: frozenset[str],
) -> None:
    """Render work supplied by a partner or by the company itself.

    These are real objects rather than museum records, so they have no
    accession number to cite and no open licence behind their photography.
    They are shown as their own group, with their verification state stated
    plainly, rather than mixed into the museum catalogue where the
    surrounding rows all carry a checkable source.
    """
    # Selected by the absence of a museum record rather than by catalogue role:
    # such a work may still be recommendable, and it would otherwise vanish from
    # the catalogue entirely, since the gallery below is driven by museum items.
    partner = tuple(product for product in products if product.product_id not in museum_backed)
    if not partner:
        return

    language = get_language()
    locale = "en" if language == Language.EN_US else "zh-CN"
    st.markdown(f"### {t('catalog.partner_title')}")
    st.caption(t("catalog.partner_note"))

    for product in partner:
        with st.container(border=True):
            visual, detail = st.columns([1, 1.3], gap="large")
            with visual:
                # Shown whole: a 4:3 crop would cut the frame, inscription and seals.
                product_image(product.image_path, product.image_alt_zh, uncropped=True)
            with detail:
                name = (
                    product.product_name_en
                    if language == Language.EN_US
                    else product.product_name_zh
                )
                secondary = (
                    product.product_name_zh
                    if language == Language.EN_US
                    else product.product_name_en
                )
                st.markdown(f"#### {name}")
                st.caption(secondary)
                st.markdown(
                    f'<span class="hl-catalog-pill">{escape(t("catalog.partner_pill"))}</span>'
                    f'<span class="hl-catalog-pill muted">'
                    f"{escape(t('catalog.partner_status'))}</span>",
                    unsafe_allow_html=True,
                )
                rows = product_texts[
                    (product_texts.get("product_id") == product.product_id)
                    & (product_texts.get("locale") == locale)
                ]
                if not rows.empty:
                    row = rows.iloc[0]
                    st.write(str(row["craft_summary"]))
                    with st.expander(t("catalog.partner_heritage")):
                        st.write(str(row["cultural_story"]))
                        st.caption(str(row["meaning_summary"]))
                        st.caption(str(row["source_note"]))
                st.caption(t("catalog.partner_no_price"))
