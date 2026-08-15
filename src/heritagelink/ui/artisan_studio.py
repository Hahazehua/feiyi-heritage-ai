"""Presentation helpers for the single-page Artisan Studio experience.

The workflow itself belongs to :mod:`heritagelink.artisan_studio`.  These
helpers deliberately do not read or mutate Streamlit session state, which
keeps navigation and draft persistence under the application's control.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.i18n import t

_STAGE_INDEX = {
    "landing": 0,
    "story": 0,
    "step_1": 0,
    "commercial": 1,
    "culture": 2,
    "organize": 1,
    "step_2": 1,
    "review": 2,
    "passport": 2,
    "submitted": 2,
    "confirm": 2,
    "step_3": 2,
}


def render_artisan_hero() -> None:
    """Render the Artisan Studio hero without adding navigation or widgets."""
    st.markdown(
        f"""
        <section class="hl-hero hl-artisan-hero">
          <div class="hl-eyebrow">{t("artisan.eyebrow")}</div>
          <h1 class="hl-brand">{t("artisan.title")}</h1>
          <p class="hl-copy">{t("artisan.subtitle")}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_artisan_journey() -> None:
    """Explain the three-part onboarding journey in a compact branded panel."""
    journey_steps = (
        ("01", t("artisan.journey_tell"), t("artisan.journey_tell_copy")),
        ("02", t("artisan.journey_structure"), t("artisan.journey_structure_copy")),
        ("03", t("artisan.journey_confirm"), t("artisan.journey_confirm_copy")),
    )
    cards = "".join(
        (
            '<div class="hl-artisan-step">'
            f'<span class="hl-artisan-step-number">{number}</span>'
            f"<strong>{escape(title)}</strong>"
            f"<p>{escape(copy)}</p>"
            "</div>"
        )
        for number, title, copy in journey_steps
    )
    st.markdown(
        f'<section class="hl-artisan-journey" '
        f'aria-label="{escape(t("artisan.journey_aria"))}">{cards}</section>',
        unsafe_allow_html=True,
    )


def render_artisan_progress(stage: str) -> None:
    """Render three-step progress for a supported application-level stage.

    Detailed workflow stages are intentionally folded into three concepts:
    telling the story, organizing the material, and human confirmation.
    """
    normalized = stage.strip().casefold()
    if normalized not in _STAGE_INDEX:
        supported = ", ".join(sorted(_STAGE_INDEX))
        raise ValueError(f"未知 Artisan Studio 阶段；支持：{supported}")
    current = _STAGE_INDEX[normalized]
    progress_steps = (
        t("artisan.progress.story"),
        t("artisan.progress.commercial"),
        t("artisan.progress.culture"),
    )
    items: list[str] = []
    for index, title in enumerate(progress_steps):
        state = "active" if index == current else "done" if index < current else ""
        marker = "✓" if index < current else f"{index + 1:02d}"
        # The check glyph and colour are the only visual completion cues, so
        # state has to reach assistive tech through aria-current and text.
        current_attr = ' aria-current="step"' if index == current else ""
        items.append(
            f'<li class="hl-artisan-progress-step {state}"{current_attr}>'
            f'<span aria-hidden="true">{marker}</span>'
            f"<strong>{escape(title)}</strong>"
            "</li>"
        )
    st.markdown(
        f'<nav class="hl-artisan-progress" '
        f'aria-label="{escape(t("artisan.progress_aria"))}">'
        f'<ol class="hl-artisan-progress-list">{"".join(items)}</ol></nav>',
        unsafe_allow_html=True,
    )


def render_artisan_section(kicker: str, title: str, copy: str) -> None:
    """Render escaped section copy shared by progressive intake screens."""
    st.markdown(
        '<header class="hl-artisan-section">'
        f'<div class="hl-kicker">{escape(kicker)}</div>'
        f"<h2>{escape(title)}</h2>"
        f'<p class="hl-copy">{escape(copy)}</p>'
        "</header>",
        unsafe_allow_html=True,
    )


__all__ = [
    "render_artisan_hero",
    "render_artisan_journey",
    "render_artisan_progress",
    "render_artisan_section",
]
