"""Template-only bilingual culture content built from reviewed data fields."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from heritagelink.models import Product, ProductSummary

PENDING_ZH = "待商家确认"
PENDING_EN = "Pending merchant confirmation"


@dataclass(frozen=True, slots=True)
class LocalizedContent:
    """One locale of product content plus provenance and pending markers."""

    locale: str
    text: str
    craft_summary: str
    cultural_story: str
    meaning_summary: str
    source_note: str
    review_status: str
    pending_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BilingualContent:
    """Chinese and English content generated without inventing product facts."""

    product_id: str
    zh: LocalizedContent
    en: LocalizedContent
    pending_confirmations: tuple[str, ...]


def _field_value(row: pd.Series | None, field: str, pending_text: str) -> tuple[str, bool]:
    if row is None or field not in row.index:
        return pending_text, True
    value = str(row[field]).strip()
    if not value:
        return pending_text, True
    return value, False


def _localized_content(
    product: Product | ProductSummary,
    product_texts: pd.DataFrame,
    locale: str,
) -> LocalizedContent:
    rows = product_texts[
        (product_texts.get("product_id") == product.product_id)
        & (product_texts.get("locale") == locale)
    ]
    row = rows.iloc[0] if not rows.empty else None
    is_zh = locale == "zh-CN"
    pending_text = PENDING_ZH if is_zh else PENDING_EN
    pending_fields: list[str] = []
    values: dict[str, str] = {}
    for field in ("craft_summary", "cultural_story", "meaning_summary", "source_note"):
        value, missing = _field_value(row, field, pending_text)
        values[field] = value
        if missing:
            pending_fields.append(field)

    review_status, missing_review = _field_value(row, "review_status", pending_text)
    if missing_review:
        pending_fields.append("review_status")
    if is_zh:
        review_line = (
            "演示文案，待商家审核" if review_status != "approved" else "已标记为商家审核通过"
        )
        text = "\n".join(
            (
                f"{product.product_name_zh}",
                f"工艺说明：{values['craft_summary']}",
                f"文化介绍：{values['cultural_story']}",
                f"文化寓意：{values['meaning_summary']}",
                f"资料说明：{values['source_note']}",
                f"审核状态：{review_line}",
            )
        )
    else:
        review_line = (
            "MVP demo copy pending merchant review"
            if review_status != "approved"
            else "Marked as approved by the merchant"
        )
        text = "\n".join(
            (
                f"{product.product_name_en}",
                f"Craft: {values['craft_summary']}",
                f"Cultural introduction: {values['cultural_story']}",
                f"Meaning: {values['meaning_summary']}",
                f"Source note: {values['source_note']}",
                f"Review status: {review_line}",
            )
        )
    return LocalizedContent(
        locale=locale,
        text=text,
        craft_summary=values["craft_summary"],
        cultural_story=values["cultural_story"],
        meaning_summary=values["meaning_summary"],
        source_note=values["source_note"],
        review_status=review_status,
        pending_fields=tuple(pending_fields),
    )


def generate_bilingual_content(
    product: Product | ProductSummary,
    product_texts: pd.DataFrame,
) -> BilingualContent:
    """Render bilingual copy using only product names and stored content fields."""
    required_columns = {"product_id", "locale"}
    if not required_columns.issubset(product_texts.columns):
        product_texts = pd.DataFrame(columns=sorted(required_columns))
    zh = _localized_content(product, product_texts, "zh-CN")
    en = _localized_content(product, product_texts, "en")
    pending = tuple(
        sorted(
            {f"zh-CN.{field}" for field in zh.pending_fields}
            | {f"en.{field}" for field in en.pending_fields}
        )
    )
    return BilingualContent(
        product_id=product.product_id,
        zh=zh,
        en=en,
        pending_confirmations=pending,
    )
