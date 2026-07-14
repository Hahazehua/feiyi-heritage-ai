"""CSV loading, normalization and cross-table validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from heritagelink.models import MVP_DISCLAIMER_PREFIX, DataBundle, Product, readonly_mapping


class DataValidationError(ValueError):
    """Raised when local product data cannot safely feed the recommender."""


TABLE_COLUMNS = {
    "merchants.csv": {
        "merchant_id",
        "merchant_name_zh",
        "merchant_name_en",
        "city",
        "province",
        "contact_channel",
        "status",
        "data_version",
        "is_demo",
    },
    "heritage_items.csv": {
        "heritage_id",
        "heritage_name_zh",
        "heritage_name_en",
        "category_code",
        "region",
        "official_level",
        "verification_note",
        "status",
        "data_version",
        "is_demo",
    },
    "products.csv": {
        "product_id",
        "merchant_id",
        "heritage_id",
        "sku",
        "product_name_zh",
        "product_name_en",
        "price_min_fen",
        "price_max_fen",
        "min_order_qty",
        "recommended_max_qty",
        "demo_max_order_qty",
        "lead_time_days",
        "dimensions_text",
        "material_text",
        "recipient_tags",
        "occasion_tags",
        "style_tags",
        "meaning_tags",
        "supports_international_shipping",
        "shipping_note",
        "status",
        "data_version",
        "is_demo",
        "demo_disclaimer",
    },
    "product_texts.csv": {
        "product_id",
        "locale",
        "craft_summary",
        "cultural_story",
        "meaning_summary",
        "source_note",
        "review_status",
        "reviewed_at",
        "is_demo",
    },
    "customization_options.csv": {
        "customization_option_id",
        "product_id",
        "customization_type",
        "description_zh",
        "description_en",
        "price_impact",
        "extra_lead_days",
        "enabled",
        "is_demo",
        "demo_disclaimer",
    },
}

ID_RULES = {
    "merchant_id": r"^mer_[a-z0-9_]+$",
    "heritage_id": r"^heritage_[a-z0-9_]+$",
    "product_id": r"^prod_[a-z0-9_]+$",
    "customization_option_id": r"^custopt_[a-z0-9_]+$",
}
STATUS_VALUES = {"active", "inactive"}
OFFICIAL_LEVEL_VALUES = {
    "national",
    "provincial",
    "municipal",
    "county",
    "other",
    "unverified",
}
LOCALE_VALUES = {"zh-CN", "en"}
REVIEW_STATUS_VALUES = {"draft", "approved"}
CUSTOMIZATION_TYPES = {"inscription", "pattern", "size", "packaging", "color", "logo", "other"}
PRICE_IMPACT_VALUES = {"none", "possible", "required_quote"}
TAG_COLUMNS = ("recipient_tags", "occasion_tags", "style_tags", "meaning_tags")


def _read_csv(data_dir: Path, file_name: str) -> pd.DataFrame:
    path = data_dir / file_name
    if not path.exists():
        raise DataValidationError(f"缺少数据文件 {file_name}：{path}")
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"{file_name} 为空且没有表头：{path}") from exc
    if frame.empty:
        raise DataValidationError(f"{file_name} 没有任何记录：{path}")
    missing = sorted(TABLE_COLUMNS[file_name] - set(frame.columns))
    if missing:
        raise DataValidationError(f"{file_name} 缺少必需字段：{', '.join(missing)}")
    return frame


def _require_nonempty(frame: pd.DataFrame, file_name: str, columns: set[str]) -> None:
    for column in columns:
        empty_rows = frame.index[frame[column].astype(str).str.strip() == ""].tolist()
        if empty_rows:
            rows = ", ".join(str(row + 2) for row in empty_rows)
            raise DataValidationError(f"{file_name} 字段 {column} 在 CSV 行 {rows} 不能为空")


def _validate_ids(frame: pd.DataFrame, file_name: str, id_column: str) -> None:
    _require_nonempty(frame, file_name, {id_column})
    duplicates = frame.loc[frame[id_column].duplicated(), id_column].tolist()
    if duplicates:
        raise DataValidationError(f"{file_name} 的 {id_column} 存在重复值：{duplicates}")
    pattern = re.compile(ID_RULES[id_column])
    invalid = [value for value in frame[id_column] if not pattern.fullmatch(value)]
    if invalid:
        raise DataValidationError(f"{file_name} 的 {id_column} 格式非法：{invalid}")


def _parse_bool(value: str, file_name: str, column: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise DataValidationError(
            f"{file_name} 字段 {column} 在 CSV 行 {row_number} 必须为 true 或 false"
        )
    return normalized == "true"


def _parse_int(
    value: str,
    file_name: str,
    column: str,
    row_number: int,
    *,
    optional: bool = False,
) -> int | None:
    normalized = value.strip()
    if optional and not normalized:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise DataValidationError(
            f"{file_name} 字段 {column} 在 CSV 行 {row_number} 必须为整数"
        ) from exc
    return parsed


def _parse_tags(value: str, file_name: str, column: str, row_number: int) -> frozenset[str]:
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DataValidationError(
            f"{file_name} 字段 {column} 在 CSV 行 {row_number} 必须是合法 JSON 数组"
        ) from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, str) and item.strip() for item in parsed)
    ):
        raise DataValidationError(
            f"{file_name} 字段 {column} 在 CSV 行 {row_number} 必须是非空字符串数组"
        )
    normalized = frozenset(item.strip().lower() for item in parsed)
    if any(not re.fullmatch(r"[a-z0-9_]+", item) for item in normalized):
        raise DataValidationError(f"{file_name} 字段 {column} 在 CSV 行 {row_number} 含非法标签")
    return normalized


def _validate_enum(frame: pd.DataFrame, file_name: str, column: str, allowed: set[str]) -> None:
    invalid = sorted(set(frame[column]) - allowed)
    if invalid:
        raise DataValidationError(
            f"{file_name} 字段 {column} 含非法值 {invalid}；允许值为 {sorted(allowed)}"
        )


def _normalize_merchants(frame: pd.DataFrame) -> pd.DataFrame:
    file_name = "merchants.csv"
    _validate_ids(frame, file_name, "merchant_id")
    _require_nonempty(
        frame,
        file_name,
        {"merchant_name_zh", "merchant_name_en", "city", "province", "status", "data_version"},
    )
    _validate_enum(frame, file_name, "status", STATUS_VALUES)
    frame["is_demo"] = [
        _parse_bool(value, file_name, "is_demo", row + 2)
        for row, value in enumerate(frame["is_demo"])
    ]
    if not frame["is_demo"].all():
        raise DataValidationError("merchants.csv 的 MVP 数据必须全部标记 is_demo=true")
    return frame


def _normalize_heritage_items(frame: pd.DataFrame) -> pd.DataFrame:
    file_name = "heritage_items.csv"
    _validate_ids(frame, file_name, "heritage_id")
    _require_nonempty(
        frame,
        file_name,
        {
            "heritage_name_zh",
            "heritage_name_en",
            "category_code",
            "region",
            "official_level",
            "verification_note",
            "status",
            "data_version",
        },
    )
    _validate_enum(frame, file_name, "status", STATUS_VALUES)
    _validate_enum(frame, file_name, "official_level", OFFICIAL_LEVEL_VALUES)
    frame["is_demo"] = [
        _parse_bool(value, file_name, "is_demo", row + 2)
        for row, value in enumerate(frame["is_demo"])
    ]
    if not frame["is_demo"].all():
        raise DataValidationError("heritage_items.csv 的 MVP 数据必须全部标记 is_demo=true")
    return frame


def _normalize_products(frame: pd.DataFrame) -> pd.DataFrame:
    file_name = "products.csv"
    _validate_ids(frame, file_name, "product_id")
    _require_nonempty(
        frame,
        file_name,
        TABLE_COLUMNS[file_name] - {"recommended_max_qty", "demo_max_order_qty"},
    )
    _validate_enum(frame, file_name, "status", STATUS_VALUES)
    if frame.duplicated(subset=["merchant_id", "sku"]).any():
        raise DataValidationError("products.csv 的 merchant_id + sku 必须唯一")

    required_ints = ("price_min_fen", "price_max_fen", "min_order_qty", "lead_time_days")
    optional_ints = ("recommended_max_qty", "demo_max_order_qty")
    for column in required_ints:
        frame[column] = [
            _parse_int(value, file_name, column, row + 2) for row, value in enumerate(frame[column])
        ]
    for column in optional_ints:
        frame[column] = [
            _parse_int(value, file_name, column, row + 2, optional=True)
            for row, value in enumerate(frame[column])
        ]

    for row_index, row in frame.iterrows():
        row_number = row_index + 2
        if row["price_min_fen"] < 0 or row["price_max_fen"] < row["price_min_fen"]:
            raise DataValidationError(f"products.csv 在 CSV 行 {row_number} 的价格范围非法")
        if row["min_order_qty"] < 1 or row["lead_time_days"] < 0:
            raise DataValidationError(f"products.csv 在 CSV 行 {row_number} 的数量或交期非法")
        for column in optional_ints:
            value = row[column]
            if value is not None and value < row["min_order_qty"]:
                raise DataValidationError(
                    f"products.csv 字段 {column} 在 CSV 行 {row_number} 不能低于最低起订量"
                )
        if (
            row["recommended_max_qty"] is not None
            and row["demo_max_order_qty"] is not None
            and row["recommended_max_qty"] > row["demo_max_order_qty"]
        ):
            raise DataValidationError(
                f"products.csv 在 CSV 行 {row_number} 的建议数量不能超过演示允许数量"
            )
        if not row["demo_disclaimer"].strip().startswith(MVP_DISCLAIMER_PREFIX):
            raise DataValidationError(
                f"products.csv 在 CSV 行 {row_number} 必须明确标注为 MVP 演示数据"
            )

    for column in TAG_COLUMNS:
        frame[column] = [
            _parse_tags(value, file_name, column, row + 2)
            for row, value in enumerate(frame[column])
        ]
    for column in ("supports_international_shipping", "is_demo"):
        frame[column] = [
            _parse_bool(value, file_name, column, row + 2)
            for row, value in enumerate(frame[column])
        ]
    if not frame["is_demo"].all():
        raise DataValidationError("products.csv 的 MVP 数据必须全部标记 is_demo=true")
    return frame


def _normalize_product_texts(frame: pd.DataFrame) -> pd.DataFrame:
    file_name = "product_texts.csv"
    _require_nonempty(
        frame,
        file_name,
        TABLE_COLUMNS[file_name] - {"reviewed_at"},
    )
    if frame.duplicated(subset=["product_id", "locale"]).any():
        raise DataValidationError("product_texts.csv 的 product_id + locale 必须唯一")
    _validate_enum(frame, file_name, "locale", LOCALE_VALUES)
    _validate_enum(frame, file_name, "review_status", REVIEW_STATUS_VALUES)
    approved_without_date = frame[
        (frame["review_status"] == "approved") & (frame["reviewed_at"].str.strip() == "")
    ]
    if not approved_without_date.empty:
        raise DataValidationError("product_texts.csv 中 approved 文案必须填写 reviewed_at")
    frame["is_demo"] = [
        _parse_bool(value, file_name, "is_demo", row + 2)
        for row, value in enumerate(frame["is_demo"])
    ]
    if not frame["is_demo"].all():
        raise DataValidationError("product_texts.csv 的 MVP 数据必须全部标记 is_demo=true")
    return frame


def _normalize_customization_options(frame: pd.DataFrame) -> pd.DataFrame:
    file_name = "customization_options.csv"
    _validate_ids(frame, file_name, "customization_option_id")
    _require_nonempty(frame, file_name, TABLE_COLUMNS[file_name])
    _validate_enum(frame, file_name, "customization_type", CUSTOMIZATION_TYPES)
    _validate_enum(frame, file_name, "price_impact", PRICE_IMPACT_VALUES)
    frame["extra_lead_days"] = [
        _parse_int(value, file_name, "extra_lead_days", row + 2)
        for row, value in enumerate(frame["extra_lead_days"])
    ]
    if (frame["extra_lead_days"] < 0).any():
        raise DataValidationError("customization_options.csv 的 extra_lead_days 不能为负数")
    for column in ("enabled", "is_demo"):
        frame[column] = [
            _parse_bool(value, file_name, column, row + 2)
            for row, value in enumerate(frame[column])
        ]
    if not frame["is_demo"].all():
        raise DataValidationError("customization_options.csv 的 MVP 数据必须全部标记 is_demo=true")
    invalid_disclaimer_rows = frame.index[
        ~frame["demo_disclaimer"].str.strip().str.startswith(MVP_DISCLAIMER_PREFIX)
    ].tolist()
    if invalid_disclaimer_rows:
        rows = ", ".join(str(row + 2) for row in invalid_disclaimer_rows)
        raise DataValidationError(
            f"customization_options.csv 在 CSV 行 {rows} 必须明确标注为 MVP 演示数据"
        )
    return frame


def _validate_foreign_keys(bundle: DataBundle) -> None:
    merchant_ids = set(bundle.merchants["merchant_id"])
    heritage_ids = set(bundle.heritage_items["heritage_id"])
    product_ids = set(bundle.products["product_id"])

    unknown_merchants = sorted(set(bundle.products["merchant_id"]) - merchant_ids)
    unknown_heritage = sorted(set(bundle.products["heritage_id"]) - heritage_ids)
    unknown_text_products = sorted(set(bundle.product_texts["product_id"]) - product_ids)
    unknown_option_products = sorted(set(bundle.customization_options["product_id"]) - product_ids)
    if unknown_merchants:
        raise DataValidationError(f"products.csv 引用了不存在的 merchant_id：{unknown_merchants}")
    if unknown_heritage:
        raise DataValidationError(f"products.csv 引用了不存在的 heritage_id：{unknown_heritage}")
    if unknown_text_products:
        raise DataValidationError(
            f"product_texts.csv 引用了不存在的 product_id：{unknown_text_products}"
        )
    if unknown_option_products:
        raise DataValidationError(
            f"customization_options.csv 引用了不存在的 product_id：{unknown_option_products}"
        )

    active_product_ids = set(
        bundle.products.loc[bundle.products["status"] == "active", "product_id"]
    )
    for product_id in sorted(active_product_ids):
        locales = set(
            bundle.product_texts.loc[bundle.product_texts["product_id"] == product_id, "locale"]
        )
        if locales != LOCALE_VALUES:
            raise DataValidationError(
                f"active 产品 {product_id} 必须且只能各有一条 zh-CN 和 en 文案"
            )


def load_data(data_dir: str | Path) -> DataBundle:
    """Load and validate all five local CSV tables."""
    directory = Path(data_dir)
    bundle = DataBundle(
        merchants=_normalize_merchants(_read_csv(directory, "merchants.csv")),
        heritage_items=_normalize_heritage_items(_read_csv(directory, "heritage_items.csv")),
        products=_normalize_products(_read_csv(directory, "products.csv")),
        product_texts=_normalize_product_texts(_read_csv(directory, "product_texts.csv")),
        customization_options=_normalize_customization_options(
            _read_csv(directory, "customization_options.csv")
        ),
    )
    _validate_foreign_keys(bundle)
    return bundle


def build_products(bundle: DataBundle) -> tuple[Product, ...]:
    """Join validated tables into merchant-agnostic product domain objects."""
    merchants = bundle.merchants.set_index("merchant_id").to_dict("index")
    heritage_items = bundle.heritage_items.set_index("heritage_id").to_dict("index")
    products: list[Product] = []

    for _, row in bundle.products.iterrows():
        option_rows = bundle.customization_options[
            (bundle.customization_options["product_id"] == row["product_id"])
            & bundle.customization_options["enabled"]
        ]
        extra_days = {
            option["customization_type"]: int(option["extra_lead_days"])
            for _, option in option_rows.iterrows()
        }
        text_rows = bundle.product_texts[bundle.product_texts["product_id"] == row["product_id"]]
        merchant = merchants[row["merchant_id"]]
        heritage = heritage_items[row["heritage_id"]]
        products.append(
            Product(
                product_id=row["product_id"],
                merchant_id=row["merchant_id"],
                merchant_name_zh=merchant["merchant_name_zh"],
                heritage_id=row["heritage_id"],
                sku=row["sku"],
                product_name_zh=row["product_name_zh"],
                product_name_en=row["product_name_en"],
                price_min_fen=int(row["price_min_fen"]),
                price_max_fen=int(row["price_max_fen"]),
                min_order_qty=int(row["min_order_qty"]),
                recommended_max_qty=row["recommended_max_qty"],
                demo_max_order_qty=row["demo_max_order_qty"],
                lead_time_days=int(row["lead_time_days"]),
                dimensions_text=row["dimensions_text"],
                material_text=row["material_text"],
                recipient_tags=row["recipient_tags"],
                occasion_tags=row["occasion_tags"],
                style_tags=row["style_tags"],
                meaning_tags=row["meaning_tags"],
                supports_international_shipping=bool(row["supports_international_shipping"]),
                shipping_note=row["shipping_note"],
                status=row["status"],
                merchant_status=merchant["status"],
                heritage_status=heritage["status"],
                data_version=row["data_version"],
                is_demo=bool(row["is_demo"]),
                demo_disclaimer=row["demo_disclaimer"],
                customization_options=frozenset(extra_days),
                customization_extra_lead_days=readonly_mapping(extra_days),
                content_review_statuses=frozenset(text_rows["review_status"]),
            )
        )
    return tuple(products)
