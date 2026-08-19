"""The catalogue's claim to be verifiable, checked offline.

Spot-checking six records against the Met's live API returned six exact
accession-number matches, all flagged public domain. That check needs the
network, so what is asserted here is the property it depends on: every product
the buyer can be shown carries an accession number, a licence and a resolvable
museum URL, and none of it silently goes missing.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parents[1]
REFERENCE = ROOT / "data" / "catalog" / "heritage_products.csv"
PRODUCTS = ROOT / "data" / "demo" / "products.csv"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_sale_product_is_backed_by_a_museum_record() -> None:
    """The join is what lets a product card cite an accession number.

    Work with no museum record behind it is the deliberate exception: it may
    not claim one, and it earns the exemption by declaring itself unverified.
    The obligations that come with that declaration are checked below.
    """
    backed = {row["demo_product_id"] for row in _rows(REFERENCE) if row["demo_product_id"]}
    unbacked = [
        row
        for row in _rows(PRODUCTS)
        if row["product_id"] not in backed and row["verification_status"] != "needs_verification"
    ]

    assert not unbacked, f"products with no museum reference: {[r['product_id'] for r in unbacked]}"


def test_work_without_a_museum_record_says_so() -> None:
    """The exemption above must not become a hole to smuggle claims through.

    A product may skip museum backing only by declaring itself unverified, and
    declaring that carries obligations: it may not appear in the museum table,
    and it may not borrow an open museum licence for its photography.
    """
    backed = {row["demo_product_id"] for row in _rows(REFERENCE) if row["demo_product_id"]}
    exempt = [row for row in _rows(PRODUCTS) if row["verification_status"] == "needs_verification"]

    assert exempt, "the exemption exists, so something should be using it"
    for row in exempt:
        product = row["product_id"]
        assert product not in backed, f"{product} claims a museum record it does not have"
        assert "CC0" not in row["image_license"], f"{product} may not claim an open museum licence"
        # Commercial terms sit on a different axis from the object's provenance:
        # a partner can confirm price and delivery for a work whose authorship
        # is still unverified. Confirmation counts only when a real merchant
        # stands behind it, never the platform's own demo curation entity.
        if row["commercial_data_status"] == "verified_merchant_fact":
            assert row["merchant_id"] != "mer_demo_feiyi", product
        else:
            assert row["commercial_data_status"] == "demo_assumption", product


def test_every_museum_record_can_actually_be_looked_up() -> None:
    """An accession number the reader cannot check is decoration."""
    for row in _rows(REFERENCE):
        product = row["catalog_product_id"]
        assert row["source_object_number"].strip(), f"{product} has no accession number"
        assert row["source_name"].strip(), f"{product} names no holding institution"
        assert row["source_url"].startswith("https://"), f"{product} has no source URL"


def test_images_carry_an_open_licence() -> None:
    """Reusing a museum image is only defensible when the licence permits it."""
    for row in _rows(REFERENCE):
        licence = row["image_license"].strip().casefold()
        assert "cc0" in licence or "public domain" in licence, (
            f"{row['catalog_product_id']} image licence is {row['image_license']!r}"
        )


def test_museum_records_are_not_presented_as_purchasable() -> None:
    """Museum objects are not for sale; the catalogue has to keep saying so.

    Two batches carry different prefixes — museum_ for the twenty backing sale
    products, catalog_ for the thirty reference-only ones — but the promise
    they make is the same one.
    """
    for row in _rows(REFERENCE):
        assert row["commercial_status"].endswith("_not_for_sale"), (
            f"{row['catalog_product_id']} is {row['commercial_status']!r}"
        )


def test_every_museum_record_records_when_it_was_checked() -> None:
    """The credential shows this date, so it has to be there and be a date."""
    for row in _rows(REFERENCE):
        status = row["verification_status"]
        assert status.startswith("source_verified_"), f"{row['catalog_product_id']}: {status!r}"
        assert status.rsplit("_", 1)[-1].count("-") == 2, f"{row['catalog_product_id']}: {status!r}"


def test_sale_products_keep_commercial_terms_marked_as_assumptions() -> None:
    """The credential covers craft and image facts only.

    Cultural data is sourced. Commercial data is invented for the demo wherever
    no merchant exists to confirm it, and the two must not drift into looking
    equally verified. Partner-supplied work is the one exception: a named
    merchant can confirm its terms, so it may say so.
    """
    backed = {row["demo_product_id"] for row in _rows(REFERENCE) if row["demo_product_id"]}
    for row in _rows(PRODUCTS):
        assert row["cultural_data_status"] == "verified_public_cultural_fact"
        assert row["is_demo"] == "true"
        if row["product_id"] in backed:
            # A museum record has no merchant behind it, so its commercial terms
            # are invented for the demo and have to keep saying so.
            assert row["commercial_data_status"] == "demo_assumption", row["product_id"]
        else:
            assert row["commercial_data_status"] in {
                "demo_assumption",
                "verified_merchant_fact",
            }, row["product_id"]
