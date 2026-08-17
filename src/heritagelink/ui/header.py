"""Global product header, language selector, and competition demo guide.

Role navigation is deliberately absent: the entry screen picks a side and the
footer switches it.  What remains is identity — a masthead large enough to read
as a site rather than a toolbar — plus the two controls a visitor may need at
any moment, language and the competition demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from heritagelink.i18n import Language, get_language, set_language, t


@dataclass(frozen=True, slots=True)
class HeaderAction:
    toggle_demo: bool = False
    reset_demo: bool = False


def render_global_header(*, role: str, demo_active: bool) -> HeaderAction:
    """Render the masthead for the active role and report demo controls."""
    role_label = t("entry.artisan_title") if role == "artisan" else t("entry.buyer_title")
    st.markdown(
        '<header class="hl-app-header">'
        '<div class="hl-app-brand">'
        f"<strong>{escape(t('brand.name'))}</strong>"
        f'<span class="hl-app-tagline">{escape(t("brand.full"))}</span>'
        "</div>"
        '<div class="hl-app-meta">'
        f'<span class="hl-app-role">{escape(role_label)}</span>'
        f'<span class="hl-app-positioning">{escape(t("brand.positioning"))}</span>'
        "</div>"
        "</header>",
        unsafe_allow_html=True,
    )

    language_column, demo_column, reset_column = st.columns([1.2, 1, 1])
    current = get_language()
    selected_language = language_column.selectbox(
        t("nav.language"),
        (Language.ZH_CN, Language.EN_US),
        index=0 if current == Language.ZH_CN else 1,
        format_func=lambda item: t(
            "language.zh" if item == Language.ZH_CN else "language.en",
            language=current,
        ),
        key="global_language_selector",
        label_visibility="collapsed",
    )
    if selected_language is not current:
        set_language(selected_language, st.session_state)
        st.rerun()

    toggle_demo = demo_column.button(
        t("nav.demo_active") if demo_active else t("nav.competition_demo"),
        key="toggle_competition_demo",
        type="primary" if demo_active else "secondary",
        width="stretch",
    )
    reset_demo = False
    if demo_active:
        reset_demo = reset_column.button(
            t("nav.reset_demo"),
            key="reset_competition_demo",
            width="stretch",
        )
    return HeaderAction(toggle_demo=toggle_demo, reset_demo=reset_demo)


__all__ = ["HeaderAction", "render_global_header"]
