"""Reusable requirement forms and confirmation summaries."""

from __future__ import annotations

from typing import Any

import streamlit as st

from heritagelink.request_parser import (
    ParsedCustomerRequest,
    RequestValidationError,
    validate_parsed_payload,
)

CUSTOMER_TYPES = {
    "企业客户": "corporate",
    "政府/高校/文化机构": "institution",
    "个人客户": "individual",
    "海外客户": "overseas",
}
RECIPIENTS = {
    "商务伙伴": "business_partner",
    "机构客户": "institution",
    "员工": "employee",
    "长辈": "elder",
    "家人": "family",
    "朋友": "friend",
    "新婚夫妇": "newlywed",
    "教师": "teacher",
    "收藏者": "collector",
}
SCENES = {
    "商务礼赠": "business_gift",
    "机构纪念": "commemoration",
    "婚礼": "wedding",
    "周年纪念": "anniversary",
    "乔迁": "housewarming",
    "生日": "birthday",
    "节庆": "festival",
    "毕业": "graduation",
    "感谢答谢": "appreciation",
    "收藏": "collection",
    "展览展示": "exhibition",
}
STYLES = {
    "传统": "traditional",
    "现代": "modern",
    "简约": "minimal",
    "大气": "grand",
    "典雅": "elegant",
    "喜庆": "festive",
    "温暖": "warm",
}
MEANINGS = {
    "文化传承": "heritage",
    "繁荣兴盛": "prosperity",
    "祝福": "blessing",
    "和谐": "harmony",
    "长久": "longevity",
    "坚韧": "resilience",
    "纪念": "remembrance",
    "感谢": "gratitude",
    "相伴结合": "union",
}
OUTPUT_LANGUAGES = {"中文": "zh", "English": "en", "中英双语": "bilingual"}
CUSTOMIZATION_TYPES = {
    "题字": "inscription",
    "图案定制": "pattern",
    "尺寸定制": "size",
    "包装定制": "packaging",
    "颜色定制": "color",
    "其他定制": "other",
}

FIELD_DISPLAY = {
    "customer_type": "客户类型",
    "recipient": "送礼对象",
    "scene": "礼赠场景",
    "budget_per_item": "单件预算",
    "quantity": "采购数量",
    "style_preferences": "风格偏好",
    "symbolism_preferences": "文化偏好",
    "customization_required": "定制要求",
    "customization_types": "定制类型",
    "logo_required": "Logo",
    "destination": "目的地",
    "required_delivery_days": "交付周期",
    "output_language": "内容语言",
}


def _optional_float(value: str, field: str) -> float | None:
    if not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise RequestValidationError(f"{field}必须是有效数字。") from exc
    if number <= 0:
        raise RequestValidationError(f"{field}必须大于 0。")
    return number


def _optional_int(value: str, field: str) -> int | None:
    if not value.strip():
        return None
    try:
        number = int(value)
    except ValueError as exc:
        raise RequestValidationError(f"{field}必须是正整数。") from exc
    if number <= 0:
        raise RequestValidationError(f"{field}必须大于 0。")
    return number


def _bool_value(label: str) -> bool | None:
    return {"需要": True, "不需要": False, "未说明": None}[label]


def _bool_label(value: bool | None) -> str:
    return "需要" if value is True else "不需要" if value is False else "未说明"


