# ruff: noqa: E501
"""Small reusable presentation helpers for the five-stage experience."""

from __future__ import annotations

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


def render_hero() -> None:
    st.markdown(
        """
        <section class="hl-hero">
          <div class="hl-eyebrow">AI · INTANGIBLE CULTURAL HERITAGE · GIFTING</div>
          <h1 class="hl-brand">飞颐礼遇</h1>
          <div class="hl-en">HERITAGELINK AI</div>
          <div class="hl-value">让中国非遗礼赠需求更清晰、更有文化依据、更便于商家确认。</div>
          <p class="hl-copy">说出赠礼对象、预算与场景，AI 顾问将整理需求，并从当前产品中提供可解释的匹配方案与商家沟通材料。</p>
          <div class="hl-tags"><span class="hl-tag">可解释推荐</span><span class="hl-tag">中英双语</span><span class="hl-tag">定制需求整理</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_progress(stage: str) -> None:
    current = next((index for index, item in enumerate(STEPS) if item[0] == stage), 0)
    parts = []
    for index, (_, label) in enumerate(STEPS):
        state = "active" if index == current else "done" if index < current else ""
        parts.append(f'<div class="hl-step {state}">{escape(label)}</div>')
    st.markdown(f'<nav class="hl-stepper">{"".join(parts)}</nav>', unsafe_allow_html=True)


def section_intro(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f'<div class="hl-kicker">{escape(kicker)}</div><h2>{escape(title)}</h2>'
        f'<p class="hl-copy">{escape(copy)}</p>',
        unsafe_allow_html=True,
    )


def product_image(image_path: str, image_alt: str) -> None:
    """Render a validated local product image from the repository assets directory."""
    project_root = Path(__file__).parents[3]
    st.image(
        str(project_root / PurePosixPath(image_path)),
        caption=image_alt,
        width="stretch",
    )


def badges(items: list[tuple[str, str]]) -> None:
    markup = "".join(
        f'<span class="hl-badge {escape(kind)}">{escape(text)}</span>' for text, kind in items
    )
    st.markdown(f'<div class="hl-badges">{markup}</div>', unsafe_allow_html=True)
