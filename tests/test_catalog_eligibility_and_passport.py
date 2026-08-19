from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from heritagelink.artisan_studio import build_passport, create_draft
from heritagelink.catalog_eligibility import eligible_products, is_recommendation_eligible
from heritagelink.data_loader import build_products, load_data
from heritagelink.heritage_passport import build_catalog_passports, build_product_passport
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.inference_policy import build_recommendation_context
from heritagelink.request_parser import demo_parse_request
from heritagelink.skills import recommendation_skill

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "demo"


@pytest.fixture(scope="module")
def catalog_data():  # type: ignore[no-untyped-def]
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


def _broad_context():  # type: ignore[no-untyped-def]
    return build_recommendation_context(
        demo_parse_request("送给合作伙伴的周年礼物，数量1件，每件预算10000元。")
    )


def test_catalog_keeps_exactly_twentyone_formal_and_thirty_reference_products(
    catalog_data,
) -> None:  # type: ignore[no-untyped-def]
    _, products = catalog_data
    formal = tuple(product for product in products if is_recommendation_eligible(product))
    references = tuple(
        product for product in products if product.catalog_role == "catalog_reference"
    )

    assert len(products) == 51
    assert len(formal) == 21
    assert len(references) == 30
    assert len({product.product_id for product in formal}) == 21
    assert len({product.product_id for product in references}) == 30
    assert {product.product_id for product in formal}.isdisjoint(
        product.product_id for product in references
    )
    assert all(product.publication_status is PublicationStatus.RECOMMENDABLE for product in formal)
    assert all(
        product.publication_status is PublicationStatus.REFERENCE_ONLY for product in references
    )
    assert eligible_products(products) == formal


@pytest.mark.parametrize(
    "publication_status",
    (
        PublicationStatus.DRAFT,
        PublicationStatus.PENDING_REVIEW,
        PublicationStatus.REFERENCE_ONLY,
        PublicationStatus.ARCHIVED,
    ),
)
def test_nonrecommendable_publication_status_fails_closed_before_skill3(
    catalog_data,
    publication_status: PublicationStatus,
) -> None:  # type: ignore[no-untyped-def]
    _, products = catalog_data
    canonical = next(product for product in products if is_recommendation_eligible(product))
    candidate = replace(canonical, publication_status=publication_status)

    result = recommendation_skill.execute((candidate,), _broad_context())

    assert not is_recommendation_eligible(candidate)
    assert result.response.recommendations == ()


def test_forged_active_reference_still_fails_closed_through_skill3(catalog_data) -> None:  # type: ignore[no-untyped-def]
    _, products = catalog_data
    reference = next(product for product in products if product.catalog_role == "catalog_reference")
    forged = replace(
        reference,
        status="active",
        merchant_status="active",
        heritage_status="active",
        publication_status=PublicationStatus.RECOMMENDABLE,
    )

    result = recommendation_skill.execute((forged,), _broad_context())

    assert not is_recommendation_eligible(forged)
    assert eligible_products((forged,)) == ()
    assert result.response.recommendations == ()


def test_existing_formal_product_passport_keeps_commercial_data_pending(
    catalog_data,
) -> None:  # type: ignore[no-untyped-def]
    bundle, products = catalog_data
    product = next(item for item in products if is_recommendation_eligible(item))

    passport = build_product_passport(product, bundle)
    commercial = {fact.field_name: fact for fact in passport.commercial_facts}

    assert passport.publication_status is PublicationStatus.RECOMMENDABLE
    assert passport.commercial_verification_status is VerificationStatus.PENDING_REVIEW
    assert passport.cultural_verification_status is VerificationStatus.PENDING_REVIEW
    assert passport.bilingual_content is not None
    assert passport.bilingual_content.verification_status is VerificationStatus.PENDING_REVIEW
    for field_name in ("price_min_fen", "price_max_fen", "moq", "lead_time_days"):
        fact = commercial[field_name]
        assert fact.source is FactSource.UNKNOWN
        assert fact.verification_status is VerificationStatus.PENDING_REVIEW


def test_unverified_existing_product_shipping_remains_unknown_not_false(
    catalog_data,
) -> None:  # type: ignore[no-untyped-def]
    bundle, products = catalog_data
    product = next(item for item in products if is_recommendation_eligible(item))

    passport = build_product_passport(product, bundle)
    shipping = next(
        fact for fact in passport.commercial_facts if fact.field_name == "international_shipping"
    )

    assert product.commercial_data_status in {"demo_assumption", "pending_verification"}
    assert shipping.value is None
    assert shipping.source is FactSource.UNKNOWN
    assert shipping.verification_status is VerificationStatus.UNKNOWN
    assert "不支持国际运输" not in str(shipping.source_note)


def test_existing_product_passport_keeps_traceable_cultural_sources(
    catalog_data,
) -> None:  # type: ignore[no-untyped-def]
    bundle, products = catalog_data
    product = next(item for item in products if is_recommendation_eligible(item))

    passport = build_product_passport(product, bundle)

    assert passport.cultural_sources
    assert all(source.url.startswith("https://") for source in passport.cultural_sources)
    assert all(source.source is FactSource.PUBLIC_SOURCE for source in passport.cultural_sources)
    assert all(
        source.verification_status is VerificationStatus.CONFIRMED
        for source in passport.cultural_sources
    )
    assert {source.url for source in passport.cultural_sources} <= {
        product.source_culture_url,
        product.reference_source_url,
    }


def test_artisan_passport_preserves_unknown_shipping_and_source_provenance() -> None:
    draft = create_draft(
        "artisan-session",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            "international_shipping": "暂不确定",
            "merchant_source_url": "https://example.org/merchant-source",
        },
    )

    passport = build_passport(draft)
    shipping = next(
        fact for fact in passport.commercial_facts if fact.field_name == "international_shipping"
    )
    source = passport.cultural_sources[0]

    assert shipping.value is None
    assert shipping.source is FactSource.UNKNOWN
    assert shipping.verification_status is VerificationStatus.UNKNOWN
    assert passport.commercial_verification_status is VerificationStatus.UNKNOWN
    assert source.url == "https://example.org/merchant-source"
    assert source.source is FactSource.ARTISAN_PROVIDED
    assert source.verification_status is VerificationStatus.PENDING_REVIEW


def test_catalog_passport_adapter_covers_all_products_without_changing_boundaries(
    catalog_data,
) -> None:  # type: ignore[no-untyped-def]
    bundle, products = catalog_data

    passports = build_catalog_passports(products, bundle)

    assert len(passports) == 51
    assert set(passports) == {product.product_id for product in products}
    assert (
        sum(
            passport.publication_status is PublicationStatus.RECOMMENDABLE
            for passport in passports.values()
        )
        == 21
    )
    assert (
        sum(
            passport.publication_status is PublicationStatus.REFERENCE_ONLY
            for passport in passports.values()
        )
        == 30
    )