def parsed_from_widgets(
    prefix: str, parsed: ParsedCustomerRequest | None = None
) -> ParsedCustomerRequest:
    """Validate the structured editor before it reaches recommendation logic."""
    raw = parsed.raw_user_text if parsed else "精准填写需求"
    budget = _optional_float(st.session_state[f"{prefix}_budget"], "单件预算")
    quantity = _optional_int(st.session_state[f"{prefix}_quantity"], "采购数量")
    delivery = _optional_int(st.session_state[f"{prefix}_delivery"], "交付天数")
    logo = _bool_value(st.session_state[f"{prefix}_logo"])
    customization = _bool_value(st.session_state[f"{prefix}_customization"])
    customization_types = [
        CUSTOMIZATION_TYPES[item] for item in st.session_state[f"{prefix}_customization_types"]
    ]
    international = _bool_value(st.session_state[f"{prefix}_international"])
    if logo:
        customization_types.append("logo")
    requested_text = st.session_state[f"{prefix}_text"].strip() or None
    packaging_note = st.session_state[f"{prefix}_packaging_note"].strip() or None
    if requested_text and "inscription" not in customization_types:
        customization_types.append("inscription")
    if packaging_note and "packaging" not in customization_types:
        customization_types.append("packaging")
    if customization is False and customization_types:
        raise RequestValidationError("已选择具体定制内容时，不能同时选择“不需要定制”。")
    customization_required = True if customization_types else customization
    destination = st.session_state[f"{prefix}_destination"].strip() or None
    customer_type = CUSTOMER_TYPES.get(st.session_state[f"{prefix}_customer_type"])
    recipient = RECIPIENTS.get(st.session_state[f"{prefix}_recipient"])
    scene = SCENES.get(st.session_state[f"{prefix}_scene"])
    payload: dict[str, Any] = {
        "customer_type": customer_type,
        "budget_type": "per_item" if budget is not None else None,
        "total_budget": None,
        "budget_per_item": budget,
        "quantity": quantity,
        "recipient": recipient,
        "scene": scene,
        "style_preferences": [STYLES[item] for item in st.session_state[f"{prefix}_styles"]],
        "symbolism_preferences": [
            MEANINGS[item] for item in st.session_state[f"{prefix}_meanings"]
        ],
        "customization_required": customization_required,
        "customization_types": customization_types,
        "logo_required": logo,
        "international_shipping_required": international,
        "destination": destination,
        "required_delivery_days": delivery,
        "output_language": OUTPUT_LANGUAGES.get(st.session_state[f"{prefix}_language"]),
        "requested_theme": st.session_state[f"{prefix}_theme"].strip() or None,
        "requested_text": requested_text,
        "packaging_requirement": packaging_note,
        "additional_notes": st.session_state[f"{prefix}_notes"].strip() or None,
        "uncertain_fields": [],
        "missing_fields": [],
        "clarification_questions": [],
    }
    return validate_parsed_payload(
        payload,
        raw_user_text=raw,
        parser_mode=parsed.parser_mode if parsed else "deterministic_demo",
    )


def render_structured_form(
    *, prefix: str, parsed: ParsedCustomerRequest | None = None, submit_label: str
) -> bool:
    """Render the grouped precise editor for initial input or confirmation."""

    def selected_label(mapping: dict[str, str], value: str | None, *, fresh_default: str) -> str:
        if parsed is None:
            return fresh_default
        return {code: label for label, code in mapping.items()}.get(value or "", "未说明")

    with st.form(f"{prefix}_form", border=True):
        st.markdown("#### 基本礼赠信息")
        left, right = st.columns(2)
        left.selectbox(
            "客户类型",
            ["未说明", *CUSTOMER_TYPES],
            index=["未说明", *CUSTOMER_TYPES].index(
                selected_label(
                    CUSTOMER_TYPES,
                    parsed.customer_type if parsed else None,
                    fresh_default="未说明",
                )
            ),
            key=f"{prefix}_customer_type",
        )
        right.selectbox(
            "礼赠对象",
            ["未说明", *RECIPIENTS],
            index=["未说明", *RECIPIENTS].index(
                selected_label(
                    RECIPIENTS, parsed.recipient if parsed else None, fresh_default="未说明"
                )
            ),
            key=f"{prefix}_recipient",
        )
        left.selectbox(
            "礼赠场景",
            ["未说明", *SCENES],
            index=["未说明", *SCENES].index(
                selected_label(SCENES, parsed.scene if parsed else None, fresh_default="未说明")
            ),
            key=f"{prefix}_scene",
        )
        left.text_input(
            "单件预算（元）",
            value=""
            if parsed is None or parsed.budget_per_item is None
            else str(parsed.budget_per_item),
            placeholder="例如 800",
            key=f"{prefix}_budget",
        )
        right.text_input(
            "采购数量",
            value="" if parsed is None or parsed.quantity is None else str(parsed.quantity),
            placeholder="例如 20",
            key=f"{prefix}_quantity",
        )
        right.text_input(
            "交付天数",
            value=(
                ""
                if parsed is None or parsed.required_delivery_days is None
                else str(parsed.required_delivery_days)
            ),
            placeholder="例如 21",
            key=f"{prefix}_delivery",
        )
        with st.expander("偏好与文化表达", expanded=prefix == "confirm"):
            st.multiselect(
                "风格偏好",
                list(STYLES),
                default=[]
                if parsed is None
                else [label for label, code in STYLES.items() if code in parsed.style_preferences],
                key=f"{prefix}_styles",
            )
            st.multiselect(
                "文化寓意",
                list(MEANINGS),
                default=[]
                if parsed is None
                else [
                    label
                    for label, code in MEANINGS.items()
                    if code in parsed.symbolism_preferences
                ],
                key=f"{prefix}_meanings",
            )
            st.text_input(
                "定制主题",
                value="" if parsed is None else parsed.requested_theme or "",
                key=f"{prefix}_theme",
            )
            st.text_input(
                "题字内容",
                value="" if parsed is None else parsed.requested_text or "",
                key=f"{prefix}_text",
            )
        with st.expander("定制与交付", expanded=prefix == "confirm"):
            col1, col2 = st.columns(2)
            col1.radio(
                "是否需要定制",
                ("未说明", "需要", "不需要"),
                index=("未说明", "需要", "不需要").index(
                    _bool_label(parsed.customization_required if parsed else None)
                ),
                key=f"{prefix}_customization",
            )
            col1.radio(
                "需要 Logo",
                ("未说明", "需要", "不需要"),
                index=("未说明", "需要", "不需要").index(
                    _bool_label(parsed.logo_required if parsed else None)
                ),
                key=f"{prefix}_logo",
            )
            col1.radio(
                "需要国际运输",
                ("未说明", "需要", "不需要"),
                index=("未说明", "需要", "不需要").index(
                    _bool_label(parsed.international_shipping_required if parsed else None)
                ),
                key=f"{prefix}_international",
            )
            existing_types = set(parsed.customization_types) if parsed else set()
            col2.multiselect(
                "定制类型",
                list(CUSTOMIZATION_TYPES),
                default=[
                    label for label, code in CUSTOMIZATION_TYPES.items() if code in existing_types
                ],
                key=f"{prefix}_customization_types",
            )
            st.text_input(
                "包装要求",
                value="" if parsed is None else parsed.packaging_requirement or "",
                key=f"{prefix}_packaging_note",
            )
            st.text_input(
                "目的国家或地区",
                value="" if parsed is None else parsed.destination or "",
                placeholder="例如 美国",
                key=f"{prefix}_destination",
            )
            language_value = (
                "未说明"
                if parsed is None
                else {code: label for label, code in OUTPUT_LANGUAGES.items()}.get(
                    parsed.output_language or "", "未说明"
                )
            )
            st.radio(
                "文化介绍语言",
                ("未说明", *OUTPUT_LANGUAGES),
                index=["未说明", *OUTPUT_LANGUAGES].index(language_value),
                horizontal=True,
                key=f"{prefix}_language",
            )
            st.text_area(
                "其他说明",
                value="" if parsed is None else parsed.additional_notes or "",
                height=80,
                key=f"{prefix}_notes",
            )
        return st.form_submit_button(submit_label, type="primary", width="stretch")


