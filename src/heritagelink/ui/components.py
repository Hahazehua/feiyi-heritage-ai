# ruff: noqa: E501
"""Small reusable presentation helpers for the conversational experience."""

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
          <div class="hl-eyebrow">HAHA · HELP ARTISAN HAPPY AGAIN</div>
          <h1 class="hl-brand">HAHA｜飞颐礼遇</h1>
          <div class="hl-value">连接非遗手艺人与全球礼赠及商业机会</div>
          <p class="hl-copy">让手艺人因被看见、被尊重、获得持续机会而再次绽放笑容。我们以 AI 连接全国 20 万件非遗产品资源的长期愿景，从一份真实礼赠需求开始，为您匹配有文化依据的礼品方案。</p>
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
