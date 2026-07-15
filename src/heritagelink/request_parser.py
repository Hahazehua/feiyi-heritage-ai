"""Validated natural-language parsing with a deterministic local fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any, Literal
from uuid import uuid4

from heritagelink.inquiry import InquiryDetails
from heritagelink.llm_client import DeepSeekClient, LLMClientError
from heritagelink.models import GiftRequest

ParserMode = Literal["deepseek", "deterministic_demo"]
ParsePreference = Literal["auto", "deepseek", "deterministic_demo"]

BUDGET_TYPES = ("per_item", "total")
CUSTOMER_TYPES = ("corporate", "institution", "individual", "overseas")
OUTPUT_LANGUAGES = ("zh", "en", "bilingual")
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
CUSTOMIZATION_TYPES = frozenset(
    {"inscription", "pattern", "size", "packaging", "color", "logo", "other"}
)
REQUEST_FIELDS = (
    "customer_type",
    "budget_type",
    "total_budget",
    "budget_per_item",
    "quantity",
    "recipient",
    "scene",
    "style_preferences",
    "symbolism_preferences",
    "customization_required",
    "customization_types",
    "logo_required",
    "international_shipping_required",
    "destination",
    "required_delivery_days",
    "output_language",
    "requested_theme",
    "requested_text",
    "packaging_requirement",
    "additional_notes",
)
META_FIELDS = ("uncertain_fields", "missing_fields", "clarification_questions")
ALLOWED_PAYLOAD_FIELDS = frozenset((*REQUEST_FIELDS, *META_FIELDS))


class RequestValidationError(ValueError):
    """Raised when extracted data cannot safely enter business logic."""


@dataclass(frozen=True, slots=True)
class ParsedCustomerRequest:
    """One locally validated parse that still requires explicit user confirmation."""

    customer_type: str | None
    budget_type: str | None
    total_budget: float | None
    budget_per_item: float | None
    quantity: int | None
    recipient: str | None
    scene: str | None
    style_preferences: tuple[str, ...]
    symbolism_preferences: tuple[str, ...]
    customization_required: bool | None
    customization_types: tuple[str, ...]
    logo_required: bool | None
    international_shipping_required: bool | None
    destination: str | None
    required_delivery_days: int | None
    output_language: str | None
    requested_theme: str | None
    requested_text: str | None
    packaging_requirement: str | None
    additional_notes: str | None
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
    """Parse text with DeepSeek or the explicitly labelled deterministic fallback."""
    cleaned = text.strip()
    if not cleaned:
        raise RequestValidationError("礼品需求描述不能为空。")
    if len(cleaned) > 3000:
        raise RequestValidationError("礼品需求描述不能超过 3000 个字符。")
    if mode not in {"auto", "deepseek", "deterministic_demo"}:
        raise RequestValidationError(f"不支持的解析模式：{mode}")
    if mode == "deterministic_demo":
        return demo_parse_request(cleaned)

    try:
        active_client = client or DeepSeekClient.from_env()
        payload = active_client.extract_request(cleaned)
    except LLMClientError as exc:
        return replace(demo_parse_request(cleaned), parser_notice=str(exc))
    try:
        return validate_parsed_payload(payload, raw_user_text=cleaned, parser_mode="deepseek")
    except RequestValidationError:
        return replace(
            demo_parse_request(cleaned),
            parser_notice="AI 解析结果未通过本地校验，已切换到演示解析模式。",
        )


def validate_parsed_payload(
    payload: dict[str, Any],
    *,
    raw_user_text: str,
    parser_mode: ParserMode = "deepseek",
) -> ParsedCustomerRequest:
    """Validate and normalize untrusted parser JSON before any business conversion."""
    if not isinstance(payload, dict):
        raise RequestValidationError("解析结果必须是 JSON 对象。")
    if not raw_user_text.strip() or len(raw_user_text) > 3000:
        raise RequestValidationError("原始需求文本为空或过长。")
    unknown = sorted(set(payload) - ALLOWED_PAYLOAD_FIELDS)
    if unknown:
        raise RequestValidationError(f"解析结果包含未知字段：{', '.join(unknown)}")

    strings = {
        name: _optional_string(payload.get(name), name)
        for name in (
            "customer_type",
            "budget_type",
            "recipient",
            "scene",
            "destination",
            "output_language",
            "requested_theme",
            "requested_text",
            "packaging_requirement",
            "additional_notes",
        )
    }
    _validate_controlled_value(strings["customer_type"], frozenset(CUSTOMER_TYPES), "customer_type")
    _validate_controlled_value(strings["budget_type"], frozenset(BUDGET_TYPES), "budget_type")
    _validate_controlled_value(strings["recipient"], RECIPIENT_TAGS, "recipient")
    _validate_controlled_value(strings["scene"], SCENE_TAGS, "scene")
    _validate_controlled_value(
        strings["output_language"], frozenset(OUTPUT_LANGUAGES), "output_language"
    )

    total_budget = _optional_positive_money(payload.get("total_budget"), "total_budget")
    budget_per_item = _optional_positive_money(payload.get("budget_per_item"), "budget_per_item")
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
    styles = _string_tuple(payload.get("style_preferences", []), "style_preferences")
    meanings = _string_tuple(payload.get("symbolism_preferences", []), "symbolism_preferences")
    customization_types = _string_tuple(
        payload.get("customization_types", []), "customization_types"
    )
    _validate_controlled_list(styles, STYLE_TAGS, "style_preferences")
    _validate_controlled_list(meanings, SYMBOLISM_TAGS, "symbolism_preferences")
    _validate_controlled_list(customization_types, CUSTOMIZATION_TYPES, "customization_types")

    if logo is True and "logo" not in customization_types:
        customization_types = (*customization_types, "logo")
    if strings["requested_text"] and "inscription" not in customization_types:
        customization_types = (*customization_types, "inscription")
    if strings["packaging_requirement"] and "packaging" not in customization_types:
        customization_types = (*customization_types, "packaging")
    customization_types = _stable_unique(customization_types)
    if logo is True or customization_types:
        if customization is False:
            raise RequestValidationError("存在定制内容时 customization_required 不能为 false。")
        customization = True

    budget_per_item = _normalize_budget(
        strings["budget_type"], total_budget, budget_per_item, quantity
    )

    supplied_missing = _string_tuple(payload.get("missing_fields", []), "missing_fields")
    uncertain = _string_tuple(payload.get("uncertain_fields", []), "uncertain_fields")
    questions = _string_tuple(payload.get("clarification_questions", []), "clarification_questions")
    _validate_field_references(supplied_missing, "missing_fields")
    _validate_field_references(uncertain, "uncertain_fields")

    normalized: dict[str, Any] = {
        **strings,
        "total_budget": total_budget,
        "budget_per_item": budget_per_item,
        "quantity": quantity,
        "style_preferences": styles,
        "symbolism_preferences": meanings,
        "customization_required": customization,
        "customization_types": customization_types,
        "logo_required": logo,
        "international_shipping_required": international,
        "required_delivery_days": delivery,
    }
    computed_missing = []
    for name in REQUEST_FIELDS:
        if _is_missing_value(normalized.get(name)):
            computed_missing.append(name)
    if strings["budget_type"] == "per_item":
        computed_missing = [name for name in computed_missing if name != "total_budget"]
    if customization is False:
        computed_missing = [name for name in computed_missing if name != "customization_types"]
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
    """Extract a bounded set of explicit Chinese facts using deterministic rules."""
    payload: dict[str, Any] = {name: None for name in REQUEST_FIELDS}
    payload["style_preferences"] = []
    payload["symbolism_preferences"] = []
    payload["customization_types"] = []
    uncertain: list[str] = []
    questions: list[str] = []

    quantity_match = re.search(r"(\d+)\s*(?:位|人|份|件|套|个)(?!元)", text)
    if quantity_match:
        payload["quantity"] = int(quantity_match.group(1))

    total_match = re.search(r"总预算(?:为|是|约|大约)?\s*(\d+(?:\.\d+)?)\s*(万)?元", text)
    per_item_match = re.search(
        r"(?:每(?:件|份)|单件)\s*(?:预算(?:为|是)?\s*)?(\d+(?:\.\d+)?)\s*元",
        text,
    )
    if total_match:
        payload["budget_type"] = "total"
        multiplier = 10000 if total_match.group(2) else 1
        payload["total_budget"] = float(total_match.group(1)) * multiplier
    elif per_item_match:
        payload["budget_type"] = "per_item"
        payload["budget_per_item"] = float(per_item_match.group(1))
    if (total_match or per_item_match) and re.search(r"左右|大约|约|上下", text):
        field = "total_budget" if total_match else "budget_per_item"
        uncertain.append(field)
        questions.append("请确认该金额是否为不可超过的预算上限？")

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

    if re.search(r"企业采购|企业礼品|企业给|公司(?:想|要|计划)采购", text):
        payload["customer_type"] = "corporate"
    elif re.search(r"政府|高校|博物馆|文化机构", text):
        payload["customer_type"] = "institution"
    elif re.search(r"个人|我自己", text):
        payload["customer_type"] = "individual"

    if re.search(r"美国|United States|\bUSA\b", text, re.IGNORECASE):
        payload["destination"] = "United States"
        payload["international_shipping_required"] = True
    elif re.search(r"中国大陆|国内", text):
        payload["destination"] = "中国大陆"
        payload["international_shipping_required"] = False
    elif re.search(r"不需要(?:国际|海外)运输", text):
        payload["international_shipping_required"] = False

    no_logo = bool(re.search(r"不(?:需要|加|加入).{0,4}logo", text, re.IGNORECASE))
    logo_requested = not no_logo and bool(
        re.search(r"(?:加|加入|印|放).{0,6}logo", text, re.IGNORECASE)
    )
    custom_requested = logo_requested or bool(re.search(r"定制|题字|刻字", text))
    if custom_requested:
        payload["customization_required"] = True
    elif re.search(r"不需要定制", text):
        payload["customization_required"] = False
    if logo_requested:
        payload["logo_required"] = True
        payload["customization_types"].append("logo")
    elif no_logo:
        payload["logo_required"] = False

    if re.search(r"中英文|中英双语|双语", text):
        payload["output_language"] = "bilingual"
    elif "英文" in text or re.search(r"\bEnglish\b", text, re.IGNORECASE):
        payload["output_language"] = "en"
    elif "中文" in text:
        payload["output_language"] = "zh"

    text_match = re.search(r"(?:题字|刻字)[为是：:]?\s*[“\"]([^”\"]+)[”\"]", text)
    if text_match:
        payload["requested_text"] = text_match.group(1).strip()
        payload["customization_types"].append("inscription")
    packaging_match = re.search(r"([^，。；;]{1,30}(?:包装|礼盒))", text)
    if packaging_match:
        payload["packaging_requirement"] = packaging_match.group(1).strip()
        payload["customization_types"].append("packaging")
    notes_match = re.search(r"(?:备注|其他要求)[：:]\s*([^。；;]+)", text)
    if notes_match:
        payload["additional_notes"] = notes_match.group(1).strip()

    payload["uncertain_fields"] = uncertain
    payload["missing_fields"] = []
    payload["clarification_questions"] = questions
    result = validate_parsed_payload(payload, raw_user_text=text, parser_mode="deterministic_demo")
    return replace(
        result,
        parser_notice="当前使用确定性演示解析模式，结果不是 DeepSeek 输出。",
    )


def to_business_request(
    parsed: ParsedCustomerRequest,
) -> tuple[GiftRequest, InquiryDetails]:
    """Convert a user-confirmed parse into the unchanged recommendation contract."""
    required = {
        "budget_type": parsed.budget_type,
        "budget_per_item": parsed.budget_per_item,
        "quantity": parsed.quantity,
        "recipient": parsed.recipient,
        "scene": parsed.scene,
    }
    missing = [name for name, value in required.items() if _is_missing_value(value)]
    if missing:
        raise RequestValidationError(f"开始推荐前请补充：{', '.join(missing)}")
    assert parsed.budget_per_item is not None
    assert parsed.quantity is not None
    assert parsed.recipient is not None
    assert parsed.scene is not None
    required_types = set(parsed.customization_types) - {"logo"}
    request = GiftRequest(
        request_id=f"req_nlp_{uuid4().hex[:12]}",
        unit_budget_max_fen=_yuan_to_fen(parsed.budget_per_item),
        quantity=parsed.quantity,
        recipient_tags=frozenset({parsed.recipient}),
        occasion_tags=frozenset({parsed.scene}),
        style_tags=frozenset(parsed.style_preferences),
        meaning_tags=frozenset(parsed.symbolism_preferences),
        customization_required=bool(parsed.customization_required),
        required_customization_types=frozenset(required_types),
        logo_required=bool(parsed.logo_required),
        international_shipping_required=bool(parsed.international_shipping_required),
        available_lead_days=parsed.required_delivery_days,
    )
    return request, to_inquiry_details(parsed)


def to_inquiry_details(parsed: ParsedCustomerRequest) -> InquiryDetails:
    """Build non-ranking inquiry details even when procurement fields are incomplete."""
    return InquiryDetails(
        customer_type=parsed.customer_type or "待商家确认",
        customization_theme=parsed.requested_theme or "",
        inscription_text=parsed.requested_text or "",
        packaging_requirement=parsed.packaging_requirement or "",
        destination=parsed.destination or "",
        output_language={"zh": "中文", "en": "English", "bilingual": "中英双语"}.get(
            parsed.output_language or "", "待商家确认"
        ),
        additional_notes=parsed.additional_notes or "",
    )


def _normalize_budget(
    budget_type: str | None,
    total_budget: float | None,
    budget_per_item: float | None,
    quantity: int | None,
) -> float | None:
    if budget_type == "total":
        if total_budget is None or quantity is None:
            return budget_per_item
        calculated = (_money_decimal(total_budget) / quantity).quantize(
            Decimal("0.01"), rounding=ROUND_FLOOR
        )
        if budget_per_item is not None:
            difference = abs(_money_decimal(budget_per_item) - calculated)
            if difference > Decimal("0.01"):
                raise RequestValidationError("总预算、数量与单件预算换算不一致。")
        return float(calculated)
    if budget_type == "per_item" and budget_per_item is not None:
        if total_budget is not None and quantity is not None:
            expected_total = _money_decimal(budget_per_item) * quantity
            if abs(_money_decimal(total_budget) - expected_total) > Decimal("0.01"):
                raise RequestValidationError("总预算与单件预算乘采购数量不一致。")
        return budget_per_item
    return budget_per_item


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestValidationError(f"{field_name} 必须是字符串或 null。")
    cleaned = value.strip()
    if len(cleaned) > 500:
        raise RequestValidationError(f"{field_name} 不能超过 500 个字符。")
    return cleaned or None


def _optional_positive_money(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestValidationError(f"{field_name} 必须是正数或 null。")
    decimal_value = _money_decimal(value)
    if decimal_value <= 0:
        raise RequestValidationError(f"{field_name} 必须是正数或 null。")
    return float(decimal_value)


def _money_decimal(value: int | float) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise RequestValidationError("金额格式非法。") from exc
    if not decimal_value.is_finite():
        raise RequestValidationError("金额必须是有限数值。")
    return decimal_value


def _yuan_to_fen(value: float) -> int:
    return int((_money_decimal(value) * 100).to_integral_value(rounding=ROUND_FLOOR))


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
    return _stable_unique(tuple(item.strip() for item in value))


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