def _display_value(value: Any, mapping: dict[str, str] | None = None) -> str:
    if value is None or value == "" or value == ():
        return "需要补充"
    if isinstance(value, bool):
        return "需要" if value else "不需要"
    if isinstance(value, tuple):
        reverse = {code: label for label, code in (mapping or {}).items()}
        return "、".join(reverse.get(str(item), str(item)) for item in value) or "需要补充"
    if mapping:
        reverse = {code: label for label, code in mapping.items()}
        return reverse.get(str(value), str(value))
    return str(value)


def requirement_rows(parsed: ParsedCustomerRequest) -> list[tuple[str, str, str]]:
    values = {
        "customer_type": _display_value(parsed.customer_type, CUSTOMER_TYPES),
        "recipient": _display_value(parsed.recipient, RECIPIENTS),
        "scene": _display_value(parsed.scene, SCENES),
        "budget_per_item": (
            "需要补充" if parsed.budget_per_item is None else f"¥{parsed.budget_per_item:,.0f} / 件"
        ),
        "quantity": "需要补充" if parsed.quantity is None else f"{parsed.quantity} 件",
        "style_preferences": _display_value(parsed.style_preferences, STYLES),
        "symbolism_preferences": _display_value(parsed.symbolism_preferences, MEANINGS),
        "customization_required": _display_value(parsed.customization_required),
        "customization_types": _display_value(parsed.customization_types, CUSTOMIZATION_TYPES),
        "logo_required": _display_value(parsed.logo_required),
        "destination": _display_value(parsed.destination),
        "required_delivery_days": (
            "需要补充"
            if parsed.required_delivery_days is None
            else f"{parsed.required_delivery_days} 天内"
        ),
        "output_language": _display_value(parsed.output_language, OUTPUT_LANGUAGES),
    }
    rows = []
    for field, value in values.items():
        if field in parsed.uncertain_fields:
            status = "待用户确认"
        elif field in parsed.missing_fields or value == "需要补充":
            status = "需要补充"
        else:
            status = "已确认"
        rows.append((FIELD_DISPLAY[field], value, status))
    return rows


def render_requirement_summary(parsed: ParsedCustomerRequest) -> None:
    """Render requirement facts as readable status cards instead of raw JSON."""
    columns = st.columns(3)
    for index, (label, value, status) in enumerate(requirement_rows(parsed)):
        with columns[index % 3], st.container(border=True):
            st.caption(f"{label} · {status}")
            st.markdown(f"**{value}**")
