from __future__ import annotations

import pytest

from heritagelink.data_loader import build_products, load_data
from heritagelink.llm_client import LLMTimeoutError
from heritagelink.recommender import recommend
from heritagelink.request_parser import (
    RequestValidationError,
    demo_parse_request,
    parse_request,
    to_business_request,
    validate_parsed_payload,
)

EXAMPLE = (
    "我想给30位美国合作伙伴准备周年纪念礼物，每件预算1000元左右，"
    "希望体现安徽文化，可以加公司Logo，30天内完成，需要中英文介绍。"
)


class TimeoutClient:
    def extract_request(self, text: str) -> dict[str, object]:
        raise LLMTimeoutError("请求超时")


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_type": None,
        "recipient": "business_partner",
        "budget_per_item": 1000,
        "quantity": 30,
        "scene": "anniversary",
        "style_preferences": [],
        "symbolism_preferences": ["heritage"],
        "customization_required": True,
        "logo_required": True,
        "destination_country": "United States",
        "international_shipping_required": True,
        "required_delivery_days": 30,
        "output_language": "中英双语",
        "requested_theme": "安徽文化",
        "requested_text": None,
        "packaging_requirement": None,
        "uncertain_fields": ["budget_per_item"],
        "missing_fields": ["customer_type", "requested_text", "packaging_requirement"],
        "clarification_questions": ["1000元是预算上限吗？"],
    }
    payload.update(overrides)
    return payload


def test_chinese_demo_parser_extracts_budget_quantity_and_delivery() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.budget_per_item == 1000
    assert parsed.quantity == 30
    assert parsed.required_delivery_days == 30


def test_parser_recognizes_us_and_international_shipping() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.destination_country == "United States"
    assert parsed.international_shipping_required is True


def test_parser_recognizes_customization_and_logo() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.customization_required is True
    assert parsed.logo_required is True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("需要中文介绍", "中文"),
        ("需要英文介绍", "English"),
        ("需要中英文介绍", "中英双语"),
    ],
)
def test_parser_recognizes_output_language(text: str, expected: str) -> None:
    assert demo_parse_request(text).output_language == expected


def test_missing_fields_are_computed_locally() -> None:
    parsed = demo_parse_request("想准备一批礼物")

    assert "budget_per_item" in parsed.missing_fields
    assert "quantity" in parsed.missing_fields
    assert "required_delivery_days" in parsed.missing_fields


def test_approximate_budget_is_uncertain_and_asks_question() -> None:
    parsed = demo_parse_request("每件预算1000元左右")

    assert "budget_per_item" in parsed.uncertain_fields
    assert parsed.clarification_questions


def test_valid_json_converts_to_customer_request() -> None:
    parsed = validate_parsed_payload(_valid_payload(), raw_user_text=EXAMPLE)
    request, details = to_business_request(parsed)

    assert request.unit_budget_max_fen == 100000
    assert request.quantity == 30
    assert request.logo_required is True
    assert request.international_shipping_required is True
    assert details.destination == "United States"


@pytest.mark.parametrize(
    "overrides",
    [
        {"budget_per_item": -1},
        {"quantity": 1.5},
        {"required_delivery_days": 0},
        {"logo_required": "true"},
        {"style_preferences": "modern"},
        {"output_language": "法语"},
        {"unexpected_business_rule": True},
    ],
)
def test_invalid_payload_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(RequestValidationError):
        validate_parsed_payload(_valid_payload(**overrides), raw_user_text=EXAMPLE)


def test_no_api_key_uses_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    parsed = parse_request(EXAMPLE, mode="auto")

    assert parsed.parser_mode == "demo"
    assert "演示解析模式" in parsed.parser_notice


def test_timeout_safely_falls_back_to_demo_mode() -> None:
    parsed = parse_request(EXAMPLE, client=TimeoutClient())  # type: ignore[arg-type]

    assert parsed.parser_mode == "demo"
    assert "请求超时" in parsed.parser_notice


def test_parser_cannot_bypass_recommender_hard_budget_filter() -> None:
    payload = _valid_payload(budget_per_item=1)
    parsed = validate_parsed_payload(payload, raw_user_text="单件预算1元")
    request, _ = to_business_request(parsed)
    products = build_products(load_data("data/demo"))

    response = recommend(products, request)

    assert not response.has_eligible_products


def test_missing_hard_filter_input_cannot_start_recommendation() -> None:
    parsed = validate_parsed_payload(
        _valid_payload(required_delivery_days=None), raw_user_text=EXAMPLE
    )

    with pytest.raises(RequestValidationError, match="required_delivery_days"):
        to_business_request(parsed)
