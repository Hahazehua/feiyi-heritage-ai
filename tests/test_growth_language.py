"""The campaign language has to reach the copy, not just the prompt.

The live-AI path passed the requested language to the model, but the
deterministic path — which is the default generation mode — built its output
from hardcoded English. Selecting 简体中文 changed nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heritagelink.data_loader import build_products, load_data
from heritagelink.growth_grounding import build_catalog_growth_context
from heritagelink.growth_models import GrowthOutputSource, GrowthRunRequest
from heritagelink.growth_orchestrator import run_growth_workflow
from heritagelink.growth_phrases import EN, ZH, is_bilingual, phrases_for
from heritagelink.heritage_passport import build_catalog_passports

ROOT = Path(__file__).parents[1]


def _campaign(language: str):  # type: ignore[no-untyped-def]
    bundle = load_data(ROOT / "data" / "demo")
    products = build_products(bundle)
    passports = build_catalog_passports(products, bundle)
    product = products[0]
    context = build_catalog_growth_context(product, passports[product.product_id])
    request = GrowthRunRequest(
        artisan_id=context.artisan_id,
        product_id=product.product_id,
        campaign_goal="overseas corporate anniversary gifting",
        target_geography="United States",
        optional_target_audience="",
        preferred_channels=("LinkedIn",),
        language=language,
        output_source=GrowthOutputSource.DETERMINISTIC_DEMO,
    )
    _state, campaign = run_growth_workflow(request, context)
    return campaign


def _has_han(text: str) -> bool:
    return any("一" <= character <= "鿿" for character in text)


def test_every_phrase_exists_on_both_sides() -> None:
    """A missing entry would surface as English inside Chinese output."""
    for field in ZH.__dataclass_fields__:
        assert getattr(ZH, field), f"ZH.{field} is empty"
        assert getattr(EN, field), f"EN.{field} is empty"
        assert getattr(ZH, field) != getattr(EN, field), f"{field} was never translated"


def test_chinese_campaign_is_written_in_chinese() -> None:
    campaign = _campaign("Chinese")

    assert campaign.market_analysis.recommended_segment == ZH.segment_corporate
    assert campaign.strategy.cta == ZH.cta
    assert _has_han(campaign.market_analysis.summary)
    assert _has_han(campaign.assets[0].content)
    # The give-away from before the fix.
    assert "Request verified product" not in campaign.assets[0].content


def test_english_campaign_is_written_in_english() -> None:
    campaign = _campaign("English")

    assert campaign.market_analysis.recommended_segment == EN.segment_corporate
    assert campaign.strategy.cta == EN.cta
    assert not _has_han(campaign.market_analysis.summary)


def test_english_copy_uses_the_english_product_name() -> None:
    """Naming the item in Chinese inside English copy reads half-translated."""
    campaign = _campaign("English")
    content = campaign.assets[0].content

    assert "Heritage-Inspired" in content, content[:160]


def test_bilingual_carries_both_languages() -> None:
    campaign = _campaign("Bilingual")
    content = campaign.assets[0].content

    assert _has_han(content)
    assert "Looking for a more meaningful approach" in content


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Chinese", ZH), ("中文", ZH), ("Bilingual", ZH), ("English", EN), ("", EN), (None, EN)],
)
def test_language_resolution(value: str | None, expected: object) -> None:
    assert phrases_for(value) is expected


def test_bilingual_is_recognised_separately() -> None:
    assert is_bilingual("Bilingual")
    assert not is_bilingual("Chinese")
    assert not is_bilingual("English")


def test_audiences_follow_the_localized_segment_names() -> None:
    """Segment names double as identifiers, so they must resolve per language."""
    assert _campaign("Chinese").strategy.target_audience == ZH.audience_corporate
    assert _campaign("English").strategy.target_audience == EN.audience_corporate
