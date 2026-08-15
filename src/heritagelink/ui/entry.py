"""Role chooser shown before either product surface is revealed.

Buyers and artisans use different halves of the product, so the entry screen
asks once and the rest of the session stays inside that half.  The choice is
recoverable from the footer rather than the main navigation, which keeps the
header free of a control most visitors only ever use once.

This is also the only place the brand gets to introduce itself, so the
wordmark leads and the acronym is spelled out beneath it.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.i18n import t

BUYER = "buyer"
ARTISAN = "artisan"


def render_entry_screen() -> str | None:
    """Render the chooser and return the picked role, or None while waiting."""
    _render_backdrop()
    st.markdown(
        '<section class="hl-entry" aria-labelledby="hl-entry-title">'
        f'<p class="hl-entry-wordmark">{escape(t("brand.name"))}</p>'
        f'<p class="hl-entry-expansion">{escape(t("brand.full"))}</p>'
        f'<p class="hl-entry-mission">{escape(t("brand.primary_message"))}</p>'
        '<span class="hl-entry-divider" aria-hidden="true"></span>'
        f'<h1 class="hl-entry-prompt" id="hl-entry-title">{escape(t("entry.title"))}</h1>'
        f'<p class="hl-entry-sub">{escape(t("entry.subtitle"))}</p>'
        "</section>",
        unsafe_allow_html=True,
    )

    buyer_column, artisan_column = st.columns(2, gap="large")
    choice: str | None = None

    with buyer_column:
        _render_card(
            index=1,
            title=t("entry.buyer_title"),
            copy=t("entry.buyer_copy"),
        )
        if st.button(
            t("entry.buyer_cta"),
            key="entry_choose_buyer",
            type="primary",
            width="stretch",
        ):
            choice = BUYER

    with artisan_column:
        _render_card(
            index=2,
            title=t("entry.artisan_title"),
            copy=t("entry.artisan_copy"),
        )
        if st.button(
            t("entry.artisan_cta"),
            key="entry_choose_artisan",
            type="primary",
            width="stretch",
        ):
            choice = ARTISAN

    return choice


def _render_backdrop() -> None:
    """Drifting colour fields behind the chooser.

    Rendered only here, so the rest of the product keeps its flat paper
    ground.  Purely decorative, hence hidden from assistive tech; the
    reduced-motion rule in the theme freezes it in place.
    """
    st.markdown(
        '<div class="hl-entry-bg" aria-hidden="true">'
        '<span class="hl-entry-orb hl-entry-orb-1"></span>'
        '<span class="hl-entry-orb hl-entry-orb-2"></span>'
        '<span class="hl-entry-orb hl-entry-orb-3"></span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_card(*, index: int, title: str, copy: str) -> None:
    """One choice panel.  The index drives the staggered entrance animation."""
    st.markdown(
        f'<article class="hl-entry-card hl-entry-card-{index}">'
        f'<span class="hl-entry-card-index" aria-hidden="true">{index:02d}</span>'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(copy)}</p>"
        "</article>",
        unsafe_allow_html=True,
    )


__all__ = ["ARTISAN", "BUYER", "render_entry_screen"]
