from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.models import DEMO_DISCLAIMER

DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "demo"
    shutil.copytree(DATA_DIR, target)
    return target


def _rewrite_products(data_dir: Path, mutate: object) -> None:
    path = data_dir / "products.csv"
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if callable(mutate):
        mutate(frame)
    frame.to_csv(path, index=False, encoding="utf-8")


def test_loads_expected_demo_dataset() -> None:
    bundle = load_data(DATA_DIR)
    products = build_products(bundle)

    assert len(bundle.merchants) == 1
    assert len(bundle.heritage_items) == 4
    assert len(products) == 20
    assert len(bundle.product_texts) == 40
    assert all(product.is_demo for product in products)
    assert all(product.demo_disclaimer == DEMO_DISCLAIMER for product in products)
    assert all((Path(__file__).parents[1] / product.image_path).is_file() for product in products)
    assert len({product.image_path for product in products}) == 20
    assert (bundle.customization_options["demo_disclaimer"] == DEMO_DISCLAIMER).all()
    assert (bundle.heritage_items["official_level"] == "unverified").all()


def test_missing_csv_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    (data_dir / "merchants.csv").unlink()

    with pytest.raises(DataValidationError, match="缺少数据文件.*merchants.csv"):
        load_data(data_dir)


def test_missing_required_column_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def drop_column(frame: pd.DataFrame) -> None:
        frame.drop(columns=["price_min_fen"], inplace=True)

    _rewrite_products(data_dir, drop_column)

    with pytest.raises(DataValidationError, match="products.csv 缺少必需字段：price_min_fen"):
        load_data(data_dir)


def test_illegal_money_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def break_money(frame: pd.DataFrame) -> None:
        frame.loc[0, "price_min_fen"] = "not-an-integer"

    _rewrite_products(data_dir, break_money)

    with pytest.raises(DataValidationError, match="price_min_fen.*必须为整数"):
        load_data(data_dir)


def test_illegal_quantity_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def break_quantity(frame: pd.DataFrame) -> None:
        frame.loc[0, "min_order_qty"] = "0"

    _rewrite_products(data_dir, break_quantity)

    with pytest.raises(DataValidationError, match="数量或交期非法"):
        load_data(data_dir)


def test_empty_csv_records_raise_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "products.csv"
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.iloc[0:0].to_csv(path, index=False, encoding="utf-8")

    with pytest.raises(DataValidationError, match="products.csv.*没有任何记录"):
        load_data(data_dir)


def test_invalid_foreign_key_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def break_merchant(frame: pd.DataFrame) -> None:
        frame.loc[0, "merchant_id"] = "mer_missing"

    _rewrite_products(data_dir, break_merchant)

    with pytest.raises(DataValidationError, match="不存在的 merchant_id"):
        load_data(data_dir)


def test_missing_product_image_raises_clear_error(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def break_image(frame: pd.DataFrame) -> None:
        frame.loc[0, "image_path"] = "assets/products/missing.jpg"

    _rewrite_products(data_dir, break_image)

    with pytest.raises(DataValidationError, match="找不到图片"):
        load_data(data_dir)


def test_incomplete_demo_disclaimer_is_rejected(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    def break_disclaimer(frame: pd.DataFrame) -> None:
        frame.loc[0, "demo_disclaimer"] = "仅供演示"

    _rewrite_products(data_dir, break_disclaimer)

    with pytest.raises(DataValidationError, match="明确标注为 MVP 演示数据"):
        load_data(data_dir)


def test_loader_supports_more_than_one_merchant(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)

    merchants_path = data_dir / "merchants.csv"
    merchants = pd.read_csv(merchants_path, dtype=str, keep_default_na=False)
    other_merchant = merchants.iloc[0].copy()
    other_merchant["merchant_id"] = "mer_demo_other"
    other_merchant["merchant_name_zh"] = "另一非遗演示商家"
    other_merchant["merchant_name_en"] = "Another Heritage Demo Merchant"
    pd.concat([merchants, other_merchant.to_frame().T], ignore_index=True).to_csv(
        merchants_path, index=False, encoding="utf-8"
    )

    products_path = data_dir / "products.csv"
    product_rows = pd.read_csv(products_path, dtype=str, keep_default_na=False)
    other_product = product_rows.iloc[2].copy()
    other_product["product_id"] = "prod_demo_other_001"
    other_product["merchant_id"] = "mer_demo_other"
    other_product["sku"] = "DEMO-OTHER-001"
    other_product["demo_disclaimer"] = "MVP演示数据"
    pd.concat([product_rows, other_product.to_frame().T], ignore_index=True).to_csv(
        products_path, index=False, encoding="utf-8"
    )

    texts_path = data_dir / "product_texts.csv"
    text_rows = pd.read_csv(texts_path, dtype=str, keep_default_na=False)
    other_texts = text_rows[text_rows["product_id"] == "prod_demo_003"].copy()
    other_texts["product_id"] = "prod_demo_other_001"
    pd.concat([text_rows, other_texts], ignore_index=True).to_csv(
        texts_path, index=False, encoding="utf-8"
    )

    products = build_products(load_data(data_dir))

    assert len(products) == 21
    assert any(product.merchant_id == "mer_demo_other" for product in products)
