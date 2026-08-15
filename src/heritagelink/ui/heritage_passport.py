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
from heritagelink.i18n import Language, get_language, t
from heritagelink.ui.system import status_label

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


def _commercial_labels() -> dict[str, str]:
    return {
        "moq": t("passport.moq"),
        "lead_time_days": t("passport.lead_time"),
        "customization": t("passport.customization"),
        "logo_supported": t("passport.logo"),
        "packaging": t("passport.packaging"),
        "dimensions": t("passport.dimensions"),
        "materials": t("passport.materials"),
        "domestic_shipping": t("passport.domestic_shipping"),
        "international_shipping": t("passport.international_shipping"),
        "quantity_capacity": t("passport.capacity"),
    }


def _customization_labels() -> dict[str, str]:
    if get_language() == Language.EN_US:
        return {
            "logo": "Logo",
            "inscription": "Inscription",
            "pattern": "Pattern",
            "size": "Size",
            "packaging": "Packaging",
            "color": "Colour",
            "other": "Other",
        }
    return {
        "logo": "企业 Logo",
        "inscription": "题字",
        "pattern": "图案",
        "size": "尺寸",
        "packaging": "包装",
        "color": "色彩",
        "other": "其他定制",
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
    english_interface = get_language() == Language.EN_US
    primary_name = (
        passport.product_name_en
        if english_interface and passport.product_name_en
        else passport.product_name_zh
    )
    secondary_name = passport.product_name_zh if english_interface else passport.product_name_en
    english_name = (
        f'<p class="hl-passport-en">{escape(secondary_name)}</p>' if secondary_name else ""
    )
    publication = status_label(passport.publication_status)
    publication_markup = (
        f'<span class="hl-passport-status">{escape(publication)}</span>'
        if audience == "artisan" or passport.publication_status is PublicationStatus.RECOMMENDABLE
        else ""
    )
    st.markdown(
        '<section class="hl-passport-shell">'
        f'<div class="hl-passport-kicker">{escape(t("passport.kicker"))}</div>'
        f"<h3>{escape(primary_name)}</h3>"
        f"{english_name}{publication_markup}</section>",
        unsafe_allow_html=True,
    )


def _render_cultural_summary(passport: HeritagePassport, *, compact: bool) -> None:
    unknown = t("passport.unknown_neutral")
    symbolism = " · ".join(_visible_texts(passport.symbolism)) or unknown
    rows = [
        (t("passport.craft"), passport.craft_name or unknown),
        (t("passport.region"), passport.region or unknown),
        (t("passport.meaning"), symbolism),
    ]
    if not compact:
        background = (
            passport.cultural_background_en
            if get_language() == Language.EN_US
            else passport.cultural_background_zh
        )
        rows.append((t("passport.background"), background or unknown))
    _render_fact_grid(rows, css_class="hl-passport-cultural")


def _render_status_summary(
    passport: HeritagePassport,
    *,
    audience: PassportAudience,
) -> None:
    cultural = status_label(passport.cultural_verification_status)
    commercial = status_label(passport.commercial_verification_status)
    if audience == "buyer":
        cultural = _buyer_status(
            passport.cultural_verification_status,
            subject=t("passport.cultural_story"),
        )
        commercial = _buyer_status(
            passport.commercial_verification_status,
            subject=t("passport.commercial"),
        )
    _render_fact_grid(
        ((t("passport.cultural_status"), cultural), (t("passport.commercial_status"), commercial)),
        css_class="hl-passport-status-grid",
    )


def _render_commercial_facts(
    passport: HeritagePassport,
    *,
    audience: PassportAudience,
    compact: bool,
) -> None:
    facts = {fact.field_name: fact for fact in passport.commercial_facts}
    labels = _commercial_labels()
    rows: list[tuple[str, str, str | None]] = []
    price = _price_row(facts, audience=audience)
    if price is not None:
        rows.append(price)

    names = (
        ("logo_supported", "international_shipping", "customization") if compact else tuple(labels)
    )
    for name in names:
        fact = facts.get(name)
        if fact is None:
            rows.append((labels[name], t("passport.unknown_neutral"), None))
            continue
        value = _commercial_value(fact, audience=audience)
        source = _source_label(fact) if audience == "artisan" else None
        rows.append((labels[name], value, source))

    st.markdown(f"#### {t('passport.product_info')}")
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
        return (t("passport.price"), t("passport.unknown_neutral"), None)

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
        value = t("passport.unknown_neutral")
    source = _source_label(price_facts[0]) if audience == "artisan" and price_facts else None
    return (t("passport.price"), value, source)


def _commercial_value(fact: ProvenancedFact, *, audience: PassportAudience) -> str:
    if audience == "buyer" and not _confirmed(fact):
        return t("passport.unknown_neutral")
    if _unknown(fact.value):
        return t("passport.unknown_neutral")

    value = fact.value
    if fact.field_name in {
        "logo_supported",
        "domestic_shipping",
        "international_shipping",
    } and isinstance(value, bool):
        if _confirmed(fact):
            return t("passport.supported") if value else t("passport.not_supported")
        return t("common.needs_verification")
    if fact.field_name == "moq":
        return _number_with_unit(value, "items" if get_language() == Language.EN_US else "件")
    if fact.field_name == "lead_time_days":
        return _number_with_unit(value, "days" if get_language() == Language.EN_US else "天")
    if fact.field_name == "quantity_capacity":
        return _number_with_unit(value, "items" if get_language() == Language.EN_US else "件")
    if fact.field_name == "customization":
        values = _iter_values(value)
        labels = _customization_labels()
        visible = [labels.get(item.casefold(), item) for item in values]
        separator = ", " if get_language() == Language.EN_US else "、"
        return separator.join(visible) or t("passport.unknown_neutral")
    return _display_value(value)


def _render_sources(
    sources: tuple[SourceReference, ...],
    *,
    audience: PassportAudience,
    compact: bool,
) -> None:
    st.markdown(f"#### {t('passport.sources')}")
    if not sources:
        st.caption(t("passport.unknown_neutral"))
        return

    visible = sources[:2] if compact else sources
    rows: list[str] = []
    for source in visible:
        if audience == "buyer":
            source_status = (
                t("common.verified")
                if source.verification_status is VerificationStatus.CONFIRMED
                else t("passport.source_pending")
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

    st.markdown(f"#### {t('passport.bilingual_content')}")
    if audience == "artisan" and not confirmed:
        st.caption(t("passport.ai_draft_note"))
    chinese, english = st.tabs(
        (t("passport.chinese_description"), t("passport.english_description"))
    )
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
    value = reviewed_at.strftime("%Y-%m-%d %H:%M %Z") if reviewed_at else t("passport.not_reviewed")
    st.caption(f"{t('passport.last_reviewed')}: {value}")


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
        return f"{subject}: {t('common.verified')} ✓"
    if status is VerificationStatus.NOT_APPLICABLE:
        return "N/A"
    return f"{subject}: {t('common.needs_verification')}"


def _source_label(fact: ProvenancedFact) -> str:
    if fact.verification_status is VerificationStatus.UNKNOWN:
        return t("common.unknown")
    if fact.verification_status is VerificationStatus.NOT_APPLICABLE:
        return "N/A"
    return {
        FactSource.ARTISAN_PROVIDED: t("common.needs_verification"),
        FactSource.ARTISAN_CONFIRMED: t("passport.source_artisan"),
        FactSource.MERCHANT_CONFIRMED: t("passport.source_merchant"),
        FactSource.PUBLIC_SOURCE: t("passport.source_public"),
        FactSource.AI_INFERRED: t("passport.source_ai"),
        FactSource.UNKNOWN: t("common.unknown"),
    }[fact.source]


def _source_reference_label(source: SourceReference) -> str:
    if source.verification_status is VerificationStatus.CONFIRMED:
        if source.source is FactSource.ARTISAN_CONFIRMED:
            return t("passport.source_artisan")
        if source.source is FactSource.MERCHANT_CONFIRMED:
            return t("passport.source_merchant")
        return t("passport.source_public")
    if source.source is FactSource.AI_INFERRED:
        return t("passport.source_ai")
    return t("passport.source_pending")


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
        return t("passport.supported") if value else t("passport.not_supported")
    values = _iter_values(value)
    separator = ", " if get_language() == Language.EN_US else "、"
    return separator.join(values) if values else t("passport.unknown_neutral")


def _number_with_unit(value: object, unit: str) -> str:
    if isinstance(value, bool):
        return t("passport.unknown_neutral")
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
