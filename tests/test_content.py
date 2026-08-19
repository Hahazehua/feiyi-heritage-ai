from __future__ import annotations

import re
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


def test_english_source_notes_are_localized_and_keep_provenance() -> None:
    bundle = load_data(ROOT / "data" / "demo")
    english_rows = bundle.product_texts[bundle.product_texts["locale"] == "en"]

    assert len(english_rows) == 54
    # Museum-backed rows cite the Met; partner work cites the craft registry
    # instead, because there is no museum record to point at.
    museum_rows = english_rows[~english_rows["product_id"].str.startswith("prod_wuhu")]
    assert all("https://www.metmuseum.org/" in note for note in museum_rows["source_note"])
    partner_rows = english_rows[english_rows["product_id"].str.startswith("prod_wuhu")]
    assert all("ihchina.cn" in note for note in partner_rows["source_note"])
    assert all(not re.search(r"[\u4e00-\u9fff]", note) for note in english_rows["source_note"])
