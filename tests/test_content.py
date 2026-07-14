from __future__ import annotations

from pathlib import Path

import pandas as pd

from heritagelink.content import PENDING_EN, PENDING_ZH, generate_bilingual_content
from heritagelink.data_loader import build_products, load_data

ROOT = Path(__file__).parents[1]


def test_bilingual_content_uses_stored_facts_without_unknown_claims() -> None:
    bundle = load_data(ROOT / "data" / "demo")
    product = build_products(bundle)[0]
    content = generate_bilingual_content(product, bundle.product_texts)
    source_rows = bundle.product_texts[bundle.product_texts["product_id"] == product.product_id]

    for _, row in source_rows.iterrows():
        rendered = content.zh.text if row["locale"] == "zh-CN" else content.en.text
        for field in ("craft_summary", "cultural_story", "meaning_summary", "source_note"):
            assert row[field] in rendered
    forbidden_unknown_claims = ("国家级认证", "百年传承", "政府指定", "收藏价值保证")
    combined = f"{content.zh.text}\n{content.en.text}"
    assert not any(claim in combined for claim in forbidden_unknown_claims)


def test_missing_content_is_marked_pending_confirmation() -> None:
    bundle = load_data(ROOT / "data" / "demo")
    product = build_products(bundle)[0]
    incomplete = pd.DataFrame(
        [
            {
                "product_id": product.product_id,
                "locale": "zh-CN",
                "craft_summary": "",
                "review_status": "draft",
            }
        ]
    )

    content = generate_bilingual_content(product, incomplete)

    assert PENDING_ZH in content.zh.text
    assert PENDING_EN in content.en.text
    assert content.pending_confirmations
