"""Customer-safe presentation for the shared Heritage Passport model."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from html import escape
from typing import Literal

import streamlit as st

from heritagelink.heritage_passport_models import (
    BilingualProductDraft,
    FactSource,
    HeritagePassport,
    ProvenancedFact,
    PublicationStatus,
    SourceReference,
    VerificationStatus,
)

PassportAudience = Literal["artisan", "buyer"]

_UNKNOWN_TEXT = frozenset(
    {
        "",
        "unknown",
        "待确认",
        "待补充",
        "暂不确定",
        "暂无信息",
        "不清楚",
        "不知道",
        "none",
        "null",
    }
)

_COMMERCIAL_LABELS = {
    "moq": "最低起订量",
    "lead_time_days": "预计制作周期",
    "customization": "定制能力",
    "logo_supported": "企业 Logo 定制",
    "packaging": "包装",
    "dimensions": "尺寸",
    "materials": "材料",
    "domestic_shipping": "境内运输",
    "international_shipping": "国际运输",
    "quantity_capacity": "可承接数量",
}

_CUSTOMIZATION_LABELS = {
    "logo": "企业 Logo",
    "inscription": "题字",
    "pattern": "图案",
    "size": "尺寸",
    "packaging": "包装",
    "color": "色彩",
    "other": "其他定制",
}

_STATUS_LABELS = {
    VerificationStatus.CONFIRMED: "已确认",
    VerificationStatus.PENDING_REVIEW: "待确认",
    VerificationStatus.UNKNOWN: "需进一步确认",
    VerificationStatus.NOT_APPLICABLE: "不适用",
}

_PUBLICATION_LABELS = {
    PublicationStatus.DRAFT: "资料整理中",
    PublicationStatus.PENDING_REVIEW: "已提交审核",
    PublicationStatus.REFERENCE_ONLY: "文化资料展示",
    PublicationStatus.RECOMMENDABLE: "可参与正式推荐",
    PublicationStatus.ARCHIVED: "已停止展示",
}

_SOURCE_LABELS = {
    FactSource.ARTISAN_PROVIDED: "您提供 · 待确认",
    FactSource.ARTISAN_CONFIRMED: "您已确认",
    FactSource.MERCHANT_CONFIRMED: "商家已确认",
    FactSource.PUBLIC_SOURCE: "公开资料",
    FactSource.AI_INFERRED: "AI 整理 · 请确认",
    FactSource.UNKNOWN: "尚未提供",
}


def render_heritage_passport(
    passport: HeritagePassport,
    *,
    audience: PassportAudience = "artisan",
    compact: bool = False,
) -> None:
    """Render a passport without exposing internal status or provenance tokens.

    Buyer presentation fails closed: pending commercial values are replaced by
    ``需进一步确认``.  The artisan presentation may show entered values while
    translating provenance into plain-language review labels.
    """
    if audience not in {"artisan", "buyer"}:
        raise ValueError("audience 必须是 artisan 或 buyer")

    _render_header(passport, audience=audience)
    _render_cultural_summary(passport, compact=compact)
    _render_status_summary(passport, audience=audience)
    _render_commercial_facts(passport, audience=audience, compact=compact)
    _render_sources(passport.cultural_sources, audience=audience, compact=compact)
    if not compact:
        _render_bilingual_content(passport.bilingual_content, audience=audience)
        _render_review_time(passport.reviewed_at)


def _render_header(passport: HeritagePassport, *, audience: PassportAudience) -> None:
    english_name = (
        f'<p class="hl-passport-en">{escape(passport.product_name_en)}</p>'
        if passport.product_name_en
        else ""
    )
    publication = _PUBLICATION_LABELS[passport.publication_status]
    publication_markup = (
        f'<span class="hl-passport-status">{escape(publication)}</span>'
        if audience == "artisan" or passport.publication_status is PublicationStatus.RECOMMENDABLE
        else ""
    )
    st.markdown(
        '<section class="hl-passport-shell">'
        '<div class="hl-passport-kicker">HERITAGE PASSPORT · 非遗文化护照</div>'
        f"<h3>{escape(passport.product_name_zh)}</h3>"
        f"{english_name}{publication_markup}</section>",
        unsafe_allow_html=True,
    )


def _render_cultural_summary(passport: HeritagePassport, *, compact: bool) -> None:
    symbolism = " · ".join(_visible_texts(passport.symbolism)) or "需进一步确认"
    rows = [
        ("工艺", passport.craft_name or "需进一步确认"),
        ("地域", passport.region or "需进一步确认"),
        ("文化寓意", symbolism),
    ]
    if not compact:
        rows.append(("工艺背景", passport.cultural_background_zh or "需进一步确认"))
    _render_fact_grid(rows, css_class="hl-passport-cultural")


def _render_status_summary(
    passport: HeritagePassport,
    *,
    audience: PassportAudience,
) -> None:
    cultural = _STATUS_LABELS[passport.cultural_verification_status]
    commercial = _STATUS_LABELS[passport.commercial_verification_status]
    if audience == "buyer":
        cultural = _buyer_status(passport.cultural_verification_status, subject="文化资料")
        commercial = _buyer_status(passport.commercial_verification_status, subject="商品信息")
    _render_fact_grid(
        (("文化资料状态", cultural), ("商品事实状态", commercial)),
        css_class="hl-passport-status-grid",
    )


def _render_commercial_facts(
    passport: HeritagePassport,
    *,
    audience: PassportAudience,
    compact: bool,
) -> None:
    facts = {fact.field_name: fact for fact in passport.commercial_facts}
    rows: list[tuple[str, str, str | None]] = []
    price = _price_row(facts, audience=audience)
    if price is not None:
        rows.append(price)

    names = (
        ("logo_supported", "international_shipping", "customization")
        if compact
        else tuple(_COMMERCIAL_LABELS)
    )
    for name in names:
        fact = facts.get(name)
        if fact is None:
            rows.append((_COMMERCIAL_LABELS[name], "需进一步确认", None))
            continue
        value = _commercial_value(fact, audience=audience)
        source = _source_label(fact) if audience == "artisan" else None
        rows.append((_COMMERCIAL_LABELS[name], value, source))

    st.markdown("#### 商品信息")
    _render_commercial_grid(rows)


def _price_row(
    facts: dict[str, ProvenancedFact],
    *,
    audience: PassportAudience,
) -> tuple[str, str, str | None] | None:
    minimum = facts.get("price_min_fen")
    maximum = facts.get("price_max_fen")
    currency = facts.get("currency")
    if minimum is None and maximum is None:
        return None

    price_facts = tuple(fact for fact in (minimum, maximum) if fact is not None)
    confirmed = bool(price_facts) and all(_confirmed(fact) for fact in price_facts)
    if audience == "buyer" and not confirmed:
        return ("价格", "需进一步确认", None)

    minimum_value = _fen(minimum.value) if minimum and not _unknown(minimum.value) else None
    maximum_value = _fen(maximum.value) if maximum and not _unknown(maximum.value) else None
    symbol = _currency_symbol(currency.value if currency else None)
    if minimum_value is not None and maximum_value is not None:
        value = f"{symbol}{minimum_value:,.0f}–{symbol}{maximum_value:,.0f}"
    elif minimum_value is not None:
        value = f"{symbol}{minimum_value:,.0f} 起"
    elif maximum_value is not None:
        value = f"{symbol}{maximum_value:,.0f} 以内"
    else:
        value = "需进一步确认"
    source = _source_label(price_facts[0]) if audience == "artisan" and price_facts else None
    return ("价格", value, source)


def _commercial_value(fact: ProvenancedFact, *, audience: PassportAudience) -> str:
    if audience == "buyer" and not _confirmed(fact):
        return "需进一步确认"
    if _unknown(fact.value):
        return "需进一步确认"

    value = fact.value
    if fact.field_name in {
        "logo_supported",
        "domestic_shipping",
        "international_shipping",
    } and isinstance(value, bool):
        if _confirmed(fact):
            return "已确认支持" if value else "已确认不支持"
        return "支持 · 待确认" if value else "不支持 · 待确认"
    if fact.field_name == "moq":
        return _number_with_unit(value, "件")
    if fact.field_name == "lead_time_days":
        return _number_with_unit(value, "天")
    if fact.field_name == "quantity_capacity":
        return _number_with_unit(value, "件")
    if fact.field_name == "customization":
        values = _iter_values(value)
        visible = [_CUSTOMIZATION_LABELS.get(item.casefold(), item) for item in values]
        return "、".join(visible) or "需进一步确认"
    return _display_value(value)


def _render_sources(
    sources: tuple[SourceReference, ...],
    *,
    audience: PassportAudience,
    compact: bool,
) -> None:
    st.markdown("#### 文化来源")
    if not sources:
        st.caption("文化来源需进一步确认")
        return

    visible = sources[:2] if compact else sources
    rows: list[str] = []
    for source in visible:
        if audience == "buyer":
            source_status = (
                "已有来源"
                if source.verification_status is VerificationStatus.CONFIRMED
                else "来源待核实"
            )
        else:
            source_status = _source_reference_label(source)
        rows.append(
            '<li><a href="'
            f'{escape(source.url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f"{escape(source.label)}</a>"
            f"<span>{escape(source_status)}</span></li>"
        )
    st.markdown(
        f'<ul class="hl-source-list">{"".join(rows)}</ul>',
        unsafe_allow_html=True,
    )


def _render_bilingual_content(
    content: BilingualProductDraft | None,
    *,
    audience: PassportAudience,
) -> None:
    if content is None:
        return
    confirmed = content.verification_status is VerificationStatus.CONFIRMED
    if audience == "buyer" and not confirmed:
        return

    st.markdown("#### 中英文作品介绍")
    if audience == "artisan" and not confirmed:
        st.caption("AI 协助整理 · 请确认；以下内容尚未进入正式推荐资料。")
    chinese, english = st.tabs(("中文介绍", "English Description"))
    with chinese:
        for value in (
            content.overview_zh,
            content.craft_background_zh,
            content.cultural_meaning_zh,
            content.gifting_contexts_zh,
            content.customization_zh,
        ):
            st.write(value)
    with english:
        for value in (
            content.overview_en,
            content.craft_background_en,
            content.cultural_meaning_en,
            content.gifting_contexts_en,
            content.customization_en,
        ):
            st.write(value)


def _render_review_time(reviewed_at: datetime | None) -> None:
    value = reviewed_at.strftime("%Y年%m月%d日 %H:%M %Z") if reviewed_at else "尚未完成审核"
    st.caption(f"最后确认时间：{value}")


def _render_fact_grid(rows: Iterable[tuple[str, str]], *, css_class: str) -> None:
    cards = "".join(
        '<div class="hl-passport-fact">'
        f"<span>{escape(label)}</span><strong>{escape(_safe_text(value))}</strong>"
        "</div>"
        for label, value in rows
    )
    st.markdown(
        f'<div class="hl-passport-grid {escape(css_class, quote=True)}">{cards}</div>',
        unsafe_allow_html=True,
    )


def _render_commercial_grid(rows: Iterable[tuple[str, str, str | None]]) -> None:
    cards: list[str] = []
    for label, value, source in rows:
        source_markup = f'<small class="hl-fact-source">{escape(source)}</small>' if source else ""
        cards.append(
            '<div class="hl-passport-fact">'
            f"<span>{escape(label)}</span><strong>{escape(_safe_text(value))}</strong>"
            f"{source_markup}</div>"
        )
    st.markdown(
        f'<div class="hl-passport-grid hl-passport-commercial">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _buyer_status(status: VerificationStatus, *, subject: str) -> str:
    if status is VerificationStatus.CONFIRMED:
        return f"{subject}已确认 ✓"
    if status is VerificationStatus.NOT_APPLICABLE:
        return "不适用"
    return f"{subject}需进一步确认"


def _source_label(fact: ProvenancedFact) -> str:
    if fact.verification_status is VerificationStatus.UNKNOWN:
        return "尚未提供"
    if fact.verification_status is VerificationStatus.NOT_APPLICABLE:
        return "不适用"
    return _SOURCE_LABELS[fact.source]


def _source_reference_label(source: SourceReference) -> str:
    if source.verification_status is VerificationStatus.CONFIRMED:
        if source.source is FactSource.ARTISAN_CONFIRMED:
            return "您已确认"
        if source.source is FactSource.MERCHANT_CONFIRMED:
            return "商家已确认"
        return "已有公开来源"
    if source.source is FactSource.AI_INFERRED:
        return "AI 整理 · 请确认"
    return "来源待核实"


def _confirmed(fact: ProvenancedFact) -> bool:
    return fact.verification_status is VerificationStatus.CONFIRMED


def _unknown(value: object) -> bool:
    if value is None or value == () or value == []:
        return True
    return isinstance(value, str) and value.strip().casefold() in _UNKNOWN_TEXT


def _visible_texts(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(_safe_text(value) for value in values if not _unknown(value))


def _iter_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray, dict)):
        return tuple(_safe_text(item) for item in value if not _unknown(item))
    return () if _unknown(value) else (_safe_text(value),)


def _display_value(value: object) -> str:
    if isinstance(value, bool):
        return "支持" if value else "不支持"
    values = _iter_values(value)
    return "、".join(values) if values else "需进一步确认"


def _number_with_unit(value: object, unit: str) -> str:
    if isinstance(value, bool):
        return "需进一步确认"
    if isinstance(value, (int, float)):
        return f"{value:g} {unit}"
    text = _safe_text(value)
    return text if unit in text else f"{text} {unit}"


def _fen(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) / 100
    try:
        return float(str(value)) / 100
    except (TypeError, ValueError):
        return None


def _currency_symbol(value: object) -> str:
    normalized = _safe_text(value).upper() if not _unknown(value) else "CNY"
    return {"CNY": "¥", "RMB": "¥", "USD": "$", "EUR": "€", "GBP": "£"}.get(
        normalized,
        "",
    )


def _safe_text(value: object) -> str:
    return str(value).strip()


__all__ = ["PassportAudience", "render_heritage_passport"]
