"""Competition-facing HAHA overview and platform story."""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.i18n import t
from heritagelink.ui.system import render_demo_badge


def render_buyer_hero() -> None:
    st.markdown(
        '<section class="hl-hero hl-home-hero">'
        f'<div class="hl-eyebrow">{escape(t("home.eyebrow"))}</div>'
        '<h1 class="hl-brand">HAHA｜飞觞礼遇</h1>'
        f'<div class="hl-value">{escape(t("buyer.title"))}</div>'
        f'<p class="hl-copy">{escape(t("buyer.subtitle"))}</p>'
        "</section>",
        unsafe_allow_html=True,
    )
    render_demo_badge()


def render_platform_story(*, compact: bool = True) -> None:
    st.markdown(f"## {t('home.how_title')}")
    cards = (
        ("01", t("home.digitize"), t("home.digitize_copy")),
        ("02", t("home.grow"), t("home.grow_copy")),
        ("03", t("home.connect"), t("home.connect_copy")),
    )
    markup = "".join(
        '<article class="hl-story-card">'
        f"<span>{number}</span><h3>{escape(title)}</h3><p>{escape(copy)}</p>"
        "</article>"
        for number, title, copy in cards
    )
    st.markdown(f'<div class="hl-story-grid">{markup}</div>', unsafe_allow_html=True)
    if not compact:
        render_value_system()


def render_value_system() -> None:
    st.markdown(f"## {t('home.why_title')}")
    items = (
        (t("home.trusted_title"), t("home.trusted_copy")),
        (t("home.team_title"), t("home.team_copy")),
        (t("home.guardian_title"), t("home.guardian_copy")),
    )
    markup = "".join(
        '<article class="hl-value-item">'
        f"<strong>{escape(title)}</strong><p>{escape(copy)}</p>"
        "</article>"
        for title, copy in items
    )
    st.markdown(f'<div class="hl-value-grid">{markup}</div>', unsafe_allow_html=True)


def render_about_page() -> None:
    st.markdown(
        '<section class="hl-hero hl-about-hero">'
        f'<div class="hl-eyebrow">{escape(t("brand.full"))}</div>'
        f'<h1 class="hl-brand">{escape(t("about.title"))}</h1>'
        f'<p class="hl-copy">{escape(t("about.subtitle"))}</p>'
        "</section>",
        unsafe_allow_html=True,
    )
    render_platform_story(compact=False)
    labels = (
        t("home.story_artisan"),
        t("home.story_passport"),
        t("home.story_growth"),
        t("home.story_campaign"),
        t("home.story_demand"),
    )
    # The arrows carry no meaning a list does not already convey, so they are
    # hidden from assistive tech rather than read out between every step.
    flow = '<span class="hl-story-arrow" aria-hidden="true">→</span>'.join(
        f'<li class="hl-story-node">{escape(label)}</li>' for label in labels
    )
    st.markdown(
        f'<ol class="hl-platform-flow" aria-label="{escape(t("home.how_title"))}">{flow}</ol>',
        unsafe_allow_html=True,
    )


__all__ = [
    "render_about_page",
    "render_buyer_hero",
    "render_platform_story",
    "render_value_system",
]
