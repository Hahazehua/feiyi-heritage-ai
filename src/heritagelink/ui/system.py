"""Reusable status, metric, and empty-state presentation primitives."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

import streamlit as st

from heritagelink.i18n import t

STATUS_LABEL_KEYS = {
    "confirmed": "common.verified",
    "artisan_confirmed": "common.artisan_confirmed",
    "verified": "common.verified",
    "unknown": "common.unknown",
    "pending_review": "common.pending_review",
    "draft": "common.draft",
    "reference_only": "common.reference_only",
    "recommendable": "common.recommendable",
    "archived": "common.archived",
    "ready": "common.ready",
    "needs_review": "common.needs_review",
    "low": "common.low_risk",
    "medium": "common.medium_risk",
    "high": "common.high_risk",
}


def status_label(status: object) -> str:
    value = getattr(status, "value", status)
    normalized = str(value).strip().casefold()
    return t(STATUS_LABEL_KEYS.get(normalized, "common.needs_verification"))


def status_tone(status: object) -> str:
    value = str(getattr(status, "value", status)).strip().casefold()
    if value in {"confirmed", "artisan_confirmed", "verified", "ready", "recommendable", "low"}:
        return "ok"
    if value in {"draft", "pending_review", "needs_review", "medium"}:
        return "wait"
    if value in {"high", "failed", "blocked"}:
        return "risk"
    return "neutral"


def render_status_badge(status: object, *, label: str | None = None) -> None:
    text = label or status_label(status)
    tone = status_tone(status)
    st.markdown(
        f'<span class="hl-status-badge {tone}">{escape(text)}</span>',
        unsafe_allow_html=True,
    )


def status_badge_markup(status: object, *, label: str | None = None) -> str:
    text = label or status_label(status)
    return f'<span class="hl-status-badge {status_tone(status)}">{escape(text)}</span>'


def render_metric_strip(items: Iterable[tuple[str, str, str | None]]) -> None:
    cards = "".join(
        '<div class="hl-metric-card">'
        f'<span class="hl-metric-label">{escape(label)}</span>'
        f"<strong>{escape(value)}</strong>"
        f"<small>{escape(note or '')}</small>"
        "</div>"
        for label, value, note in items
    )
    st.markdown(f'<div class="hl-metric-strip">{cards}</div>', unsafe_allow_html=True)


def render_empty_state(title: str, copy: str, *, icon: str = "◇") -> None:
    st.markdown(
        '<section class="hl-empty-state">'
        f'<span aria-hidden="true">{escape(icon)}</span>'
        f"<strong>{escape(title)}</strong>"
        f"<p>{escape(copy)}</p>"
        "</section>",
        unsafe_allow_html=True,
    )


def render_demo_badge() -> None:
    render_status_badge("draft", label=t("common.demo_data"))


__all__ = [
    "render_demo_badge",
    "render_empty_state",
    "render_metric_strip",
    "render_status_badge",
    "status_badge_markup",
    "status_label",
    "status_tone",
]
