"""Role chooser shown before either product surface is revealed.

Buyers and artisans use different halves of the product, so the entry screen
asks once and the rest of the session stays inside that half.  The choice is
recoverable from the footer rather than the main navigation, which keeps the
header free of a control most visitors only ever use once.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.i18n import t

BUYER = "buyer"
ARTISAN = "artisan"


def render_entry_screen() -> str | None:
    """Render the chooser and return the picked role, or None while waiting."""
    st.markdown(
        '<section class="hl-entry" aria-labelledby="hl-entry-title">'
        f'<div class="hl-eyebrow">{escape(t("brand.full"))}</div>'
        f'<h1 class="hl-brand hl-entry-brand" id="hl-entry-title">{escape(t("entry.title"))}</h1>'
        f'<p class="hl-copy hl-entry-sub">{escape(t("entry.subtitle"))}</p>'
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
