"""Adapt canonical catalogue products to the shared Heritage Passport contract.

The adapter is deliberately conservative.  Existing catalogue prices and service
capabilities are MVP assumptions, so their values may be shown for review but are
never promoted to confirmed facts unless both merchant and commercial source
statuses explicitly say that they have been verified.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from heritagelink.catalog_eligibility import is_recommendation_eligible
from heritagelink.heritage_passport_models import (
    BilingualProductDraft,
    FactGroup,
    FactSource,
    HeritagePassport,
    ProvenancedFact,
    PublicationStatus,
    SourceReference,
    VerificationStatus,
)
from heritagelink.models import DataBundle, Product

__all__ = ["build_catalog_passports", "build_product_passport"]


_CONFIRMED_MERCHANT_STATUSES = frozenset({"confirmed", "merchant_confirmed", "verified"})
_CONFIRMED_COMMERCIAL_STATUSES = frozenset(
    {"approved", "confirmed", "merchant_confirmed", "verified", "verified_commercial_fact"}
)


def build_product_passport(product: Product, bundle: DataBundle) -> HeritagePassport:
    """Build a provenance-safe passport for one canonical catalogue product.

    A ``recommendation_demo`` product is recommendable only when it also passes
    the central catalogue eligibility gate.  A ``catalog_reference`` record is
    always reference-only, even if a malformed fixture marks it active.
    """
    heritage = _heritage_row(bundle, product.heritage_id)
    zh_row = _content_row(bundle, product.product_id, "zh-CN")
    en_row = _content_row(bundle, product.product_id, "en")
    content_confirmed = _content_confirmed(zh_row, en_row)
    commercial_confirmed = _commercial_confirmed(product)

    return HeritagePassport(
        passport_id=f"passport_{product.product_id}",
        product_id=product.product_id,
        artisan_or_merchant_name=_optional_text(product.merchant_name_zh),
        product_name_zh=product.product_name_zh,
        product_name_en=_optional_text(product.product_name_en),
        craft_name=_craft_name(heritage, product),
        region=_region(heritage, product),
        cultural_background_zh=_row_text(zh_row, "cultural_story"),
        cultural_background_en=_row_text(en_row, "cultural_story"),
        symbolism=_symbolism(zh_row, en_row, product),
        cultural_sources=_cultural_sources(product),
        commercial_facts=_commercial_facts(product, confirmed=commercial_confirmed),
        cultural_verification_status=_cultural_status(
            product,
            content_confirmed=content_confirmed,
        ),
        commercial_verification_status=(
            VerificationStatus.CONFIRMED
            if commercial_confirmed
            else VerificationStatus.PENDING_REVIEW
        ),
        publication_status=_publication_status(product),
        reviewed_at=_reviewed_at(zh_row, en_row) if content_confirmed else None,
        bilingual_content=_bilingual_content(
            product,
            zh_row,
            en_row,
            content_confirmed=content_confirmed,
        ),
    )


def build_catalog_passports(
    products: Iterable[Product],
    bundle: DataBundle,
) -> dict[str, HeritagePassport]:
    """Build passports keyed by product ID while rejecting duplicate IDs."""
    passports: dict[str, HeritagePassport] = {}
    for product in products:
        if product.product_id in passports:
            raise ValueError(f"duplicate product_id: {product.product_id}")
        passports[product.product_id] = build_product_passport(product, bundle)
    return passports


def _publication_status(product: Product) -> PublicationStatus:
    if is_recommendation_eligible(product):
        return PublicationStatus.RECOMMENDABLE
    if product.catalog_role == "catalog_reference":
        return PublicationStatus.REFERENCE_ONLY
    if product.status == "inactive":
        return PublicationStatus.ARCHIVED
    return PublicationStatus.DRAFT


def _commercial_confirmed(product: Product) -> bool:
    """Fail closed; in particular, ``demo_assumption`` is never confirmation."""
    return (
        product.merchant_fact_status in _CONFIRMED_MERCHANT_STATUSES
        and product.commercial_data_status in _CONFIRMED_COMMERCIAL_STATUSES
    )


def _commercial_facts(
    product: Product,
    *,
    confirmed: bool,
) -> tuple[ProvenancedFact, ...]:
    source = FactSource.MERCHANT_CONFIRMED if confirmed else FactSource.UNKNOWN
    status = VerificationStatus.CONFIRMED if confirmed else VerificationStatus.PENDING_REVIEW
    note = (
        "商家已确认的商业资料"
        if confirmed
        else (
            "MVP 展示值，待商家确认；"
            f"merchant_fact_status={product.merchant_fact_status}, "
            f"commercial_data_status={product.commercial_data_status}"
        )
    )

    # A missing/unverified boolean remains None.  It must not be projected as a
    # negative capability simply because the canonical Product model uses bool.
    international_shipping: bool | None = (
        product.supports_international_shipping if confirmed else None
    )
    logo_supported: bool | None = "logo" in product.customization_options if confirmed else None
    values: tuple[tuple[str, Any, str | None], ...] = (
        ("price_min_fen", product.price_min_fen, None),
        ("price_max_fen", product.price_max_fen, None),
        ("currency", "CNY", None),
        ("moq", product.min_order_qty, None),
        ("lead_time_days", product.lead_time_days, None),
        ("customization", tuple(sorted(product.customization_options)), None),
        ("logo_supported", logo_supported, None),
        ("packaging", None, None),
        ("dimensions", _optional_text(product.dimensions_text), None),
        ("materials", _optional_text(product.material_text), None),
        ("domestic_shipping", None, None),
        ("international_shipping", international_shipping, product.shipping_note),
        ("quantity_capacity", None, None),
    )
    return tuple(
        ProvenancedFact(
            field_name=field_name,
            value=value,
            group=FactGroup.COMMERCIAL,
            source=source,
            verification_status=(
                VerificationStatus.UNKNOWN if value is None and not confirmed else status
            ),
            source_note=_join_notes(note, field_note),
        )
        for field_name, value, field_note in values
    )


def _cultural_status(
    product: Product,
    *,
    content_confirmed: bool,
) -> VerificationStatus:
    public_fact_verified = (
        product.cultural_data_status == "verified_public_cultural_fact"
        and _is_https(product.source_culture_url)
    )
    if public_fact_verified and content_confirmed:
        return VerificationStatus.CONFIRMED
    if public_fact_verified or product.content_review_statuses:
        return VerificationStatus.PENDING_REVIEW
    return VerificationStatus.UNKNOWN


def _bilingual_content(
    product: Product,
    zh_row: pd.Series | None,
    en_row: pd.Series | None,
    *,
    content_confirmed: bool,
) -> BilingualProductDraft:
    return BilingualProductDraft(
        overview_zh=product.product_name_zh,
        overview_en=product.product_name_en,
        craft_background_zh=_row_text(zh_row, "craft_summary") or "待审核补充",
        craft_background_en=_row_text(en_row, "craft_summary") or "Pending editorial review",
        cultural_meaning_zh=_row_text(zh_row, "meaning_summary") or "待审核补充",
        cultural_meaning_en=_row_text(en_row, "meaning_summary") or "Pending editorial review",
        gifting_contexts_zh="、".join(sorted(product.occasion_tags)) or "待确认",
        gifting_contexts_en=", ".join(sorted(product.occasion_tags)) or "Pending confirmation",
        customization_zh="待商家确认",
        customization_en="Pending merchant confirmation",
        source=FactSource.PUBLIC_SOURCE,
        verification_status=(
            VerificationStatus.CONFIRMED if content_confirmed else VerificationStatus.PENDING_REVIEW
        ),
    )


def _heritage_row(bundle: DataBundle, heritage_id: str) -> pd.Series | None:
    rows = bundle.heritage_items[bundle.heritage_items["heritage_id"] == heritage_id]
    return None if rows.empty else rows.iloc[0]


def _content_row(bundle: DataBundle, product_id: str, locale: str) -> pd.Series | None:
    rows = bundle.product_texts[
        (bundle.product_texts["product_id"] == product_id)
        & (bundle.product_texts["locale"] == locale)
    ]
    return None if rows.empty else rows.iloc[0]


def _content_confirmed(zh_row: pd.Series | None, en_row: pd.Series | None) -> bool:
    return all(
        row is not None
        and _row_text(row, "review_status") == "approved"
        and bool(_row_text(row, "reviewed_at"))
        for row in (zh_row, en_row)
    )


def _reviewed_at(zh_row: pd.Series | None, en_row: pd.Series | None) -> datetime | None:
    values = [
        parsed
        for row in (zh_row, en_row)
        if (parsed := _parse_datetime(_row_text(row, "reviewed_at"))) is not None
    ]
    return max(values, default=None)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = pd.Timestamp(value).to_pydatetime()
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _craft_name(heritage: pd.Series | None, product: Product) -> str:
    return (
        _row_text(heritage, "heritage_name_zh")
        or _optional_text(product.category_code)
        or "待补充工艺"
    )


def _region(heritage: pd.Series | None, product: Product) -> str | None:
    return _row_text(heritage, "region") or _optional_text(product.region_code)


def _symbolism(
    zh_row: pd.Series | None,
    en_row: pd.Series | None,
    product: Product,
) -> tuple[str, ...]:
    zh_meaning = _row_text(zh_row, "meaning_summary")
    if zh_meaning:
        return (zh_meaning,)
    en_meaning = _row_text(en_row, "meaning_summary")
    if en_meaning:
        return (en_meaning,)
    return tuple(sorted(product.meaning_tags))


def _cultural_sources(product: Product) -> tuple[SourceReference, ...]:
    candidates = (
        ("文化资料来源", product.source_culture_url),
        ("馆藏参考来源", product.reference_source_url),
    )
    sources: list[SourceReference] = []
    seen: set[str] = set()
    source_status = (
        VerificationStatus.CONFIRMED
        if product.source_status == "source_verified"
        else VerificationStatus.PENDING_REVIEW
    )
    for label, url in candidates:
        normalized = url.strip()
        if normalized in seen or not _is_https(normalized):
            continue
        seen.add(normalized)
        sources.append(
            SourceReference(
                label=label,
                url=normalized,
                verification_status=source_status,
            )
        )
    return tuple(sources)


def _is_https(value: str) -> bool:
    return value.strip().lower().startswith("https://")


def _row_text(row: pd.Series | None, field_name: str) -> str | None:
    if row is None or field_name not in row.index:
        return None
    return _optional_text(row[field_name])


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _join_notes(primary: str, secondary: str | None) -> str:
    if not secondary or not secondary.strip():
        return primary
    return f"{primary}；{secondary.strip()}"
