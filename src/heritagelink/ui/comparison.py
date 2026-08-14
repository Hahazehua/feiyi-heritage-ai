"""Customer-facing product comparison presentation.

The comparison service owns every fact and conclusion.  This module only turns
its structured result into a responsive, shopping-style decision aid.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from typing import TYPE_CHECKING, Any

import streamlit as st

if TYPE_CHECKING:
    from heritagelink.comparison_models import ProductComparisonResult


_SAFE_STATE_LABELS = {
    "unknown": "待确认",
    "verified_yes": "已确认支持",
    "verified_no": "已确认不支持",
    "not_applicable": "不适用",
}
_UNKNOWN_VALUES = frozenset(
    {
        "",
        "unknown",
        "待确认",
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


def _display(value: object, *, fallback: str = "待确认") -> str:
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
        if normalized.lower() in _SAFE_STATE_LABELS:
            return _SAFE_STATE_LABELS[normalized.lower()]
        return normalized or fallback
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        parts = [_display(item, fallback="") for item in value]
        visible = [part for part in parts if part]
        return "、".join(dict.fromkeys(visible)) if visible else fallback
    enum_value = getattr(value, "value", None)
    if enum_value is not None and enum_value is not value:
        return _display(enum_value, fallback=fallback)
    return str(value).strip() or fallback


def _combine(*values: object, fallback: str = "待确认") -> str:
    parts = [_display(value, fallback="") for value in values if value is not None]
    visible = [part for part in parts if part]
    return " · ".join(dict.fromkeys(visible)) if visible else fallback


def _is_unknown(text: str) -> bool:
    return text.strip().lower() in _UNKNOWN_VALUES


def _safe(text: object) -> str:
    return escape(str(text), quote=True)


def _cell(value: object, *, css_class: str = "hl-comparison-cell") -> str:
    text = _display(value)
    if _is_unknown(text):
        content = '<span class="hl-comparison-unknown">待确认</span>'
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
        return "、".join(labels) if labels else "待确认"
    return "待确认"


def _item_rows(result: object, item: object) -> tuple[tuple[str, str], ...]:
    return (
        ("更适合", _combine(_best_for(result, item), _attribute(item, "recipient_fit"))),
        ("适用场景", _display(_attribute(item, "scene_fit"))),
        ("整体风格", _display(_attribute(item, "style_fit"))),
        ("文化表达", _display(_attribute(item, "symbolism_fit"))),
        (
            "预算",
            _combine(
                _attribute(item, "price", "price_display"),
                _attribute(item, "price_fit"),
            ),
        ),
        (
            "定制",
            _display(_attribute(item, "customization", "customization_summary")),
        ),
        (
            "国际礼赠",
            _combine(
                _attribute(item, "shipping", "international_relevance"),
                _attribute(item, "portability_summary"),
            ),
        ),
        (
            "数量",
            _display(_attribute(item, "quantity", "quantity_summary", "quantity_fit")),
        ),
        ("交付", _display(_attribute(item, "lead_time", "lead_time_summary"))),
        (
            "主要特点",
            _combine(
                _attribute(item, "strengths", "cultural_strengths"),
                _attribute(item, "practical_strengths"),
                fallback="待确认",
            ),
        ),
        ("需要留意", _display(_attribute(item, "limitations"), fallback="暂无特别限制")),
    )


def _desktop_markup(result: object, items: tuple[object, ...]) -> str:
    count = len(items)
    header_cells = ['<div class="hl-comparison-label" role="columnheader">比较重点</div>']
    for index, item in enumerate(items, start=1):
        rank = _attribute(item, "rank_position") or index
        name = _attribute(item, "product_name", "product_name_zh") or _attribute(item, "product_id")
        header_cells.append(
            '<div class="hl-comparison-product" role="columnheader">'
            f"<span>推荐 {_safe(rank)}</span><strong>{_safe(_display(name))}</strong></div>"
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
        f'aria-label="礼品比较" style="--hl-comparison-count:{count}">' + "".join(rows) + "</div>"
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
                '<span class="hl-comparison-unknown">待确认</span>'
                if _is_unknown(text)
                else _safe(text)
            )
            facts.append(
                '<div class="hl-comparison-mobile-row">'
                f"<span>{_safe(label)}</span><strong>{content}</strong></div>"
            )
        cards.append(
            '<article class="hl-comparison-card">'
            f'<div class="hl-comparison-card-rank">推荐 {_safe(rank)}</div>'
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
            f"我会优先考虑「{_display(recommended_name)}」"
            if recommended_name is not None
            else None,
            reason,
        )
        recommendation_markup = (
            '<div class="hl-comparison-recommendation">'
            "<span>结合这次需求</span>"
            f"<strong>{_safe(recommendation_text)}</strong></div>"
        )
    tradeoffs = _list_markup("选择时可以这样权衡", _attribute(result, "tradeoffs"))
    unknowns = _list_markup(
        "仍需确认",
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
            '<details class="hl-comparison-why"><summary>为什么这样比较？</summary>'
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
    count_label = {1: "一", 2: "两", 3: "三"}.get(len(items), str(len(items)))
    context = _attribute(result, "context_summary")
    context_markup = (
        f'<p class="hl-comparison-context">这次比较主要参考：{_safe(_display(context))}</p>'
        if context is not None
        else ""
    )
    markup = (
        '<section class="hl-comparison-shell" aria-labelledby="hl-comparison-title">'
        '<div class="hl-comparison-heading">'
        '<span class="hl-comparison-kicker">HAHA SHOPPING GUIDE</span>'
        f'<h2 id="hl-comparison-title">这{_safe(count_label)}件礼物怎么选？</h2>'
        f"{context_markup}</div>"
        f"{_desktop_markup(result, items)}"
        f"{_mobile_markup(result, items)}"
        f"{_summary_markup(result)}"
        "</section>"
    )
    st.markdown(markup, unsafe_allow_html=True)
