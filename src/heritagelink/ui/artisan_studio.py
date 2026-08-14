"""Presentation helpers for the single-page Artisan Studio experience.

The workflow itself belongs to :mod:`heritagelink.artisan_studio`.  These
helpers deliberately do not read or mutate Streamlit session state, which
keeps navigation and draft persistence under the application's control.
"""

from __future__ import annotations

from html import escape

import streamlit as st

_JOURNEY_STEPS = (
    ("01", "讲述作品", "用你熟悉的方式介绍作品、工艺、地域与故事。"),
    ("02", "AI 协助整理", "将你提供的资料整理为结构化的中英文草稿。"),
    ("03", "确认并建立文化护照", "由你确认文化与商业事实，再提交审核。"),
)

_PROGRESS_STEPS = ("讲述作品", "商业信息", "文化与来源")

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
        """
        <section class="hl-hero hl-artisan-hero">
          <div class="hl-eyebrow">HAHA · ARTISAN STUDIO</div>
          <h1 class="hl-brand">让你的作品被世界更好地理解</h1>
          <div class="hl-value">从作品与故事出发，建立可供全球买家理解的文化资料。</div>
          <p class="hl-copy">告诉 HAHA 你的作品是什么、来自哪里以及它背后的故事。
          AI 会帮助你整理成适合全球买家理解的中英文商品资料；所有文化与商业事实，
          最终都由你确认。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_artisan_journey() -> None:
    """Explain the three-part onboarding journey in a compact branded panel."""
    cards = "".join(
        (
            '<div class="hl-artisan-step">'
            f'<span class="hl-artisan-step-number">{number}</span>'
            f"<strong>{escape(title)}</strong>"
            f"<p>{escape(copy)}</p>"
            "</div>"
        )
        for number, title, copy in _JOURNEY_STEPS
    )
    st.markdown(
        f'<section class="hl-artisan-journey" aria-label="添加作品的三个步骤">{cards}</section>',
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
    items: list[str] = []
    for index, title in enumerate(_PROGRESS_STEPS):
        state = "active" if index == current else "done" if index < current else ""
        marker = "✓" if index < current else f"{index + 1:02d}"
        items.append(
            f'<div class="hl-artisan-progress-step {state}">'
            f'<span aria-hidden="true">{marker}</span>'
            f"<strong>{escape(title)}</strong>"
            "</div>"
        )
    st.markdown(
        f'<nav class="hl-artisan-progress" aria-label="作品录入进度">{"".join(items)}</nav>',
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
