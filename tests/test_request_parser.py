from __future__ import annotations

from pathlib import Path

import pytest

from heritagelink.data_loader import build_products, load_data
from heritagelink.llm_client import LLMTimeoutError
from heritagelink.models import FilterReasonCode
from heritagelink.recommender import recommend
from heritagelink.request_parser import (
    RequestValidationError,
    demo_parse_request,
    parse_request,
    to_business_request,
    validate_parsed_payload,
)

ROOT = Path(__file__).parents[1]
EXAMPLE = (
    "我们想给30位美国合作伙伴准备周年纪念礼物，每件预算1000元左右，"
    "希望体现安徽文化，可以加入公司Logo，30天内完成，需要中英文介绍。"
)


class TimeoutClient:
    def extract_request(self, text: str) -> dict[str, object]:
        raise LLMTimeoutError("请求超时")


class SuccessClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    def extract_request(self, text: str) -> dict[str, object]:
        self.calls += 1
        return self.payload


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_type": "corporate",
        "budget_type": "per_item",
        "total_budget": None,
        "budget_per_item": 1000,
        "quantity": 30,
        "recipient": "business_partner",
        "scene": "anniversary",
        "style_preferences": [],
        "symbolism_preferences": ["heritage"],
        "customization_required": True,
        "customization_types": ["logo"],
        "logo_required": True,
        "international_shipping_required": True,
        "destination": "United States",
        "required_delivery_days": 30,
        "output_language": "bilingual",
        "requested_theme": "安徽文化",
        "requested_text": None,
        "packaging_requirement": None,
        "additional_notes": None,
        "uncertain_fields": [],
        "missing_fields": ["requested_text", "packaging_requirement", "additional_notes"],
        "clarification_questions": [],
    }
    payload.update(overrides)
    return payload


def test_chinese_demo_parser_extracts_budget_quantity_and_delivery() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.budget_type == "per_item"
    assert parsed.budget_per_item == 1000
    assert parsed.quantity == 30
    assert parsed.required_delivery_days == 30


def test_total_budget_is_converted_to_per_item_and_preserved() -> None:
    parsed = demo_parse_request("总预算3万元，共30件，送给合作伙伴")

    assert parsed.budget_type == "total"
    assert parsed.total_budget == 30000
    assert parsed.budget_per_item == 1000
    assert parsed.quantity == 30


def test_inconsistent_total_and_per_item_budget_is_rejected() -> None:
    with pytest.raises(RequestValidationError, match="换算不一致"):
        validate_parsed_payload(
            _valid_payload(
                budget_type="total", total_budget=30000, budget_per_item=999, quantity=30
            ),
            raw_user_text="总预算3万元，30件，每件999元",
        )


def test_parser_recognizes_us_and_international_shipping() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.destination == "United States"
    assert parsed.international_shipping_required is True


def test_parser_recognizes_customization_and_logo() -> None:
    parsed = demo_parse_request(EXAMPLE)

    assert parsed.customization_required is True
    assert parsed.logo_required is True
    assert "logo" in parsed.customization_types


@pytest.mark.parametrize(
    ("text", "expected_required", "forbidden_type"),
    [
        ("不需要定制", False, None),
        ("不需要题字", None, "inscription"),
        ("不需要刻字", None, "inscription"),
        ("不需要定制包装", False, "packaging"),
    ],
)
def test_demo_parser_does_not_turn_negated_customization_into_a_requirement(
    text: str, expected_required: bool | None, forbidden_type: str | None
) -> None:
    parsed = demo_parse_request(text)

    assert parsed.customization_required is expected_required
    if forbidden_type is not None:
        assert forbidden_type not in parsed.customization_types


def test_demo_parser_preserves_supported_customization_types() -> None:
    parsed = demo_parse_request("需要图案定制、尺寸定制和颜色定制")

    assert parsed.customization_required is True
    assert set(parsed.customization_types) == {"pattern", "size", "color"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [("需要中文介绍", "zh"), ("需要英文介绍", "en"), ("需要中英文介绍", "bilingual")],
)
def test_parser_recognizes_output_language(text: str, expected: str) -> None:
    assert demo_parse_request(text).output_language == expected


