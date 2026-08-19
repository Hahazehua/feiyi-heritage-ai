from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from heritagelink.data_loader import build_products, load_data
from heritagelink.models import GiftRequest
from heritagelink.recommender import recommend

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "demo"
CATALOG_DIR = ROOT / "data" / "catalog"


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    products = pd.read_csv(DATA_DIR / "products.csv", dtype=str, keep_default_na=False)
    merchants = pd.read_csv(DATA_DIR / "merchants.csv", dtype=str, keep_default_na=False)
    heritage = pd.read_csv(DATA_DIR / "heritage_items.csv", dtype=str, keep_default_na=False)
    texts = pd.read_csv(DATA_DIR / "product_texts.csv", dtype=str, keep_default_na=False)
    return products, merchants, heritage, texts


def _tag_values(products: pd.DataFrame, column: str) -> set[str]:
    values: set[str] = set()
    for value in products[column]:
        values.update(json.loads(value))
    return values


def test_catalog_has_exactly_fifty_unique_products_and_valid_foreign_keys() -> None:
    products, merchants, heritage, _ = _frames()
    assert len(products) == 54
    assert products["product_id"].nunique() == 54
    assert set(products["merchant_id"]) <= set(merchants["merchant_id"])
    assert set(products["heritage_id"]) <= set(heritage["heritage_id"])
    assert products["product_name_zh"].str.strip().ne("").all()
    assert products["product_name_en"].str.strip().ne("").all()


def test_coverage_targets_are_met_without_category_concentration() -> None:
    products, _, _, _ = _frames()
    assert products["category_code"].nunique() >= 10
    assert products["region_code"].nunique() >= 6
    assert products["price_tier"].nunique() >= 4
    assert products["category_code"].value_counts(normalize=True).max() < 0.4
    assert len(_tag_values(products, "occasion_tags")) >= 8
    assert len(_tag_values(products, "recipient_tags")) >= 6
    assert len(_tag_values(products, "meaning_tags")) >= 6
    options = pd.read_csv(DATA_DIR / "customization_options.csv", dtype=str)
    assert options["customization_type"].nunique() >= 5


def test_every_price_tier_has_at_least_five_records() -> None:
    products, _, _, _ = _frames()
    assert (products["price_tier"].value_counts() >= 5).all()


def test_sources_fact_boundaries_and_quality_are_complete() -> None:
    products, _, _, _ = _frames()
    required = [
        "source_product_url",
        "source_culture_url",
        "source_type",
        "source_accessed_at",
        "source_status",
        "verification_status",
        "commercial_data_status",
        "cultural_data_status",
        "data_quality_level",
        "image_status",
        "image_attribution",
    ]
    assert products[required].apply(lambda column: column.str.strip().ne("").all()).all()
    uncertain = products["commercial_data_status"].isin(["demo_assumption", "pending_verification"])
    assert not (uncertain & products["merchant_fact_status"].eq("verified_merchant_fact")).any()
    assert set(products["data_quality_level"]) <= {"A", "B", "C"}


def test_catalog_references_are_not_formal_recommendation_candidates() -> None:
    bundle = load_data(DATA_DIR)
    products = build_products(bundle)
    references = [product for product in products if product.catalog_role == "catalog_reference"]
    assert len(references) == 30
    assert all(product.status == "inactive" for product in references)
    assert all(not product.supports_international_shipping for product in references)
    assert all(not product.customization_options for product in references)

    request = GiftRequest(
        request_id="catalog-boundary",
        unit_budget_max_fen=1_000_000,
        quantity=1,
    )
    response = recommend(products, request)
    recommended_ids = {item.product.product_id for item in response.recommendations}
    assert recommended_ids.isdisjoint({product.product_id for product in references})


def test_images_and_bilingual_texts_are_complete() -> None:
    products, _, _, texts = _frames()
    assert all((ROOT / path).is_file() for path in products["image_path"])
    assert products["image_path"].nunique() == 54
    assert len(texts) == 108
    assert not texts.duplicated(["product_id", "locale"]).any()
    assert set(texts["locale"]) == {"zh-CN", "en"}
    assert texts.groupby("product_id")["locale"].nunique().eq(2).all()


def test_source_registry_research_log_and_coverage_matrix_link_cleanly() -> None:
    products, _, _, _ = _frames()
    product_ids = set(products["product_id"])
    sources = pd.read_csv(CATALOG_DIR / "source_registry.csv", dtype=str)
    research = pd.read_csv(CATALOG_DIR / "research_log.csv", dtype=str)
    coverage = pd.read_csv(CATALOG_DIR / "coverage_matrix.csv", dtype=str)
    assert set(sources["product_id"]) == product_ids
    assert len(research) == 30
    assert set(research["product_id"]) == set(
        products.loc[products["catalog_role"] == "catalog_reference", "product_id"]
    )
    assert len(coverage) == 54
    assert set(coverage["product_id"]) == product_ids


def test_loading_performance_and_sorting_remain_stable() -> None:
    started = time.perf_counter()
    products = build_products(load_data(DATA_DIR))
    assert time.perf_counter() - started < 2.0
    request = GiftRequest(
        request_id="stable-order",
        unit_budget_max_fen=200_000,
        quantity=1,
        recipient_tags=frozenset({"business_partner"}),
        occasion_tags=frozenset({"business_gift"}),
    )
    first = recommend(products, request)
    second = recommend(products, request)
    assert [item.product.product_id for item in first.recommendations] == [
        item.product.product_id for item in second.recommendations
    ]
