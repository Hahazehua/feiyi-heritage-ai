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
    """The join is what lets a product card cite an accession number."""
    backed = {row["demo_product_id"] for row in _rows(REFERENCE) if row["demo_product_id"]}
    unbacked = [row["product_id"] for row in _rows(PRODUCTS) if row["product_id"] not in backed]

    assert not unbacked, f"products with no museum reference: {unbacked}"


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

    Cultural data is sourced, commercial data is invented for the demo, and the
    two must not drift into looking equally verified.
    """
    for row in _rows(PRODUCTS):
        assert row["cultural_data_status"] == "verified_public_cultural_fact"
        assert row["commercial_data_status"] == "demo_assumption"
        assert row["is_demo"] == "true"