def test_unstated_fields_are_not_invented() -> None:
    parsed = demo_parse_request("给30位合作伙伴准备礼物，每件1000元")

    assert parsed.style_preferences == ()
    assert parsed.packaging_requirement is None
    assert parsed.required_delivery_days is None
    assert "style_preferences" in parsed.missing_fields
    assert "packaging_requirement" in parsed.missing_fields


def test_missing_fields_are_computed_locally() -> None:
    parsed = demo_parse_request("想准备一批礼物")

    assert "budget_type" in parsed.missing_fields
    assert "budget_per_item" in parsed.missing_fields
    assert "quantity" in parsed.missing_fields


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


def test_uncertain_fields_cannot_enter_confirmed_business_request() -> None:
    parsed = validate_parsed_payload(
        _valid_payload(uncertain_fields=["quantity"]), raw_user_text=EXAMPLE
    )

    with pytest.raises(RequestValidationError, match="quantity"):
        to_business_request(parsed)


def test_mock_deepseek_success_path_uses_validated_result() -> None:
    client = SuccessClient(_valid_payload())

    parsed = parse_request(EXAMPLE, mode="deepseek", client=client)  # type: ignore[arg-type]

    assert parsed.parser_mode == "deepseek"
    assert parsed.quantity == 30
    assert client.calls == 1


def test_invalid_mock_deepseek_payload_safely_falls_back() -> None:
    client = SuccessClient({"unknown_field": "must not affect business"})

    parsed = parse_request(EXAMPLE, mode="deepseek", client=client)  # type: ignore[arg-type]

    assert parsed.parser_mode == "deterministic_demo"
    assert "未通过本地校验" in parsed.parser_notice


@pytest.mark.parametrize(
    "overrides",
    [
        {"budget_per_item": -1},
        {"quantity": 1.5},
        {"required_delivery_days": 0},
        {"logo_required": "true"},
        {"style_preferences": "modern"},
        {"output_language": "fr"},
        {"unexpected_business_rule": True},
    ],
)
def test_invalid_payload_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(RequestValidationError):
        validate_parsed_payload(_valid_payload(**overrides), raw_user_text=EXAMPLE)


def test_no_api_key_uses_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")

    parsed = parse_request(EXAMPLE, mode="auto")

    assert parsed.parser_mode == "deterministic_demo"
    assert "演示解析模式" in parsed.parser_notice


def test_timeout_safely_falls_back_to_demo_mode() -> None:
    parsed = parse_request(EXAMPLE, client=TimeoutClient())  # type: ignore[arg-type]

    assert parsed.parser_mode == "deterministic_demo"
    assert "请求超时" in parsed.parser_notice


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"budget_per_item": 1}, FilterReasonCode.OVER_BUDGET),
        ({"quantity": 500}, FilterReasonCode.ABOVE_MAX_ORDER),
        ({"required_delivery_days": 1}, FilterReasonCode.LEAD_TIME_INSUFFICIENT),
    ],
)
def test_parsed_request_cannot_bypass_global_hard_filters(
    overrides: dict[str, object], reason: FilterReasonCode
) -> None:
    parsed = validate_parsed_payload(_valid_payload(**overrides), raw_user_text=EXAMPLE)
    request, _ = to_business_request(parsed)
    response = recommend(build_products(load_data(ROOT / "data" / "demo")), request)

    assert not response.has_eligible_products
    assert all(reason in failure.reason_codes for failure in response.filter_failures)


def test_parsed_logo_and_shipping_requirements_remain_hard_filters() -> None:
    parsed = validate_parsed_payload(_valid_payload(), raw_user_text=EXAMPLE)
    request, _ = to_business_request(parsed)
    response = recommend(build_products(load_data(ROOT / "data" / "demo")), request)
    failures = {failure.product_id: failure.reason_codes for failure in response.filter_failures}

    assert FilterReasonCode.LOGO_UNSUPPORTED in failures["prod_demo_002"]
    assert FilterReasonCode.INTERNATIONAL_SHIPPING_UNSUPPORTED in failures["prod_demo_004"]


def test_missing_core_input_cannot_start_recommendation() -> None:
    parsed = validate_parsed_payload(_valid_payload(quantity=None), raw_user_text=EXAMPLE)

    with pytest.raises(RequestValidationError, match="quantity"):
        to_business_request(parsed)
