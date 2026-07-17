"""Load and validate the source-traceable heritage reference catalogue."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


class CatalogDataError(ValueError):
    """Raised when the reference catalogue cannot be used safely."""


@dataclass(frozen=True, slots=True)
class HeritageReferenceItem:
    """A museum reference item that is intentionally separate from sale products."""

    catalog_product_id: str
    demo_product_id: str
    source_object_id: str
    product_name_zh: str
    product_name_en: str
    craft_category_zh: str
    craft_category_en: str
    period_text: str
    region_text: str
    material_text: str
    dimensions_text: str
    introduction_zh: str
    introduction_en: str
    image_path: str
    source_url: str
    image_source_url: str
    source_name: str
    source_object_number: str
    image_license: str
    commercial_status: str
    verification_status: str

    def image_file(self, project_root: Path) -> Path:
        """Return the validated local image path for this item."""
        return project_root / PurePosixPath(self.image_path)


REQUIRED_FIELDS = tuple(HeritageReferenceItem.__dataclass_fields__)
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _validate_https_url(value: str, *, row_number: int, field_name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CatalogDataError(
            f"heritage_products.csv 第 {row_number} 行的 {field_name} 必须是完整 HTTPS 地址"
        )


def _validate_image_path(value: str, *, row_number: int, project_root: Path) -> None:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise CatalogDataError(
            f"heritage_products.csv 第 {row_number} 行的 image_path 必须是安全的相对路径"
        )
    if relative.parts[:3] != ("assets", "catalog", "products"):
        raise CatalogDataError(
            f"heritage_products.csv 第 {row_number} 行的图片必须位于 assets/catalog/products"
        )
    image_file = project_root / relative
    if image_file.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        raise CatalogDataError(
            f"heritage_products.csv 第 {row_number} 行的图片格式不受支持：{image_file.suffix}"
        )
    if not image_file.is_file():
        raise CatalogDataError(f"heritage_products.csv 第 {row_number} 行找不到本地图片：{value}")


def load_reference_catalog(
    csv_path: Path,
    *,
    project_root: Path,
) -> tuple[HeritageReferenceItem, ...]:
    """Read catalogue records and reject incomplete or untraceable rows."""
    if not csv_path.is_file():
        raise CatalogDataError(f"找不到非遗参考目录：{csv_path}")

    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = tuple(reader.fieldnames or ())
        missing_fields = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing_fields:
            raise CatalogDataError("heritage_products.csv 缺少字段：" + "、".join(missing_fields))

        items: list[HeritageReferenceItem] = []
        seen_ids: set[str] = set()
        seen_product_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            normalized = {field: (row.get(field) or "").strip() for field in REQUIRED_FIELDS}
            empty_fields = [field for field, value in normalized.items() if not value]
            if empty_fields:
                raise CatalogDataError(
                    f"heritage_products.csv 第 {row_number} 行存在空字段："
                    + "、".join(empty_fields)
                )

            catalog_id = normalized["catalog_product_id"]
            if catalog_id in seen_ids:
                raise CatalogDataError(f"heritage_products.csv 存在重复 ID：{catalog_id}")
            seen_ids.add(catalog_id)

            product_id = normalized["demo_product_id"]
            if product_id in seen_product_ids:
                raise CatalogDataError(f"heritage_products.csv 存在重复商品关联：{product_id}")
            if not product_id.startswith("prod_"):
                raise CatalogDataError(
                    f"heritage_products.csv 第 {row_number} 行的 demo_product_id 格式非法"
                )
            seen_product_ids.add(product_id)

            _validate_https_url(
                normalized["source_url"],
                row_number=row_number,
                field_name="source_url",
            )
            _validate_https_url(
                normalized["image_source_url"],
                row_number=row_number,
                field_name="image_source_url",
            )
            _validate_image_path(
                normalized["image_path"],
                row_number=row_number,
                project_root=project_root,
            )
            items.append(HeritageReferenceItem(**normalized))

    if not items:
        raise CatalogDataError("heritage_products.csv 没有可用记录")
    return tuple(items)
