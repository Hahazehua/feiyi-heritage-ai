"""Build the evidence-limited product context used by Growth Studio agents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import (
    ArtisanProductDraft,
    FactSource,
    HeritagePassport,
    ProvenancedFact,
    VerificationStatus,
)
from heritagelink.models import Product

_EXPECTED_GROWTH_FIELDS = (
    "artisan_or_merchant_name",
    "region",
    "materials",
    "dimensions",
    "price_min_fen",
    "price_max_fen",
    "currency",
    "moq",
    "lead_time_days",
    "customization",
    "logo_supported",
    "packaging",
    "international_shipping",
    "quantity_capacity",
    "cultural_background",
    "symbolism",
)


def build_catalog_growth_context(
    product: Product,
    passport: HeritagePassport,
) -> GrowthProductContext:
    """Adapt one canonical product without upgrading demo commercial assumptions."""
    verified: list[GroundedFact] = [
        _verified_fact("product_name", product.product_name_zh, "canonical product identity"),
        _verified_fact("product_name_en", product.product_name_en, "canonical product identity"),
        _verified_fact("craft_name", passport.craft_name, "structured craft classification"),
        _verified_fact("category_code", product.category_code, "validated catalogue field"),
        _verified_fact(
            "recipient_tags", tuple(sorted(product.recipient_tags)), "deterministic catalogue tags"
        ),
        _verified_fact(
            "occasion_tags", tuple(sorted(product.occasion_tags)), "deterministic catalogue tags"
        ),
        _verified_fact(
            "style_tags", tuple(sorted(product.style_tags)), "deterministic catalogue tags"
        ),
        _verified_fact(
            "meaning_tags", tuple(sorted(product.meaning_tags)), "deterministic catalogue tags"
        ),
    ]
    unverified: list[GroundedFact] = []
    unknown: set[str] = set()

    if passport.region:
        target = (
            verified
            if passport.cultural_verification_status is VerificationStatus.CONFIRMED
            else unverified
        )
        target.append(
            _fact(
                "region",
                passport.region,
                verified=target is verified,
                source=FactSource.PUBLIC_SOURCE,
                note="Heritage Passport region field",
            )
        )
    else:
        unknown.add("region")

    if passport.artisan_or_merchant_name:
        merchant_verified = product.merchant_fact_status in {
            "confirmed",
            "merchant_confirmed",
            "verified",
        }
        target = verified if merchant_verified else unverified
        target.append(
            _fact(
                "artisan_or_merchant_name",
                passport.artisan_or_merchant_name,
                verified=merchant_verified,
                source=(FactSource.MERCHANT_CONFIRMED if merchant_verified else FactSource.UNKNOWN),
                note="Canonical merchant field",
            )
        )
    else:
        unknown.add("artisan_or_merchant_name")

    if (
        passport.bilingual_content is not None
        and passport.bilingual_content.verification_status is VerificationStatus.CONFIRMED
    ):
        verified.extend(
            (
                _verified_fact(
                    "cultural_background",
                    passport.bilingual_content.craft_background_en,
                    "reviewed Heritage Passport content",
                ),
                _verified_fact(
                    "cultural_meaning",
                    passport.bilingual_content.cultural_meaning_en,
                    "reviewed Heritage Passport content",
                ),
            )
        )
    elif passport.bilingual_content is not None:
        unverified.extend(
            (
                _unverified_fact(
                    "cultural_background",
                    passport.bilingual_content.craft_background_en,
                    "draft Heritage Passport content",
                ),
                _unverified_fact(
                    "cultural_meaning",
                    passport.bilingual_content.cultural_meaning_en,
                    "draft Heritage Passport content",
                ),
            )
        )
    else:
        unknown.update(("cultural_background", "cultural_meaning"))

    for fact in passport.commercial_facts:
        converted = _from_provenanced_fact(fact)
        if converted.evidence_status is EvidenceStatus.VERIFIED:
            verified.append(converted)
        elif converted.evidence_status is EvidenceStatus.UNVERIFIED:
            unverified.append(converted)
        else:
            unknown.add(fact.field_name)

    sources = tuple(
        source.url
        for source in passport.cultural_sources
        if source.verification_status is VerificationStatus.CONFIRMED
    )
    known = {fact.field_name for fact in (*verified, *unverified)}
    unknown.update(field for field in _EXPECTED_GROWTH_FIELDS if field not in known)
    return GrowthProductContext(
        artisan_id=product.merchant_id,
        product_id=product.product_id,
        product_name=product.product_name_zh,
        product_name_en=product.product_name_en or None,
        craft_name=passport.craft_name,
        publication_status=passport.publication_status,
        verified_facts=tuple(_deduplicate(verified)),
        unverified_facts=tuple(_deduplicate(unverified)),
        unknown_fields=tuple(sorted(unknown - known)),
        cultural_source_urls=sources,
        context_label="canonical catalogue + Heritage Passport",
    )


def build_draft_growth_context(draft: ArtisanProductDraft) -> GrowthProductContext:
    """Use confirmed draft facts while keeping pending values internal and labelled."""
    facts = draft.facts_by_name
    product_name = _text_value(facts.get("product_name_zh")) or "Unconfirmed artisan product"
    product_name_en = _text_value(facts.get("product_name_en"))
    craft_name = _text_value(facts.get("craft_name")) or "Unconfirmed craft"
    verified: list[GroundedFact] = []
    unverified: list[GroundedFact] = []
    unknown: set[str] = set()
    for fact in draft.facts:
        converted = _from_provenanced_fact(fact)
        if converted.evidence_status is EvidenceStatus.VERIFIED:
            verified.append(converted)
        elif converted.evidence_status is EvidenceStatus.UNVERIFIED:
            unverified.append(converted)
        else:
            unknown.add(fact.field_name)
    known = {fact.field_name for fact in (*verified, *unverified)}
    unknown.update(field for field in _EXPECTED_GROWTH_FIELDS if field not in known)
    source_urls = tuple(
        str(fact.value)
        for fact in draft.facts
        if fact.field_name.endswith("_source_url")
        and fact.verification_status is VerificationStatus.CONFIRMED
        and isinstance(fact.value, str)
        and fact.value.startswith("https://")
    )
    return GrowthProductContext(
        artisan_id=draft.session_id,
        product_id=f"pending_{draft.draft_id.removeprefix('draft_')}",
        product_name=product_name,
        product_name_en=product_name_en,
        craft_name=craft_name,
        publication_status=draft.publication_status,
        verified_facts=tuple(_deduplicate(verified)),
        unverified_facts=tuple(_deduplicate(unverified)),
        unknown_fields=tuple(sorted(unknown - known)),
        cultural_source_urls=source_urls,
        context_label="Artisan Studio draft; internal campaign use only",
    )


def public_claim_value(context: GrowthProductContext, field_name: str) -> Any | None:
    """Return a value only when its evidence is confirmed for public-facing copy."""
    fact = context.verified_by_name.get(field_name)
    return fact.value if fact is not None else None


def _from_provenanced_fact(fact: ProvenancedFact) -> GroundedFact:
    if fact.value is None:
        return GroundedFact(
            fact.field_name,
            None,
            EvidenceStatus.UNKNOWN,
            fact.source,
            VerificationStatus.UNKNOWN,
            fact.source_note,
        )
    verified = fact.verification_status is VerificationStatus.CONFIRMED
    return _fact(
        fact.field_name,
        fact.value,
        verified=verified,
        source=fact.source,
        note=fact.source_note,
        source_url=(
            str(fact.value)
            if fact.field_name.endswith("_source_url")
            and isinstance(fact.value, str)
            and fact.value.startswith("https://")
            else None
        ),
    )


def _fact(
    field_name: str,
    value: Any,
    *,
    verified: bool,
    source: FactSource,
    note: str | None,
    source_url: str | None = None,
) -> GroundedFact:
    return GroundedFact(
        field_name=field_name,
        value=value,
        evidence_status=(EvidenceStatus.VERIFIED if verified else EvidenceStatus.UNVERIFIED),
        source=source,
        verification_status=(
            VerificationStatus.CONFIRMED if verified else VerificationStatus.PENDING_REVIEW
        ),
        source_note=note,
        source_url=source_url,
    )


def _verified_fact(field_name: str, value: Any, note: str) -> GroundedFact:
    return _fact(
        field_name,
        value,
        verified=True,
        source=FactSource.PUBLIC_SOURCE,
        note=note,
    )


def _unverified_fact(field_name: str, value: Any, note: str) -> GroundedFact:
    return _fact(
        field_name,
        value,
        verified=False,
        source=FactSource.UNKNOWN,
        note=note,
    )


def _deduplicate(facts: Iterable[GroundedFact]) -> list[GroundedFact]:
    output: dict[str, GroundedFact] = {}
    for fact in facts:
        output[fact.field_name] = fact
    return list(output.values())


def _text_value(fact: ProvenancedFact | None) -> str | None:
    if fact is None or fact.value is None:
        return None
    value = str(fact.value).strip()
    return value or None


__all__ = [
    "build_catalog_growth_context",
    "build_draft_growth_context",
    "public_claim_value",
]
