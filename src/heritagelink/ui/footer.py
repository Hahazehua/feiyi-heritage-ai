"""Site footer carrying the secondary navigation.

"How HAHA works" and the role switch both live here rather than in the header:
they are read-once destinations, and keeping them out of the main navigation is
what makes each half of the product feel like its own site.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from heritagelink.i18n import t


@dataclass(frozen=True, slots=True)
class FooterAction:
    show_about: bool = False
    switch_role: bool = False


def render_footer(*, on_about: bool = False) -> FooterAction:
    """Render the footer and report which secondary destination was chosen."""
    st.markdown('<hr class="hl-footer-rule" />', unsafe_allow_html=True)
    about_column, switch_column = st.columns(2)
    show_about = about_column.button(
        t("footer.about"),
        key="footer_about",
        type="primary" if on_about else "secondary",
        width="stretch",
    )
    switch_role = switch_column.button(
        t("footer.switch"),
        key="footer_switch_role",
        width="stretch",
    )
    st.markdown(
        f'<footer class="hl-footer" aria-label="{escape(t("footer.aria"))}">'
        f'<span class="hl-footer-brand">{escape(t("brand.name"))}</span>'
        f'<span class="hl-footer-tagline">{escape(t("brand.full"))}</span>'
        f'<span class="hl-footer-note">{escape(t("footer.note"))}</span>'
        "</footer>",
        unsafe_allow_html=True,
    )
    return FooterAction(show_about=show_about, switch_role=switch_role)


__all__ = ["FooterAction", "render_footer"]
