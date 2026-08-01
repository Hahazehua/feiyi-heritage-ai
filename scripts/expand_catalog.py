"""Build the 50-item, source-traceable Wave 3 catalogue from the Met Open Access API.

The 30 added records are museum catalogue references, not sale listings. Their
commercial fields are deliberately labelled demo_assumption and the records are
inactive so they cannot enter formal recommendation results.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).parents[1]
DEMO = ROOT / "data" / "demo"
CATALOG = ROOT / "data" / "catalog"
IMAGE_DIR = ROOT / "assets" / "catalog" / "products"
ACCESSED_AT = "2026-07-30"
VERSION = "2026-07-30.1"
MET_API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"
MET_PAGE = "https://www.metmuseum.org/art/collection/search/{}"

PRICE_BANDS = (
    (20_000, 30_000, "entry"),
    (50_000, 80_000, "mid"),
    (120_000, 180_000, "business"),
    (300_000, 450_000, "high"),
    (600_000, 800_000, "collector"),
)

CATEGORIES = {
    "fan": {
        "heritage_id": "heritage_ref_fan",
        "zh": "传统折扇与纸艺馆藏参考",
        "en": "Chinese folding fan references",
        "region": "中国（全国性文化语境）",
        "culture_url": "https://ich.unesco.org/en/RL/chinese-calligraphy-00216",
        "recipients": ["friend", "teacher", "overseas_partner"],
        "scenes": ["academic_visit", "conference_gift", "festival"],
        "styles": ["elegant", "literati", "portable"],
        "meanings": ["friendship", "wisdom", "landscape"],
    },
    "seal": {
        "heritage_id": "heritage_ref_seal",
        "zh": "中国印章艺术馆藏参考",
        "en": "Chinese seal art references",
        "region": "浙江（印章艺术文化语境）",
        "culture_url": "https://ich.unesco.org/en/RL/art-of-chinese-seal-engraving-00217",
        "recipients": ["collector", "teacher", "institution"],
        "scenes": ["collection", "honor_commemoration", "academic_visit"],
        "styles": ["traditional", "literati", "collectible"],
        "meanings": ["heritage", "wisdom", "remembrance"],
    },
    "bamboo": {
        "heritage_id": "heritage_ref_bamboo",
        "zh": "竹木文房器物馆藏参考",
        "en": "Bamboo scholar-object references",
        "region": "中国（馆藏记录未细分）",
        "culture_url": "",
        "recipients": ["teacher", "business_partner", "institution"],
        "scenes": ["business_gift", "academic_visit", "home_display"],
        "styles": ["natural", "literati", "traditional"],
        "meanings": ["resilience", "wisdom", "career"],
    },
    "tea": {
        "heritage_id": "heritage_ref_tea",
        "zh": "传统茶生活器物馆藏参考",
        "en": "Traditional tea-lifestyle references",
        "region": "中国（多地茶文化语境）",
        "culture_url": "https://ich.unesco.org/en/RL/traditional-tea-processing-techniques-and-associated-social-practices-in-china-01884?RL=01884",
        "recipients": ["elder", "overseas_partner", "business_partner"],
        "scenes": ["business_gift", "foreign_exchange", "housewarming"],
        "styles": ["elegant", "natural", "modern_chinese"],
        "meanings": ["harmony", "friendship", "blessing"],
    },
    "woodblock": {
        "heritage_id": "heritage_ref_woodblock",
        "zh": "雕版印刷与版画馆藏参考",
        "en": "Chinese woodblock-print references",
        "region": "中国（雕版印刷文化语境）",
        "culture_url": "https://ich.unesco.org/en/RL/china-engraved-block-printing-technique-00229",
        "recipients": ["overseas_partner", "teacher", "institution"],
        "scenes": ["foreign_exchange", "conference_gift", "collection"],
        "styles": ["regional", "literati", "collectible"],
        "meanings": ["heritage", "wisdom", "home_culture"],
    },
    "calligraphy": {
        "heritage_id": "heritage_ref_calligraphy",
        "zh": "中国书法馆藏参考",
        "en": "Chinese calligraphy references",
        "region": "中国（书法文化语境）",
        "culture_url": "https://ich.unesco.org/en/RL/chinese-calligraphy-00216",
        "recipients": ["teacher", "institution", "collector"],
        "scenes": ["academic_visit", "honor_commemoration", "collection"],
        "styles": ["literati", "elegant", "collectible"],
        "meanings": ["wisdom", "heritage", "career"],
    },
}

OBJECTS = (
    (41482, "fan", "鱼网纹折扇"),
    (51770, "fan", "折扇"),
    (51536, "fan", "折扇册页"),
    (35990, "fan", "青崖红枫图折扇"),
    (36000, "fan", "江景图折扇"),
    (40995, "seal", "青玉印"),
    (41006, "seal", "灰玉印"),
    (41055, "seal", "鲍文玉印"),
    (41002, "seal", "玉印"),
    (61857, "seal", "青花釉下彩印"),
    (76453, "bamboo", "仙人山水纹竹笔筒"),
    (42158, "bamboo", "《醉翁亭记》图竹笔筒"),
    (39625, "bamboo", "《醉翁亭记》图竹笔筒（早期）"),
    (39626, "bamboo", "山水高士图香筒"),
    (39855, "bamboo", "文会图竹笔筒"),
    (47879, "tea", "茶壶"),
    (46792, "tea", "牡丹纹双面茶壶"),
    (51184, "tea", "莲花形茶壶"),
    (42323, "tea", "梅花形茶壶"),
    (460687, "tea", "茶壶与托碟"),
    (712497, "woodblock", "《水浒传》插图本"),
    (60764, "woodblock", "《太平府山水》图册"),
    (63375, "woodblock", "《十竹斋画谱》册页"),
    (63372, "woodblock", "《十竹斋画谱》单页"),
    (912945, "woodblock", "内贴《姑苏冬日美人图》木箱"),
    (35993, "calligraphy", "书法折扇册页"),
    (65628, "calligraphy", "为茂叔作书画册"),
    (49029, "calligraphy", "清凉山题诗"),
    (65630, "calligraphy", "隶书格言"),
    (51784, "calligraphy", "“福”字书法"),
)

TEA_REGIONS = ("福建", "浙江", "广西", "云南", "四川")


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames or ()), list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_json(url: str) -> dict[str, Any]:
    response = requests.get(url, headers={"User-Agent": "HeritageLink-Wave3/1.0"}, timeout=45)
    response.raise_for_status()
    return response.json()


def download(url: str, path: Path) -> None:
    response = requests.get(url, headers={"User-Agent": "HeritageLink-Wave3/1.0"}, timeout=90)
    response.raise_for_status()
    path.write_bytes(response.content)


def tier_for(price_fen: int) -> str:
    yuan = price_fen / 100
    if yuan <= 300:
        return "entry"
    if yuan <= 800:
        return "mid"
    if yuan <= 2_000:
        return "business"
    if yuan <= 5_000:
        return "high"
    return "collector"


def normalize_existing_products(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    heritage_category = {
        "heritage_demo_lacquer": "lacquer",
        "heritage_demo_longquan": "ceramics",
        "heritage_demo_textile": "textile",
        "heritage_demo_jade": "jade",
    }
    for row in rows:
        price = int(row["price_min_fen"])
        row.update(
            category_code=heritage_category[row["heritage_id"]],
            region_code="中国（馆藏文化参考）",
            price_tier=tier_for(price),
            source_product_url=row["reference_source_url"],
            source_culture_url=row["reference_source_url"],
            source_merchant_url="",
            source_type="museum_open_collection",
            source_accessed_at="2026-07-17",
            source_status="source_verified",
            verification_status="reference_verified_commercial_unverified",
            merchant_fact_status="pending_verification",
            commercial_data_status="demo_assumption",
            cultural_data_status="verified_public_cultural_fact",
            image_status="open_access_local_copy",
            image_attribution="The Metropolitan Museum of Art, Open Access",
            data_quality_level="C",
            catalog_role="recommendation_demo",
        )
    return rows


def main(*, refresh_images: bool) -> None:
    product_fields, product_rows = read_rows(DEMO / "products.csv")
    product_rows = [row for row in product_rows if not row["product_id"].startswith("prod_ref_")]
    product_rows = normalize_existing_products(product_rows)
    new_product_fields = [
        "category_code",
        "region_code",
        "price_tier",
        "source_product_url",
        "source_culture_url",
        "source_merchant_url",
        "source_type",
        "source_accessed_at",
        "source_status",
        "verification_status",
        "merchant_fact_status",
        "commercial_data_status",
        "cultural_data_status",
        "image_status",
        "image_attribution",
        "data_quality_level",
        "catalog_role",
    ]
    for field in new_product_fields:
        if field not in product_fields:
            insert_at = product_fields.index("recipient_tags")
            product_fields.insert(insert_at, field)

    heritage_fields, heritage_rows = read_rows(DEMO / "heritage_items.csv")
    heritage_rows = [
        row for row in heritage_rows if not row["heritage_id"].startswith("heritage_ref_")
    ]
    for code, category in CATEGORIES.items():
        heritage_rows.append(
            {
                "heritage_id": category["heritage_id"],
                "heritage_name_zh": category["zh"],
                "heritage_name_en": category["en"],
                "category_code": code,
                "region": category["region"],
                "official_level": "unverified",
                "verification_note": (
                    "馆藏与公共文化资料分类；不声明具体商品、商家或代表性项目资质。"
                ),
                "status": "active",
                "data_version": VERSION,
                "is_demo": "true",
            }
        )

    text_fields, text_rows = read_rows(DEMO / "product_texts.csv")
    text_rows = [row for row in text_rows if not row["product_id"].startswith("prod_ref_")]
    catalog_fields, catalog_rows = read_rows(CATALOG / "heritage_products.csv")
    catalog_rows = [
        row for row in catalog_rows if not row["demo_product_id"].startswith("prod_ref_")
    ]
    source_rows: list[dict[str, str]] = []
    research_rows: list[dict[str, str]] = []
    new_ids: set[str] = set()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for index, (object_id, category_code, name_zh) in enumerate(OBJECTS, start=1):
        obj = fetch_json(MET_API.format(object_id))
        if not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
            raise RuntimeError(f"Met object {object_id} is not a public-domain item with an image")
        product_id = f"prod_ref_{index:03d}"
        new_ids.add(product_id)
        category = CATEGORIES[category_code]
        price_min, price_max, price_tier = PRICE_BANDS[(index - 1) % len(PRICE_BANDS)]
        region = category["region"]
        if category_code == "tea":
            region = f"{TEA_REGIONS[(index - 16) % 5]}（茶文化语境，非器物产地声明）"
        image_path = f"assets/catalog/products/met-{object_id}.jpg"
        image_file = ROOT / image_path
        if refresh_images or not image_file.exists():
            download(str(obj["primaryImageSmall"]), image_file)
        object_url = str(obj.get("objectURL") or MET_PAGE.format(object_id))
        culture_url = str(category["culture_url"] or object_url)
        medium = str(obj.get("medium") or "Museum record: medium not provided")
        dimensions = str(obj.get("dimensions") or "Museum record: dimensions not provided")
        title_en = str(obj.get("title") or obj.get("objectName") or f"Met object {object_id}")
        date = str(obj.get("objectDate") or "Date not specified in museum record")
        accession = str(obj.get("accessionNumber") or object_id)
        product_rows.append(
            {
                "product_id": product_id,
                "merchant_id": "mer_demo_feiyi",
                "heritage_id": category["heritage_id"],
                "sku": f"REF-MET-{object_id}",
                "product_name_zh": f"馆藏参考｜{name_zh}",
                "product_name_en": f"Museum reference | {title_en}",
                "price_min_fen": price_min,
                "price_max_fen": price_max,
                "min_order_qty": 1,
                "recommended_max_qty": "",
                "demo_max_order_qty": "",
                "lead_time_days": 30,
                "dimensions_text": dimensions,
                "material_text": medium,
                "image_path": image_path,
                "image_alt_zh": f"大都会艺术博物馆开放馆藏：{name_zh}",
                "reference_source_url": object_url,
                "image_license": "CC0 1.0 / Public Domain",
                "category_code": category_code,
                "region_code": region,
                "price_tier": price_tier,
                "source_product_url": object_url,
                "source_culture_url": culture_url,
                "source_merchant_url": "",
                "source_type": "museum_open_collection",
                "source_accessed_at": ACCESSED_AT,
                "source_status": "source_verified",
                "verification_status": "catalog_reference_only",
                "merchant_fact_status": "pending_verification",
                "commercial_data_status": "demo_assumption",
                "cultural_data_status": "verified_public_cultural_fact",
                "image_status": "open_access_local_copy",
                "image_attribution": "The Metropolitan Museum of Art, Open Access",
                "data_quality_level": "C",
                "catalog_role": "catalog_reference",
                "recipient_tags": json.dumps(category["recipients"], ensure_ascii=False),
                "occasion_tags": json.dumps(category["scenes"], ensure_ascii=False),
                "style_tags": json.dumps(category["styles"], ensure_ascii=False),
                "meaning_tags": json.dumps(category["meanings"], ensure_ascii=False),
                "supports_international_shipping": "false",
                "shipping_note": "馆藏参考，不是销售商品；运输、价格、产能和交付均待真实商家确认。",
                "status": "inactive",
                "data_version": VERSION,
                "is_demo": "true",
                "demo_disclaimer": "MVP演示数据｜馆藏参考，不可下单且不参与正式推荐",
            }
        )
        cultural_note_zh = (
            "文化背景仅按所列官方来源概括；馆藏对象与当代商品、商家及商业能力之间不作归属推断。"
        )
        cultural_note_en = (
            "Cultural context is limited to the cited official source; no link to a current "
            "merchant, sale product, or fulfilment capability is asserted."
        )
        text_rows.extend(
            (
                {
                    "product_id": product_id,
                    "locale": "zh-CN",
                    "craft_summary": (
                        f"大都会艺术博物馆将该对象记录为“{name_zh}”相关馆藏；材质记录为：{medium}。"
                    ),
                    "cultural_story": f"馆藏年代记录：{date}。{cultural_note_zh}",
                    "meaning_summary": (
                        "可用于礼赠方向的文化探索，但寓意标签是策展索引，不是馆方或商家承诺。"
                    ),
                    "source_note": (
                        f"The Met Open Access，馆藏编号 {accession}；"
                        f"访问日期 {ACCESSED_AT}；{object_url}"
                    ),
                    "review_status": "draft",
                    "reviewed_at": "",
                    "is_demo": "true",
                },
                {
                    "product_id": product_id,
                    "locale": "en",
                    "craft_summary": (
                        f"The Met records this object as “{title_en}”; "
                        f"its medium is recorded as: {medium}."
                    ),
                    "cultural_story": f"Museum date: {date}. {cultural_note_en}",
                    "meaning_summary": (
                        "Suitable for gift-direction exploration; symbolism tags are curatorial "
                        "indexes, not museum or merchant claims."
                    ),
                    "source_note": (
                        f"The Met Open Access, accession {accession}; accessed {ACCESSED_AT}; "
                        f"{object_url}"
                    ),
                    "review_status": "draft",
                    "reviewed_at": "",
                    "is_demo": "true",
                },
            )
        )
        catalog_rows.append(
            {
                "catalog_product_id": f"CAT-REF-{index:03d}",
                "demo_product_id": product_id,
                "source_object_id": object_id,
                "product_name_zh": name_zh,
                "product_name_en": title_en,
                "craft_category_zh": category["zh"],
                "craft_category_en": category["en"],
                "period_text": date,
                "region_text": str(obj.get("culture") or obj.get("country") or "China"),
                "material_text": medium,
                "dimensions_text": dimensions,
                "introduction_zh": (
                    f"大都会艺术博物馆开放馆藏对象，仅作为{category['zh']}与视觉参考，"
                    "不是在售商品。"
                ),
                "introduction_en": (
                    "An Open Access Met collection object used only as a "
                    f"{category['en']} and visual reference; it is not a sale listing."
                ),
                "image_path": image_path,
                "source_url": object_url,
                "image_source_url": str(obj["primaryImageSmall"]),
                "source_name": "The Metropolitan Museum of Art",
                "source_object_number": accession,
                "image_license": "CC0 1.0 / Public Domain",
                "commercial_status": "catalog_reference_not_for_sale",
                "verification_status": f"source_verified_{ACCESSED_AT}",
            }
        )
        source_rows.extend(
            (
                {
                    "source_id": f"SRC-MET-{object_id}",
                    "product_id": product_id,
                    "source_url": object_url,
                    "source_title": title_en,
                    "source_type": "museum_open_collection",
                    "publisher": "The Metropolitan Museum of Art",
                    "accessed_at": ACCESSED_AT,
                    "trust_level": "high",
                    "facts_supported": (
                        "title; date; medium; dimensions; accession; public-domain image"
                    ),
                    "fact_status": "verified_public_cultural_fact",
                },
                {
                    "source_id": f"SRC-CULT-{index:03d}",
                    "product_id": product_id,
                    "source_url": culture_url,
                    "source_title": f"Official cultural context for {category['en']}",
                    "source_type": "official_cultural_source",
                    "publisher": "UNESCO or The Metropolitan Museum of Art",
                    "accessed_at": ACCESSED_AT,
                    "trust_level": "high",
                    "facts_supported": "cultural context only; not merchant or commercial facts",
                    "fact_status": "verified_public_cultural_fact",
                },
            )
        )
        research_rows.append(
            {
                "research_id": f"RES-{index:03d}",
                "product_id": product_id,
                "researched_query": f"Met Open Access object {object_id}",
                "source_url": object_url,
                "source_title": title_en,
                "source_type": "museum_open_collection",
                "accessed_at": ACCESSED_AT,
                "facts_used": "title; date; medium; dimensions; image; accession",
                "facts_not_used": "merchant; price; stock; lead time; customization; shipping",
                "trust_notes": "Official museum API and object page; CC0 image flag checked.",
                "reviewer_status": "source_checked_catalog_reference",
            }
        )

    option_fields, option_rows = read_rows(DEMO / "customization_options.csv")
    if "commercial_data_status" not in option_fields:
        option_fields.append("commercial_data_status")
    for row in option_rows:
        row["commercial_data_status"] = "demo_assumption"
    option_rows = [
        row
        for row in option_rows
        if row["customization_option_id"] not in {"custopt_demo_006_size", "custopt_demo_006_color"}
    ]
    option_rows.append(
        {
            "customization_option_id": "custopt_demo_006_color",
            "product_id": "prod_demo_006",
            "customization_type": "color",
            "description_zh": ("仅作为配色方案评估入口；可用颜色、价格和交期必须由真实商家确认。"),
            "description_en": (
                "Demo colour assessment only; available colours, price, and lead time require "
                "merchant confirmation."
            ),
            "price_impact": "required_quote",
            "extra_lead_days": "7",
            "enabled": "true",
            "is_demo": "true",
            "demo_disclaimer": "MVP演示数据",
            "commercial_data_status": "demo_assumption",
        }
    )

    write_rows(DEMO / "products.csv", product_fields, product_rows)
    write_rows(DEMO / "heritage_items.csv", heritage_fields, heritage_rows)
    write_rows(DEMO / "product_texts.csv", text_fields, text_rows)
    write_rows(DEMO / "customization_options.csv", option_fields, option_rows)
    write_rows(CATALOG / "heritage_products.csv", catalog_fields, catalog_rows)

    all_sources: list[dict[str, str]] = []
    for row in product_rows[:20]:
        all_sources.append(
            {
                "source_id": f"SRC-EXISTING-{row['product_id']}",
                "product_id": row["product_id"],
                "source_url": row["source_product_url"],
                "source_title": "The Met collection object",
                "source_type": row["source_type"],
                "publisher": "The Metropolitan Museum of Art",
                "accessed_at": row["source_accessed_at"],
                "trust_level": "high",
                "facts_supported": "museum object and open-access image; not commercial fields",
                "fact_status": "verified_public_cultural_fact",
            }
        )
    all_sources.extend(source_rows)
    source_fields = [
        "source_id",
        "product_id",
        "source_url",
        "source_title",
        "source_type",
        "publisher",
        "accessed_at",
        "trust_level",
        "facts_supported",
        "fact_status",
    ]
    write_rows(CATALOG / "source_registry.csv", source_fields, all_sources)
    research_fields = [
        "research_id",
        "product_id",
        "researched_query",
        "source_url",
        "source_title",
        "source_type",
        "accessed_at",
        "facts_used",
        "facts_not_used",
        "trust_notes",
        "reviewer_status",
    ]
    write_rows(CATALOG / "research_log.csv", research_fields, research_rows)

    option_map: dict[str, list[str]] = {}
    for row in option_rows:
        if row["enabled"].lower() == "true":
            option_map.setdefault(row["product_id"], []).append(row["customization_type"])
    coverage_rows = []
    for row in product_rows:
        coverage_rows.append(
            {
                "product_id": row["product_id"],
                "category": row["category_code"],
                "region": row["region_code"],
                "price_tier": row["price_tier"],
                "recipients": row["recipient_tags"],
                "scenes": row["occasion_tags"],
                "styles": row["style_tags"],
                "symbolism": row["meaning_tags"],
                "customization_types": json.dumps(option_map.get(row["product_id"], [])),
                "portability": "unknown"
                if row["catalog_role"] == "catalog_reference"
                else "demo_assumption",
                "international_relevance": "unknown"
                if row["catalog_role"] == "catalog_reference"
                else "demo_assumption",
                "data_quality_level": row["data_quality_level"],
            }
        )
    coverage_fields = [
        "product_id",
        "category",
        "region",
        "price_tier",
        "recipients",
        "scenes",
        "styles",
        "symbolism",
        "customization_types",
        "portability",
        "international_relevance",
        "data_quality_level",
    ]
    write_rows(CATALOG / "coverage_matrix.csv", coverage_fields, coverage_rows)
    if len(product_rows) != 50 or len(catalog_rows) != 50:
        raise RuntimeError(
            f"Expected 50 products/catalogue rows, got {len(product_rows)}/{len(catalog_rows)}"
        )
    print(f"Built {len(product_rows)} products and {len(catalog_rows)} catalogue records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-images", action="store_true")
    args = parser.parse_args()
    main(refresh_images=args.refresh_images)
