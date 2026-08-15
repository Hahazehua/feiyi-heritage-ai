"""Global product header, navigation, language selector, and demo guide."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from heritagelink.i18n import Language, get_language, set_language, t


@dataclass(frozen=True, slots=True)
class HeaderAction:
    destination: str | None = None
    toggle_demo: bool = False
    reset_demo: bool = False


def render_global_header(*, destination: str, demo_active: bool) -> HeaderAction:
    st.markdown(
        '<header class="hl-app-header">'
        '<div class="hl-app-brand"><strong>HAHA</strong>'
        f"<span>{t('brand.full')}</span></div>"
        f'<div class="hl-app-positioning">{t("brand.positioning")}</div>'
        "</header>",
        unsafe_allow_html=True,
    )
    buyer, artisan, about, language = st.columns([1, 1, 1, 0.85])
    selected_destination: str | None = None
    if buyer.button(
        t("nav.buyer"),
        key="switch_to_buyer",
        type="primary" if destination == "buyer" else "secondary",
        width="stretch",
    ):
        selected_destination = "buyer"
    if artisan.button(
        t("nav.artisan"),
        key="switch_to_artisan",
        type="primary" if destination == "artisan" else "secondary",
        width="stretch",
    ):
        selected_destination = "artisan"
    if about.button(
        t("nav.about"),
        key="switch_to_about",
        type="primary" if destination == "about" else "secondary",
        width="stretch",
    ):
        selected_destination = "about"
    current = get_language()
    selected_language = language.selectbox(
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

    demo_column, reset_column = st.columns([1, 1])
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
    return HeaderAction(selected_destination, toggle_demo, reset_demo)


def render_demo_guide(step: int) -> None:
    steps = (
        t("demo.discover"),
        t("demo.recommend"),
        t("demo.artisan"),
        t("demo.growth"),
        t("demo.guardian"),
    )
    current = max(1, min(step, len(steps)))
    items = "".join(
        '<div class="hl-demo-step '
        + ("active" if index == current else "done" if index < current else "")
        + '"><span>'
        + str(index)
        + "</span><strong>"
        + label
        + "</strong></div>"
        for index, label in enumerate(steps, start=1)
    )
    progress = t("demo.step", current=current, total=len(steps))
    st.markdown(
        '<section class="hl-demo-guide">'
        f'<div class="hl-demo-guide-title">{progress}</div>'
        f'<div class="hl-demo-steps">{items}</div>'
        "</section>",
        unsafe_allow_html=True,
    )


__all__ = ["HeaderAction", "render_demo_guide", "render_global_header"]
