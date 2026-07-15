"""Validated natural-language parsing with a deterministic local fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import uuid4

from heritagelink.inquiry import InquiryDetails
from heritagelink.llm_client import DeepSeekClient, LLMClientError
from heritagelink.models import GiftRequest

ParserMode = Literal["deepseek", "demo"]
ParsePreference = Literal["auto", "deepseek", "demo"]

OUTPUT_LANGUAGES = ("中文", "English", "中英双语")
RECIPIENT_TAGS = frozenset(
    {
        "business_partner",
        "institution",
        "employee",
        "elder",
        "family",
        "friend",
        "newlywed",
        "teacher",
        "collector",
    }
)
SCENE_TAGS = frozenset(
    {
        "business_gift",
        "commemoration",
        "wedding",
        "anniversary",
        "housewarming",
        "birthday",
        "festival",
        "graduation",
        "appreciation",
        "collection",
        "exhibition",
    }
)
STYLE_TAGS = frozenset({"traditional", "modern", "minimal", "grand", "elegant", "festive", "warm"})
SYMBOLISM_TAGS = frozenset(
    {
        "heritage",
        "prosperity",
        "blessing",
        "harmony",
        "longevity",
        "resilience",
        "remembrance",
        "gratitude",
        "union",
    }
)
REQUEST_FIELDS = (
    "customer_type",
    "recipient",
    "budget_per_item",
    "quantity",
    "scene",
    "style_preferences",
    "symbolism_preferences",
    "customization_required",
    "logo_required",
    "destination_country",
    "international_shipping_required",
    "required_delivery_days",
    "output_language",
    "requested_theme",
    "requested_text",
    "packaging_requirement",
)
META_FIELDS = ("uncertain_fields", "missing_fields", "clarification_questions")
ALLOWED_PAYLOAD_FIELDS = frozenset((*REQUEST_FIELDS, *META_FIELDS))


class RequestValidationError(ValueError):
    """Raised when extracted data cannot safely enter business logic."""


@dataclass(frozen=True, slots=True)
class ParsedCustomerRequest:
    """Locally validated extraction result that still requires user confirmation."""

    customer_type: str | None
    recipient: str | None
    budget_per_item: float | None
    quantity: int | None
    scene: str | None
    style_preferences: tuple[str, ...]
    symbolism_preferences: tuple[str, ...]
    customization_required: bool | None
    logo_required: bool | None
    destination_country: str | None
    international_shipping_required: bool | None
    required_delivery_days: int | None
    output_language: str | None
    requested_theme: str | None
    requested_text: str | None
    packaging_requirement: str | None
    uncertain_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    clarification_questions: tuple[str, ...]
    parser_mode: ParserMode
    raw_user_text: str
    parser_notice: str = ""


def parse_request(
    text: str,
    *,
    mode: ParsePreference = "auto",
    client: DeepSeekClient | None = None,
) -> ParsedCustomerRequest:
    """Parse text using DeepSeek when available, otherwise use transparent demo rules."""
    cleaned = text.strip()
    if not cleaned:
        raise RequestValidationError("礼品需求描述不能为空。")
    if len(cleaned) > 3000:
        raise RequestValidationError("礼品需求描述不能超过 3000 个字符。")
    if mode not in {"auto", "deepseek", "demo"}:
        raise RequestValidationError(f"不支持的解析模式：{mode}")
    if mode == "demo":
        return demo_parse_request(cleaned)

    try:
        active_client = client or DeepSeekClient.from_env()
        payload = active_client.extract_request(cleaned)
        return validate_parsed_payload(payload, raw_user_text=cleaned, parser_mode="deepseek")
    except LLMClientError as exc:
        fallback = demo_parse_request(cleaned)
        return replace(fallback, parser_notice=str(exc))


def validate_parsed_payload(
    payload: dict[str, Any],
    *,
    raw_user_text: str,
    parser_mode: ParserMode = "deepseek",
) -> ParsedCustomerRequest:
    """Strictly validate model JSON; unknown fields are rejected, never silently used."""
    if not isinstance(payload, dict):
        raise RequestValidationError("解析结果必须是 JSON 对象。")
    unknown = sorted(set(payload) - ALLOWED_PAYLOAD_FIELDS)
    if unknown:
        raise RequestValidationError(f"解析结果包含未知字段：{', '.join(unknown)}")

    strings = {
        name: _optional_string(payload.get(name), name)
        for name in (
            "customer_type",
            "recipient",
            "scene",
            "destination_country",
            "requested_theme",
            "requested_text",
            "packaging_requirement",
        )
    }
    budget = _optional_positive_number(payload.get("budget_per_item"), "budget_per_item")
    quantity = _optional_positive_int(payload.get("quantity"), "quantity")
    delivery = _optional_positive_int(
        payload.get("required_delivery_days"), "required_delivery_days"
    )
    customization = _optional_bool(payload.get("customization_required"), "customization_required")
    logo = _optional_bool(payload.get("logo_required"), "logo_required")
    international = _optional_bool(
        payload.get("international_shipping_required"),
        "international_shipping_required",
    )
    output_language = _optional_string(payload.get("output_language"), "output_language")
    if output_language is not None and output_language not in OUTPUT_LANGUAGES:
        raise RequestValidationError(
            f"output_language 必须是以下选项之一：{', '.join(OUTPUT_LANGUAGES)}"
        )

    styles = _string_tuple(payload.get("style_preferences", []), "style_preferences")
    meanings = _string_tuple(payload.get("symbolism_preferences", []), "symbolism_preferences")
    _validate_controlled_value(strings["recipient"], RECIPIENT_TAGS, "recipient")
    _validate_controlled_value(strings["scene"], SCENE_TAGS, "scene")
    _validate_controlled_list(styles, STYLE_TAGS, "style_preferences")
    _validate_controlled_list(meanings, SYMBOLISM_TAGS, "symbolism_preferences")
    supplied_missing = _string_tuple(payload.get("missing_fields", []), "missing_fields")
    uncertain = _string_tuple(payload.get("uncertain_fields", []), "uncertain_fields")
    questions = _string_tuple(payload.get("clarification_questions", []), "clarification_questions")
    _validate_field_references(supplied_missing, "missing_fields")
    _validate_field_references(uncertain, "uncertain_fields")

    normalized: dict[str, Any] = {
        **strings,
        "budget_per_item": budget,
        "quantity": quantity,
        "style_preferences": styles,
        "symbolism_preferences": meanings,
        "customization_required": customization,
        "logo_required": logo,
        "international_shipping_required": international,
        "required_delivery_days": delivery,
        "output_language": output_language,
    }
    computed_missing = tuple(
        name for name in REQUEST_FIELDS if _is_missing_value(normalized.get(name))
    )
    missing = _stable_unique((*supplied_missing, *computed_missing))
    return ParsedCustomerRequest(
        **normalized,
        uncertain_fields=_stable_unique(uncertain),
        missing_fields=missing,
        clarification_questions=_stable_unique(questions),
        parser_mode=parser_mode,
        raw_user_text=raw_user_text,
    )


def demo_parse_request(text: str) -> ParsedCustomerRequest:
    """Extract only a small set of explicit facts using deterministic local rules."""
    payload: dict[str, Any] = {name: None for name in REQUEST_FIELDS}
    payload["style_preferences"] = []
    payload["symbolism_preferences"] = []
    uncertain: list[str] = []
    questions: list[str] = []

    budget_match = re.search(
        r"(?:每(?:件|份)|单件)?\s*(?:预算)?\s*(\d+(?:\.\d+)?)\s*(?:元|人民币)", text
    )
    if budget_match:
        payload["budget_per_item"] = float(budget_match.group(1))
        if re.search(r"左右|大约|约|上下", text):
            uncertain.append("budget_per_item")
            questions.append("请确认该金额是否为不可超过的单件预算上限？")

    quantity_match = re.search(r"(\d+)\s*(?:位|人|份|件|套|个)(?!元)", text)
    if quantity_match:
        payload["quantity"] = int(quantity_match.group(1))
    delivery_match = re.search(r"(\d+)\s*天(?:内|以内|完成|交付|送达)", text)
    if delivery_match:
        payload["required_delivery_days"] = int(delivery_match.group(1))

    _first_mapping(
        text,
        payload,
        "recipient",
        {
            "合作伙伴": "business_partner",
            "客户": "business_partner",
            "员工": "employee",
            "长辈": "elder",
            "家人": "family",
            "朋友": "friend",
            "新人": "newlywed",
            "教师": "teacher",
            "老师": "teacher",
            "收藏家": "collector",
            "机构": "institution",
        },
    )
    _first_mapping(
        text,
        payload,
        "scene",
        {
            "商务礼": "business_gift",
            "周年": "anniversary",
            "纪念": "commemoration",
            "婚礼": "wedding",
            "乔迁": "housewarming",
            "生日": "birthday",
            "节庆": "festival",
            "毕业": "graduation",
            "答谢": "appreciation",
            "收藏": "collection",
            "展览": "exhibition",
        },
    )
    for keyword, tag in {
        "传统": "traditional",
        "现代": "modern",
        "简约": "minimal",
        "大气": "grand",
        "典雅": "elegant",
        "喜庆": "festive",
        "温暖": "warm",
    }.items():
        if keyword in text:
            payload["style_preferences"].append(tag)
    for keyword, tag in {
        "安徽文化": "heritage",
        "文化传承": "heritage",
        "繁荣": "prosperity",
        "祝福": "blessing",
        "和谐": "harmony",
        "长寿": "longevity",
        "坚韧": "resilience",
        "纪念": "remembrance",
        "感谢": "gratitude",
        "相伴": "union",
    }.items():
        if keyword in text:
            payload["symbolism_preferences"].append(tag)
    if "安徽文化" in text:
        payload["requested_theme"] = "安徽文化"

    if re.search(r"企业采购|企业礼品|我们公司(?:想|要|计划)采购", text):
        payload["customer_type"] = "企业客户"
    elif re.search(r"政府|高校|博物馆|文化机构", text):
        payload["customer_type"] = "政府/高校/文化机构"
    elif re.search(r"个人|我自己", text):
        payload["customer_type"] = "个人客户"

    if re.search(r"美国|United States|\bUSA\b", text, re.IGNORECASE):
        payload["destination_country"] = "United States"
        payload["international_shipping_required"] = True
    elif re.search(r"中国大陆|国内", text):
        payload["destination_country"] = "中国大陆"
        payload["international_shipping_required"] = False

    logo_requested = bool(re.search(r"(?:加|加入|印|放).{0,6}logo", text, re.IGNORECASE))
    custom_requested = logo_requested or bool(re.search(r"定制|题字|刻字", text))
    if custom_requested:
        payload["customization_required"] = True
    if logo_requested:
        payload["logo_required"] = True

    if re.search(r"中英文|中英双语|双语", text):
        payload["output_language"] = "中英双语"
    elif "英文" in text or re.search(r"\bEnglish\b", text, re.IGNORECASE):
        payload["output_language"] = "English"
    elif "中文" in text:
        payload["output_language"] = "中文"

    text_match = re.search(r"(?:题字|刻字)[为是：:]?\s*[“\"]([^”\"]+)[”\"]", text)
    if text_match:
        payload["requested_text"] = text_match.group(1).strip()
    packaging_match = re.search(r"([^，。；;]{1,30}(?:包装|礼盒))", text)
    if packaging_match:
        payload["packaging_requirement"] = packaging_match.group(1).strip()

    payload["uncertain_fields"] = uncertain
    payload["missing_fields"] = []
    payload["clarification_questions"] = questions
    result = validate_parsed_payload(payload, raw_user_text=text, parser_mode="demo")
    return replace(result, parser_notice="当前使用确定性演示解析模式，结果不是 DeepSeek 输出。")


def to_business_request(
    parsed: ParsedCustomerRequest,
) -> tuple[GiftRequest, InquiryDetails]:
    """Convert a user-confirmed parse into the unchanged recommendation contract."""
    required = {
        "budget_per_item": parsed.budget_per_item,
        "quantity": parsed.quantity,
        "recipient": parsed.recipient,
        "scene": parsed.scene,
        "customization_required": parsed.customization_required,
        "logo_required": parsed.logo_required,
        "international_shipping_required": parsed.international_shipping_required,
        "required_delivery_days": parsed.required_delivery_days,
    }
    missing = [name for name, value in required.items() if _is_missing_value(value)]
    if missing:
        raise RequestValidationError(f"开始推荐前请补充：{', '.join(missing)}")
    assert parsed.budget_per_item is not None
    assert parsed.quantity is not None
    assert parsed.recipient is not None
    assert parsed.scene is not None
    required_types = {"inscription"} if parsed.requested_text else set()
    preferred_types = {"packaging"} if parsed.packaging_requirement else set()
    request = GiftRequest(
        request_id=f"req_nlp_{uuid4().hex[:12]}",
        unit_budget_max_fen=round(parsed.budget_per_item * 100),
        quantity=parsed.quantity,
        recipient_tags=frozenset({parsed.recipient}),
        occasion_tags=frozenset({parsed.scene}),
        style_tags=frozenset(parsed.style_preferences),
        meaning_tags=frozenset(parsed.symbolism_preferences),
        customization_required=bool(parsed.customization_required),
        required_customization_types=frozenset(required_types),
        preferred_customization_types=frozenset(preferred_types),
        logo_required=bool(parsed.logo_required),
        international_shipping_required=bool(parsed.international_shipping_required),
        available_lead_days=parsed.required_delivery_days,
    )
    details = InquiryDetails(
        customer_type=parsed.customer_type or "待商家确认",
        customization_theme=parsed.requested_theme or "",
        inscription_text=parsed.requested_text or "",
        packaging_requirement=parsed.packaging_requirement or "",
        destination=parsed.destination_country or "",
        output_language=parsed.output_language or "待商家确认",
    )
    return request, details


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestValidationError(f"{field_name} 必须是字符串或 null。")
    cleaned = value.strip()
    return cleaned or None


def _optional_positive_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise RequestValidationError(f"{field_name} 必须是正数或 null。")
    return float(value)


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RequestValidationError(f"{field_name} 必须是正整数或 null。")
    return value


def _optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise RequestValidationError(f"{field_name} 必须是真正的布尔值或 null。")
    return value


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RequestValidationError(f"{field_name} 必须是字符串列表。")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise RequestValidationError(f"{field_name} 必须只包含非空字符串。")
    return tuple(item.strip() for item in value)


def _validate_field_references(values: tuple[str, ...], field_name: str) -> None:
    invalid = sorted(set(values) - set(REQUEST_FIELDS))
    if invalid:
        raise RequestValidationError(f"{field_name} 引用了未知字段：{', '.join(invalid)}")


def _validate_controlled_value(value: str | None, allowed: frozenset[str], field_name: str) -> None:
    if value is not None and value not in allowed:
        raise RequestValidationError(f"{field_name} 包含不受支持的值：{value}")


def _validate_controlled_list(
    values: tuple[str, ...], allowed: frozenset[str], field_name: str
) -> None:
    invalid = sorted(set(values) - allowed)
    if invalid:
        raise RequestValidationError(f"{field_name} 包含不受支持的值：{', '.join(invalid)}")


def _is_missing_value(value: Any) -> bool:
    return value is None or value == "" or value == () or value == []


def _stable_unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _first_mapping(
    text: str,
    payload: dict[str, Any],
    field_name: str,
    mapping: dict[str, str],
) -> None:
    for keyword, value in mapping.items():
        if keyword in text:
            payload[field_name] = value
            return
