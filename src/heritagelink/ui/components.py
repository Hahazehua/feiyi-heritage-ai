# ruff: noqa: E501
"""Small reusable presentation helpers for the conversational experience."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path, PurePosixPath

import streamlit as st

STEPS = (
    ("describe", "01 描述需求"),
    ("confirm", "02 确认理解"),
    ("recommend", "03 查看推荐"),
    ("culture", "04 文化与定制"),
    ("inquiry", "05 商家询单"),
)


def render_hero(*, compact: bool = False) -> None:
    """Render the expansive landing hero or its compact conversation variant."""
    if compact:
        st.markdown(
            """
            <header class="hl-brandbar" data-ui-state="conversation">
              <div><strong>HAHA</strong><span>Heritage Artisans, Horizons Ahead</span></div>
              <span class="hl-brandbar-note">您的礼赠顾问</span>
            </header>
            """,
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        """
        <section class="hl-hero" data-ui-state="landing">
          <div class="hl-wordmark"><strong>HAHA</strong><span>Heritage Artisans, Horizons Ahead</span></div>
          <div class="hl-eyebrow">AI GIFT CONCIERGE · 飞颐礼遇</div>
          <h1 class="hl-brand">选一份真正有意义的礼物</h1>
          <p class="hl-value">告诉我送给谁、为什么送，<br>我会从传统匠艺中帮你找到合适的选择。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str,
    *,
    kicker: str,
    copy: str | None = None,
    section: str,
) -> None:
    """Render a consistent, semantic heading for a major advisor section."""
    description = f'<p class="hl-section-copy">{escape(copy)}</p>' if copy else ""
    st.markdown(
        f'<header class="hl-section-header" data-ui-section="{escape(section, quote=True)}">'
        '<div class="hl-section-heading-copy">'
        f'<span class="hl-section-kicker">{escape(kicker)}</span>'
        f'<h2>{escape(title)}</h2>{description}</div></header>',
        unsafe_allow_html=True,
    )


def render_progress(stage: str) -> None:
    current = next((index for index, item in enumerate(STEPS) if item[0] == stage), 0)
    parts = []
    for index, (_, label) in enumerate(STEPS):
        state = "active" if index == current else "done" if index < current else ""
        # aria-current tells a screen reader which step is live; the visual
        # cue is colour and border weight alone, which it cannot perceive.
        marker = ' aria-current="step"' if index == current else ""
        parts.append(f'<li class="hl-step {state}"{marker}>{escape(label)}</li>')
    st.markdown(
        f'<nav class="hl-stepper" aria-label="需求收集进度">'
        f'<ol class="hl-stepper-list">{"".join(parts)}</ol></nav>',
        unsafe_allow_html=True,
    )


def section_intro(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f'<div class="hl-kicker">{escape(kicker)}</div><h2>{escape(title)}</h2>'
        f'<p class="hl-copy">{escape(copy)}</p>',
        unsafe_allow_html=True,
    )


def product_image(image_path: str, image_alt: str, *, uncropped: bool = False) -> None:
    """Render a validated local product image from the repository assets directory.

    The theme crops images to 4:3 so the catalogue reads as a consistent grid.
    A framed artwork loses its frame, inscription and seals that way, so such
    works opt out and are shown whole.
    """
    project_root = Path(__file__).parents[3]
    source = str(project_root / PurePosixPath(image_path))
    if not uncropped:
        st.image(source, caption=image_alt, width="stretch")
        return
    # A keyed container is the only reliable CSS hook here: Streamlit wraps
    # each element in its own node, so a sibling marker div never lands next
    # to the image it was meant to describe.
    # Streamlit rejects a duplicate key and one page can hold several uncropped
    # works, so the key carries the image name. The theme matches it by prefix.
    slug = re.sub(r"[^a-z0-9]+", "-", PurePosixPath(image_path).stem.lower()).strip("-")
    with st.container(key=f"hl-uncropped-image-{slug}"):
        st.image(source, caption=image_alt, width="stretch")


def badges(items: list[tuple[str, str]]) -> None:
    markup = "".join(
        f'<span class="hl-badge {escape(kind)}">{escape(text)}</span>' for text, kind in items
    )
    st.markdown(f'<div class="hl-badges">{markup}</div>', unsafe_allow_html=True)
