"""Customer-facing product comparison presentation.

The comparison service owns every fact and conclusion.  This module only turns
its structured result into a responsive, shopping-style decision aid.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from typing import TYPE_CHECKING, Any

import streamlit as st

from heritagelink.i18n import t

if TYPE_CHECKING:
    from heritagelink.comparison_models import ProductComparisonResult


_UNKNOWN_VALUES = frozenset(
    {
        "",
        "unknown",
        "待确认",
        "needs confirmation",
        "暂无可靠信息",
        "暂时无可靠信息",
        "价格待确认",
    }
)


def _attribute(value: object, *names: str) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        candidate = getattr(value, name, None)
        if candidate is not None:
            return candidate
    return None


def _state_label(value: str) -> str | None:
    key = {
        "unknown": "comparison.unknown",
        "待确认": "comparison.unknown",
        "verified_yes": "comparison.verified_yes",
        "verified_no": "comparison.verified_no",
        "not_applicable": "comparison.not_applicable",
    }.get(value.strip().lower())
    return t(key) if key else None


def _display(value: object, *, fallback: str | None = None) -> str:
    fallback = fallback if fallback is not None else t("comparison.unknown")
    if value is None:
        return fallback
    if isinstance(value, Mapping):
        preferred = _attribute(value, "display", "display_text", "label", "value", "status")
        return _display(preferred, fallback=fallback)
    evidence_display = getattr(value, "display", None)
    evidence_state = getattr(value, "state", None)
    if evidence_display is not None:
        state_text = _display(evidence_state, fallback="")
        if state_text == "待确认":
            return "待确认"
        return _display(evidence_display, fallback=fallback)
    if isinstance(value, str):
        normalized = value.strip()
        if state_label := _state_label(normalized):
            return state_label
        return normalized or fallback
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        parts = [_display(item, fallback="") for item in value]
        visible = [part for part in parts if part]
        return "、".join(dict.fromkeys(visible)) if visible else fallback
    enum_value = getattr(value, "value", None)
    if enum_value is not None and enum_value is not value:
        return _display(enum_value, fallback=fallback)
    return str(value).strip() or fallback


def _combine(*values: object, fallback: str | None = None) -> str:
    fallback = fallback if fallback is not None else t("comparison.unknown")
    parts = [_display(value, fallback="") for value in values if value is not None]
    visible = [part for part in parts if part]
    return " · ".join(dict.fromkeys(visible)) if visible else fallback


def _is_unknown(text: str) -> bool:
    return text.strip().lower() in _UNKNOWN_VALUES or text == t("comparison.unknown")


def _safe(text: object) -> str:
    return escape(str(text), quote=True)


def _cell(value: object, *, css_class: str = "hl-comparison-cell") -> str:
    text = _display(value)
    if _is_unknown(text):
        content = f'<span class="hl-comparison-unknown">{_safe(t("comparison.unknown"))}</span>'
    else:
        content = _safe(text)
    return f'<div class="{css_class}" role="cell">{content}</div>'


def _best_for(result: object, item: object) -> str:
    direct = _attribute(item, "best_for")
    if direct is not None:
        return _display(direct)
    values = _attribute(result, "best_for")
    product_id = str(_attribute(item, "product_id") or "")
    if isinstance(values, Mapping):
        labels = [_display(label) for label, value in values.items() if str(value) == product_id]
        return " · ".join(labels) if labels else t("comparison.unknown")
    return t("comparison.unknown")


def _item_rows(result: object, item: object) -> tuple[tuple[str, str], ...]:
    return (
        (
            t("comparison.best_for"),
            _combine(_best_for(result, item), _attribute(item, "recipient_fit")),
        ),
        (t("comparison.occasion"), _display(_attribute(item, "scene_fit"))),
        (t("comparison.style"), _display(_attribute(item, "style_fit"))),
        (t("comparison.cultural"), _display(_attribute(item, "symbolism_fit"))),
        (
            t("comparison.budget"),
            _combine(
                _attribute(item, "price", "price_display"),
                _attribute(item, "price_fit"),
            ),
        ),
        (
            t("comparison.customization"),
            _display(_attribute(item, "customization", "customization_summary")),
        ),
        (
            t("comparison.international"),
            _combine(
                _attribute(item, "shipping", "international_relevance"),
                _attribute(item, "portability_summary"),
            ),
        ),
        (
            t("comparison.quantity"),
            _display(_attribute(item, "quantity", "quantity_summary", "quantity_fit")),
        ),
        (
            t("comparison.delivery"),
            _display(_attribute(item, "lead_time", "lead_time_summary")),
        ),
        (
            t("comparison.highlights"),
            _combine(
                _attribute(item, "strengths", "cultural_strengths"),
                _attribute(item, "practical_strengths"),
                fallback=t("comparison.unknown"),
            ),
        ),
        (
            t("comparison.watch"),
            _display(_attribute(item, "limitations"), fallback=t("comparison.no_limits")),
        ),
    )


def _desktop_markup(result: object, items: tuple[object, ...]) -> str:
    count = len(items)
    header_cells = [
        f'<div class="hl-comparison-label" role="columnheader">{_safe(t("comparison.focus"))}</div>'
    ]
    for index, item in enumerate(items, start=1):
        rank = _attribute(item, "rank_position") or index
        name = _attribute(item, "product_name", "product_name_zh") or _attribute(item, "product_id")
        header_cells.append(
            '<div class="hl-comparison-product" role="columnheader">'
            f"<span>{_safe(t('comparison.rank', rank=rank))}</span>"
            f"<strong>{_safe(_display(name))}</strong></div>"
        )
    rows = [
        '<div class="hl-comparison-row hl-comparison-row-head" role="row">'
        + "".join(header_cells)
        + "</div>"
    ]
    item_rows = [_item_rows(result, item) for item in items]
    for row_index, (label, _) in enumerate(item_rows[0]):
        cells = [f'<div class="hl-comparison-label" role="rowheader">{_safe(label)}</div>']
        cells.extend(_cell(rows_for_item[row_index][1]) for rows_for_item in item_rows)
        rows.append('<div class="hl-comparison-row" role="row">' + "".join(cells) + "</div>")
    return (
        '<div class="hl-comparison-desktop" role="table" '
        f'aria-label="{_safe(t("comparison.table_label"))}" '
        f'style="--hl-comparison-count:{count}">' + "".join(rows) + "</div>"
    )


def _mobile_markup(result: object, items: tuple[object, ...]) -> str:
    cards: list[str] = []
    for index, item in enumerate(items, start=1):
        rank = _attribute(item, "rank_position") or index
        name = _attribute(item, "product_name", "product_name_zh") or _attribute(item, "product_id")
        facts = []
        for label, value in _item_rows(result, item):
            text = _display(value)
            content = (
                f'<span class="hl-comparison-unknown">{_safe(t("comparison.unknown"))}</span>'
                if _is_unknown(text)
                else _safe(text)
            )
            facts.append(
                '<div class="hl-comparison-mobile-row">'
                f"<span>{_safe(label)}</span><strong>{content}</strong></div>"
            )
        cards.append(
            '<article class="hl-comparison-card">'
            f'<div class="hl-comparison-card-rank">'
            f"{_safe(t('comparison.rank', rank=rank))}</div>"
            f"<h3>{_safe(_display(name))}</h3>{''.join(facts)}</article>"
        )
    return '<div class="hl-comparison-mobile">' + "".join(cards) + "</div>"


def _list_markup(title: str, values: object, *, css_class: str = "") -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        items = [values] if values.strip() else []
    elif isinstance(values, Iterable) and not isinstance(values, (bytes, bytearray, Mapping)):
        items = [_display(value, fallback="") for value in values]
    else:
        items = [_display(values, fallback="")]
    visible = [item for item in items if item]
    if not visible:
        return ""
    classes = f"hl-comparison-notes {css_class}".strip()
    body = "".join(f"<li>{_safe(item)}</li>" for item in visible)
    return f'<div class="{classes}"><strong>{_safe(title)}</strong><ul>{body}</ul></div>'


def _summary_markup(result: object) -> str:
    recommendation = _attribute(result, "recommendation_for_current_user")
    reason = _attribute(result, "recommendation_reason")
    recommendation_markup = ""
    if recommendation is not None or reason is not None:
        recommended_name = recommendation
        for item in _attribute(result, "items") or ():
            if str(_attribute(item, "product_id")) == str(recommendation):
                recommended_name = _attribute(item, "product_name", "product_name_zh")
                break
        recommendation_text = _combine(
            t("comparison.prefer", name=_display(recommended_name))
            if recommended_name is not None
            else None,
            reason,
        )
        recommendation_markup = (
            '<div class="hl-comparison-recommendation">'
            f"<span>{_safe(t('comparison.for_this_need'))}</span>"
            f"<strong>{_safe(recommendation_text)}</strong></div>"
        )
    tradeoffs = _list_markup(t("comparison.tradeoffs"), _attribute(result, "tradeoffs"))
    unknowns = _list_markup(
        t("comparison.unknowns"),
        _attribute(result, "unknowns", "unknown_or_unverified"),
        css_class="hl-comparison-notes-unknown",
    )
    context = _attribute(result, "context_summary")
    explanation = _attribute(
        result,
        "explanation",
        "ai_explanation",
        "customer_summary",
        "deterministic_summary",
    )
    details = ""
    if context is not None or explanation is not None:
        paragraphs = "".join(
            f"<p>{_safe(_display(value))}</p>"
            for value in (context, explanation)
            if value is not None
        )
        details = (
            '<details class="hl-comparison-why"><summary>'
            f"{_safe(t('comparison.why'))}</summary>"
            f"{paragraphs}</details>"
        )
    return recommendation_markup + tradeoffs + unknowns + details


def render_product_comparison(result: ProductComparisonResult) -> None:
    """Render a structured comparison without exposing scores or technical state."""
    raw_items = _attribute(result, "items")
    if not isinstance(raw_items, Iterable) or isinstance(raw_items, (str, bytes, Mapping)):
        return
    items = tuple(raw_items)
    if not items:
        return
    context = _attribute(result, "context_summary")
    context_markup = (
        f'<p class="hl-comparison-context">'
        f"{_safe(t('comparison.context', context=_display(context)))}</p>"
        if context is not None
        else ""
    )
    markup = (
        '<section class="hl-comparison-shell" aria-labelledby="hl-comparison-title">'
        '<div class="hl-comparison-heading">'
        f'<span class="hl-comparison-kicker">{_safe(t("comparison.kicker"))}</span>'
        f'<h2 id="hl-comparison-title">'
        f"{_safe(t(f'comparison.title_{len(items)}', count=len(items)))}</h2>"
        f"{context_markup}</div>"
        f"{_desktop_markup(result, items)}"
        f"{_mobile_markup(result, items)}"
        f"{_summary_markup(result)}"
        "</section>"
    )
    st.markdown(markup, unsafe_allow_html=True)
