from pathlib import Path

import pytest

from heritagelink.catalog import CatalogDataError, load_reference_catalog
from heritagelink.data_loader import load_data

ROOT = Path(__file__).parents[1]
CATALOG_PATH = ROOT / "data" / "catalog" / "heritage_products.csv"


def test_reference_catalog_contains_twenty_traceable_items() -> None:
    items = load_reference_catalog(CATALOG_PATH, project_root=ROOT)

    assert len(items) == 20
    assert len({item.catalog_product_id for item in items}) == 20
    assert len({item.demo_product_id for item in items}) == 20
    assert {item.craft_category_en for item in items} >= {
        "Lacquer carving",
        "Longquan celadon",
        "Chinese embroidery",
        "Chinese jade carving",
    }
    assert all(item.source_url.startswith("https://www.metmuseum.org/") for item in items)
    assert all(item.image_license == "CC0 1.0 / Public Domain" for item in items)
    assert all(item.commercial_status == "museum_reference_not_for_sale" for item in items)


def test_reference_catalog_links_every_recommendation_product() -> None:
    items = load_reference_catalog(CATALOG_PATH, project_root=ROOT)
    product_ids = set(load_data(ROOT / "data" / "demo").products["product_id"])

    assert {item.demo_product_id for item in items} == product_ids


def test_reference_catalog_images_exist_and_are_jpegs() -> None:
    items = load_reference_catalog(CATALOG_PATH, project_root=ROOT)

    for item in items:
        image_file = item.image_file(ROOT)
        assert image_file.is_file()
        assert image_file.stat().st_size > 10_000
        assert image_file.read_bytes()[:3] == b"\xff\xd8\xff"


def test_reference_catalog_missing_fields_has_clear_error(tmp_path: Path) -> None:
    invalid_catalog = tmp_path / "heritage_products.csv"
    invalid_catalog.write_text(
        "catalog_product_id,product_name_zh\nCAT-001,测试藏品\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogDataError, match="缺少字段"):
        load_reference_catalog(invalid_catalog, project_root=tmp_path)
