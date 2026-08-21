"""Dense, task-oriented inspiration cards for the landing state."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from pathlib import Path, PurePosixPath

import streamlit as st


@dataclass(frozen=True, slots=True)
class InspirationScene:
    key: str
    title: str
    subtitle: str
    prompt: str
    image_path: str
    image_alt: str


SCENES = (
    InspirationScene(
        "overseas",
        "为海外合作伙伴准备一份中国礼物",
        "商务 · 文化交流 · 企业纪念",
        "我想给海外合作伙伴准备一份有中国文化特色、适合正式商务场景的礼物。",
        "assets/catalog/products/met-69860.jpg",
        "中国刺绣与花鸟纹样构成的海外文化礼赠场景",
    ),
    InspirationScene(
        "professor",
        "给教授或长辈选一份有文化底蕴的礼物",
        "典雅 · 文房 · 敬意",
        "我想给教授或长辈准备一份典雅、有文化故事的礼物。",
        "assets/catalog/products/met-52074.jpg",
        "青瓷器物构成的教授与长辈礼赠场景",
    ),
    InspirationScene(
        "anniversary",
        "为企业周年寻找可定制纪念礼品",
        "周年 · 定制 · 品牌表达",
        "公司正在准备企业周年纪念礼品，希望支持品牌定制。",
        "assets/catalog/products/met-39646.jpg",
        "雕漆工艺构成的企业周年纪念场景",
    ),
    InspirationScene(
        "culture",
        "给外国朋友挑一份容易理解的中国文化礼物",
        "易理解 · 有故事 · 好携带",
        "我想给外国朋友挑一份容易理解、有中国文化特色的礼物。",
        "assets/catalog/products/met-48373.jpg",
        "青瓷茶器构成的中国文化伴手礼场景",
    ),
)


def _data_url(scene: InspirationScene, project_root: Path) -> str:
    image_file = project_root / PurePosixPath(scene.image_path)
    encoded = base64.b64encode(image_file.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _render_scene_card(
    scene: InspirationScene,
    project_root: Path,
    on_select: Callable[..., None],
    *,
    hero: bool,
) -> None:
    card_type = "hero" if hero else "small"
    with st.container(key=f"inspiration_card_{scene.key}"):
        st.markdown(
            f'<div class="hl-scene-card {card_type} scene-{escape(scene.key)}">'
            f'<img src="{_data_url(scene, project_root)}" '
            f'alt="{escape(scene.image_alt, quote=True)}">'
            '<div class="hl-scene-gradient"></div>'
            '<div class="hl-scene-overlay">'
            f"<strong>{escape(scene.title)}</strong>"
            f"<span>{escape(scene.subtitle)}</span>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        if st.button(scene.title, key=f"scene_{scene.key}", width="stretch"):
            on_select(scene.prompt, entry_source=f"inspiration:{scene.key}")
            st.rerun()


def render_inspiration_cards(
    project_root: Path,
    on_select: Callable[..., None],
) -> None:
    """Render one hero scene and three fixed shopping-entry scenes."""
    with st.container(key="inspiration_section"):
        st.markdown(
            '<div class="hl-section-heading" data-ui-section="inspiration">'
            '<span>推荐灵感</span><small>从一个熟悉的场景开始</small></div>',
            unsafe_allow_html=True,
        )
        _render_scene_card(SCENES[0], project_root, on_select, hero=True)
        columns = st.columns(3, gap="medium")
        for column, scene in zip(columns, SCENES[1:], strict=True):
            with column:
                _render_scene_card(scene, project_root, on_select, hero=False)
