"""Streamlit interface for 飞颐礼遇（HeritageLink AI）."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from heritagelink.content import generate_bilingual_content
from heritagelink.conversation_state import ConversationState, new_conversation
from heritagelink.customization_concept import (
    CONCEPT_DISCLAIMER,
    build_customization_concept,
)
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.dialogue_manager import (
    mark_recommendations_shown,
    parsed_request_payload,
    process_turn,
    request_revision,
    skip_suggested_question,
)
from heritagelink.inquiry import (
    InquiryDetails,
    build_customization_inquiry,
    inquiry_to_json,
)
from heritagelink.models import DataBundle, GiftRequest, Product, Recommendation
from heritagelink.progressive_recommender import (
    FIELD_LABELS,
    MODE_LABELS,
    ProgressiveRecommendationResult,
    recommend_progressively,
)
from heritagelink.recommender import recommend
from heritagelink.request_parser import (
    BUDGET_TYPES,
    CUSTOMIZATION_TYPES,
    OUTPUT_LANGUAGES,
    ParsedCustomerRequest,
    RequestValidationError,
    parse_request,
    to_business_request,
    to_inquiry_details,
    validate_parsed_payload,
)

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "demo"

CUSTOMER_TYPES = ("企业客户", "政府/高校/文化机构", "个人客户", "海外客户")
CUSTOMER_TYPE_CODES = {
    "企业客户": "corporate",
    "政府/高校/文化机构": "institution",
    "个人客户": "individual",
    "海外客户": "overseas",
}
OUTPUT_LANGUAGE_LABELS = {"中文": "zh", "English": "en", "中英双语": "bilingual"}
BUDGET_TYPE_LABELS = {"单件预算": "per_item", "总预算": "total"}
CUSTOMIZATION_TYPE_LABELS = {
    "题字": "inscription",
    "图案": "pattern",
    "尺寸": "size",
    "包装": "packaging",
    "颜色": "color",
    "Logo": "logo",
    "其他": "other",
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
OCCASIONS = {
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
DESTINATIONS = (
    "中国大陆",
    "中国香港",
    "中国澳门",
    "中国台湾",
    "新加坡",
    "美国",
    "英国",
    "其他海外国家或地区",
)
DIMENSION_LABELS = {
    "budget": "预算匹配",
    "recipient": "赠礼对象",
    "occasion": "使用场景",
    "style": "风格偏好",
    "cultural_meaning": "文化寓意",
    "customization": "定制匹配",
    "quantity": "数量与产能",
    "lead_time": "交付时间",
}
TAG_LABELS = {
    **{value: key for key, value in RECIPIENTS.items()},
    **{value: key for key, value in OCCASIONS.items()},
    **{value: key for key, value in STYLES.items()},
    **{value: key for key, value in MEANINGS.items()},
    "customization:inscription": "定制：题字",
    "customization:packaging": "定制：包装",
    "customization:logo": "定制：Logo",
}


def _apply_modern_theme() -> None:
    """Apply a restrained modern visual system to the Streamlit shell."""
    st.markdown(
        """
        <style>
        :root {
            --hl-ink: #202521;
            --hl-muted: #68716a;
            --hl-paper: #f7f6f2;
            --hl-surface: #ffffff;
            --hl-line: #e5e1d8;
            --hl-accent: #a45f35;
            --hl-accent-dark: #7d4324;
        }
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 92% 2%, rgba(164, 95, 53, 0.10), transparent 28rem),
                var(--hl-paper);
            color: var(--hl-ink);
        }
        [data-testid="stHeader"] { background: transparent; }
        .block-container {
            max-width: 1180px;
            padding-top: 2.25rem;
            padding-bottom: 4rem;
        }
        .hl-hero {
            padding: 2.2rem 2.4rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--hl-line);
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.86);
            box-shadow: 0 18px 50px rgba(41, 35, 29, 0.06);
        }
        .hl-eyebrow {
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: #f3e8df;
            color: var(--hl-accent-dark);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.12em;
        }
        .hl-hero h1 {
            max-width: 760px;
            margin: 1rem 0 0.65rem;
            color: var(--hl-ink);
            font-size: clamp(2.1rem, 5vw, 3.75rem);
            line-height: 1.08;
            letter-spacing: -0.045em;
        }
        .hl-hero p {
            max-width: 680px;
            margin: 0;
            color: var(--hl-muted);
            font-size: 1.02rem;
            line-height: 1.75;
        }
        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--hl-line) !important;
            border-radius: 18px !important;
            background: rgba(255, 255, 255, 0.78);
        }
        div[data-testid="stMetric"] {
            padding: 1rem;
            border: 1px solid var(--hl-line);
            border-radius: 14px;
            background: var(--hl-surface);
        }
        div[data-testid="stChatMessage"] {
            border: 1px solid var(--hl-line);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.82);
        }
        .stButton > button, .stDownloadButton > button {
            min-height: 2.65rem;
            border-radius: 12px;
            border-color: #d8d1c5;
            font-weight: 650;
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(41, 35, 29, 0.08);
        }
        button[kind="primary"] {
            border-color: var(--hl-accent) !important;
            background: var(--hl-accent) !important;
        }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        textarea { border-radius: 11px !important; }
        hr { border-color: var(--hl-line); }
        @media (max-width: 700px) {
            .block-container { padding: 1rem 0.8rem 3rem; }
            .hl-hero { padding: 1.5rem; border-radius: 18px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
        <section class="hl-hero">
            <span class="hl-eyebrow">飞颐礼遇 · HERITAGELINK AI</span>
            <h1>为每一次赠礼，找到合适的非遗表达</h1>
            <p>通过对话或详细表单整理需求，获得清晰、可解释的产品推荐与定制方案。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def load_catalog() -> tuple[DataBundle, tuple[Product, ...]]:
    """Load validated local demo data once for the Streamlit process."""
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _recommendation_reasons(
    recommendation: Recommendation,
    participating_dimensions: frozenset[str] | None = None,
) -> tuple[str, ...]:
    ranked = sorted(
        (
            dimension
            for key, dimension in recommendation.score_breakdown.items()
            if participating_dimensions is None or key in participating_dimensions
        ),
        key=lambda dimension: (-dimension.score, -dimension.max_score, dimension.explanation),
    )
    if not ranked:
        return ("当前信息较少，先展示具有代表性的产品方向。",)
    return tuple(item.explanation for item in ranked[:3])


def _detailed_request_form() -> tuple[GiftRequest, InquiryDetails] | None:
    st.subheader("详细表单")
    st.caption("表单内容会直接交给可解释规则引擎，不经过大模型。")
    with st.form("gift_request_form"):
        left, right = st.columns(2)
        with left:
            customer_type = st.selectbox("客户类型", CUSTOMER_TYPES)
            recipient_label = st.selectbox("赠礼对象", tuple(RECIPIENTS))
            budget_yuan = st.number_input(
                "绝对单件预算上限（人民币元）",
                min_value=100,
                max_value=100000,
                value=1200,
            )
            quantity = st.number_input("采购数量", min_value=1, max_value=10000, value=10)
            occasion_label = st.selectbox("使用场景", tuple(OCCASIONS))
            style_label = st.selectbox("风格偏好", tuple(STYLES))
        with right:
            meaning_label = st.selectbox("文化寓意偏好", tuple(MEANINGS))
            customization_required = st.checkbox("需要定制")
            logo_required = st.checkbox("必须加入 Logo", disabled=not customization_required)
            destination = st.selectbox("目的国家或地区", DESTINATIONS)
            available_lead_days = st.number_input(
                "希望在多少天内交付", min_value=1, max_value=365, value=45
            )
            output_language = st.selectbox("输出语言", tuple(OUTPUT_LANGUAGE_LABELS), index=2)

        customization_theme = ""
        inscription_text = ""
        packaging_requirement = ""
        if customization_required:
            st.markdown("#### 定制补充信息")
            customization_theme = st.text_input("定制主题", max_chars=500)
            inscription_text = st.text_input("题字内容", max_chars=500)
            packaging_requirement = st.text_area("包装要求", max_chars=500)

        submitted = st.form_submit_button("开始推荐", type="primary", width="stretch")
    if not submitted:
        return None

    required_types = {"inscription"} if inscription_text.strip() else set()
    preferred_types = {"packaging"} if packaging_requirement.strip() else set()
    request = GiftRequest(
        request_id=f"req_demo_{uuid4().hex[:12]}",
        unit_budget_max_fen=int(budget_yuan) * 100,
        quantity=int(quantity),
        recipient_tags=frozenset({RECIPIENTS[recipient_label]}),
        occasion_tags=frozenset({OCCASIONS[occasion_label]}),
        style_tags=frozenset({STYLES[style_label]}),
        meaning_tags=frozenset({MEANINGS[meaning_label]}),
        customization_required=customization_required,
        required_customization_types=frozenset(required_types),
        preferred_customization_types=frozenset(preferred_types),
        logo_required=logo_required,
        international_shipping_required=destination != "中国大陆",
        available_lead_days=int(available_lead_days),
    )
    details = InquiryDetails(
        customer_type=customer_type,
        customization_theme=customization_theme,
        inscription_text=inscription_text,
        packaging_requirement=packaging_requirement,
        destination=destination,
        output_language=output_language,
    )
    return request, details


def _parse_optional_float(value: str, field_name: str) -> float | None:
    if not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RequestValidationError(f"{field_name} 必须是数字。") from exc
    if parsed <= 0:
        raise RequestValidationError(f"{field_name} 必须大于 0。")
    return parsed


def _parse_optional_int(value: str, field_name: str) -> int | None:
    if not value.strip():
        return None
    if not value.strip().isdigit() or int(value) <= 0:
        raise RequestValidationError(f"{field_name} 必须是正整数。")
    return int(value)


def _bool_choice(value: bool | None) -> str:
    return {True: "是", False: "否", None: "待确认"}[value]


def _choice_bool(value: str) -> bool | None:
    return {"是": True, "否": False, "待确认": None}[value]


def _invalidate_smart_confirmation(*, clear_parse: bool = False) -> None:
    """Invalidate stale confirmation and recommendations after smart input changes."""
    st.session_state["smart_request_confirmed"] = False
    for key in (
        "confirmed_customer_request",
        "edited_customer_request",
        "smart_confirmed_fingerprint",
        "recommendation_response",
        "gift_request",
        "inquiry_details",
        "active_inquiry_product",
    ):
        st.session_state.pop(key, None)
    if clear_parse:
        st.session_state.pop("parsed_customer_request", None)


def _reset_smart_editor_widgets() -> None:
    for key in tuple(st.session_state):
        if key.startswith("smart_edit_") or key == "smart_confirmation_checkbox":
            st.session_state.pop(key, None)


def _smart_parse_entry() -> None:
    st.subheader("智能描述")
    st.caption("解析结果不会直接推荐；请先逐项检查、修改并确认。")
    text = st.text_area(
        "请描述礼品需求",
        height=130,
        placeholder="例如：我想给30位美国合作伙伴准备周年纪念礼物……",
        key="smart_request_text",
    )
    parsed_source = st.session_state.get("smart_parsed_source_text")
    if parsed_source is not None and text != parsed_source:
        _invalidate_smart_confirmation(clear_parse=True)
        st.session_state.pop("smart_parsed_source_text", None)
        st.warning("原始描述已修改，旧解析和确认状态已失效，请重新解析。")
    parser_choice = st.radio(
        "解析方式",
        ("自动（优先 DeepSeek）", "确定性演示解析"),
        horizontal=True,
        key="parser_choice",
    )
    if st.button("AI解析需求", type="primary", key="parse_request_button"):
        try:
            selected_mode = "deterministic_demo" if parser_choice == "确定性演示解析" else "auto"
            parsed = parse_request(text, mode=selected_mode)
            _invalidate_smart_confirmation()
            _reset_smart_editor_widgets()
            st.session_state["smart_raw_user_text"] = text
            st.session_state["smart_parsed_source_text"] = text
            st.session_state["parsed_customer_request"] = parsed
        except RequestValidationError as exc:
            st.error(str(exc))


def _smart_confirmation_form() -> tuple[GiftRequest, InquiryDetails] | None:
    parsed = st.session_state.get("parsed_customer_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        return None
    if parsed.parser_mode == "deterministic_demo":
        st.warning("当前使用演示解析模式。该结果不是 DeepSeek 输出，请重点核对。")
    else:
        st.success("当前使用 DeepSeek AI 解析模式。")
    if parsed.parser_notice:
        st.info(parsed.parser_notice)
    if parsed.missing_fields:
        st.warning(f"缺失字段：{', '.join(parsed.missing_fields)}")
    if parsed.uncertain_fields:
        st.warning(f"不确定字段：{', '.join(parsed.uncertain_fields)}")
    for question in parsed.clarification_questions:
        st.info(f"需要补充：{question}")
    with st.expander("查看完整结构化解析结果"):
        st.json(asdict(parsed), expanded=True)

    customer_options = ("", *CUSTOMER_TYPE_CODES.values())
    recipient_options = ("", *RECIPIENTS.values())
    scene_options = ("", *OCCASIONS.values())
    language_options = ("", *OUTPUT_LANGUAGES)
    budget_type_options = ("", *BUDGET_TYPES)
    style_options = tuple(dict.fromkeys((*STYLES.values(), *parsed.style_preferences)))
    meaning_options = tuple(dict.fromkeys((*MEANINGS.values(), *parsed.symbolism_preferences)))
    customization_type_options = tuple(
        dict.fromkeys((*CUSTOMIZATION_TYPES, *parsed.customization_types))
    )
    customer_labels = {value: key for key, value in CUSTOMER_TYPE_CODES.items()}
    language_labels = {value: key for key, value in OUTPUT_LANGUAGE_LABELS.items()}
    budget_labels = {value: key for key, value in BUDGET_TYPE_LABELS.items()}
    customization_labels = {value: key for key, value in CUSTOMIZATION_TYPE_LABELS.items()}
    with st.form("smart_confirmation_form"):
        st.markdown("#### 请检查并修改解析结果")
        left, right = st.columns(2)
        with left:
            customer_type = st.selectbox(
                "客户类型",
                customer_options,
                index=customer_options.index(parsed.customer_type or ""),
                format_func=lambda value: customer_labels.get(value, "待确认"),
                key="smart_edit_customer_type",
            )
            budget_type = st.selectbox(
                "预算类型",
                budget_type_options,
                index=budget_type_options.index(parsed.budget_type or ""),
                format_func=lambda value: budget_labels.get(value, "待确认"),
                key="smart_edit_budget_type",
            )
            total_budget = st.text_input(
                "总预算（人民币元）",
                value="" if parsed.total_budget is None else f"{parsed.total_budget:g}",
                key="smart_edit_total_budget",
            )
            budget = st.text_input(
                "绝对单件预算上限（人民币元）",
                value="" if parsed.budget_per_item is None else f"{parsed.budget_per_item:g}",
                key="smart_edit_budget",
            )
            quantity = st.text_input(
                "采购数量",
                value="" if parsed.quantity is None else str(parsed.quantity),
                key="smart_edit_quantity",
            )
            recipient = st.selectbox(
                "赠礼对象",
                recipient_options,
                index=recipient_options.index(parsed.recipient or ""),
                format_func=lambda value: TAG_LABELS.get(value, "待确认"),
                key="smart_edit_recipient",
            )
            scene = st.selectbox(
                "使用场景",
                scene_options,
                index=scene_options.index(parsed.scene or ""),
                format_func=lambda value: TAG_LABELS.get(value, "待确认"),
                key="smart_edit_scene",
            )
            styles = st.multiselect(
                "风格偏好",
                style_options,
                default=parsed.style_preferences,
                format_func=lambda value: TAG_LABELS.get(value, value),
                key="smart_edit_styles",
            )
            meanings = st.multiselect(
                "文化寓意偏好",
                meaning_options,
                default=parsed.symbolism_preferences,
                format_func=lambda value: TAG_LABELS.get(value, value),
                key="smart_edit_meanings",
            )
        with right:
            customization = st.selectbox(
                "是否需要定制",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(_bool_choice(parsed.customization_required)),
                key="smart_edit_customization",
            )
            customization_types = st.multiselect(
                "定制类型",
                customization_type_options,
                default=parsed.customization_types,
                format_func=lambda value: customization_labels.get(value, value),
                key="smart_edit_customization_types",
            )
            logo = st.selectbox(
                "是否需要 Logo",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(_bool_choice(parsed.logo_required)),
                key="smart_edit_logo",
            )
            destination = st.text_input(
                "目的国家或地区",
                value=parsed.destination or "",
                key="smart_edit_destination",
            )
            international = st.selectbox(
                "是否必须国际运输",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(
                    _bool_choice(parsed.international_shipping_required)
                ),
                key="smart_edit_international",
            )
            delivery = st.text_input(
                "交付天数",
                value=(
                    ""
                    if parsed.required_delivery_days is None
                    else str(parsed.required_delivery_days)
                ),
                key="smart_edit_delivery",
            )
            output_language = st.selectbox(
                "输出语言",
                language_options,
                index=language_options.index(parsed.output_language or ""),
                format_func=lambda value: language_labels.get(value, "待确认"),
                key="smart_edit_language",
            )
            theme = st.text_input(
                "定制主题", value=parsed.requested_theme or "", key="smart_edit_theme"
            )
            requested_text = st.text_input(
                "题字内容", value=parsed.requested_text or "", key="smart_edit_text"
            )
            packaging = st.text_area(
                "包装要求", value=parsed.packaging_requirement or "", key="smart_edit_packaging"
            )
            additional_notes = st.text_area(
                "其他说明", value=parsed.additional_notes or "", key="smart_edit_notes"
            )
        confirmation_ack = st.checkbox(
            "我已核对以上字段，确认以此版本进行推荐",
            key="smart_confirmation_checkbox",
        )
        confirmation_submitted = st.form_submit_button(
            "确认结构化需求", type="primary", width="stretch"
        )

    try:
        payload: dict[str, Any] = {
            "customer_type": customer_type or None,
            "budget_type": budget_type or None,
            "total_budget": _parse_optional_float(total_budget, "总预算"),
            "budget_per_item": _parse_optional_float(budget, "单件预算"),
            "quantity": _parse_optional_int(quantity, "采购数量"),
            "recipient": recipient or None,
            "scene": scene or None,
            "style_preferences": list(styles),
            "symbolism_preferences": list(meanings),
            "customization_required": _choice_bool(customization),
            "customization_types": list(customization_types),
            "logo_required": _choice_bool(logo),
            "international_shipping_required": _choice_bool(international),
            "destination": destination.strip() or None,
            "required_delivery_days": _parse_optional_int(delivery, "交付天数"),
            "output_language": output_language or None,
            "requested_theme": theme.strip() or None,
            "requested_text": requested_text.strip() or None,
            "packaging_requirement": packaging.strip() or None,
            "additional_notes": additional_notes.strip() or None,
            "uncertain_fields": [],
            "missing_fields": [],
            "clarification_questions": [],
        }
    except RequestValidationError as exc:
        st.error(str(exc))
        return None

    fingerprint = repr(payload)
    st.session_state["smart_edited_payload"] = payload
    if (
        st.session_state.get("smart_request_confirmed")
        and st.session_state.get("smart_confirmed_fingerprint") != fingerprint
    ):
        _invalidate_smart_confirmation()
        st.warning("结构化字段已修改，旧确认和推荐结果已失效，请重新确认。")

    if confirmation_submitted:
        if not confirmation_ack:
            st.error("请先勾选确认声明。")
        else:
            try:
                confirmed_parse = validate_parsed_payload(
                    payload,
                    raw_user_text=parsed.raw_user_text,
                    parser_mode=parsed.parser_mode,
                )
                to_business_request(confirmed_parse)
                st.session_state["edited_customer_request"] = confirmed_parse
                st.session_state["confirmed_customer_request"] = confirmed_parse
                st.session_state["smart_request_confirmed"] = True
                st.session_state["smart_confirmed_fingerprint"] = fingerprint
                st.success("结构化需求已确认，现在可以开始推荐。")
            except RequestValidationError as exc:
                _invalidate_smart_confirmation()
                st.error(str(exc))

    is_confirmed = bool(st.session_state.get("smart_request_confirmed"))
    if st.button(
        "开始推荐",
        type="primary",
        width="stretch",
        disabled=not is_confirmed,
        key="smart_start_recommendation",
    ):
        confirmed_request = st.session_state.get("confirmed_customer_request")
        if isinstance(confirmed_request, ParsedCustomerRequest):
            return to_business_request(confirmed_request)
    if not is_confirmed:
        st.caption("开始推荐前必须先确认结构化需求。")
    return None


def _render_inquiry(
    recommendation: Recommendation,
    request: GiftRequest,
    details: InquiryDetails,
    bundle: DataBundle,
) -> None:
    content = generate_bilingual_content(recommendation.product, bundle.product_texts)
    inquiry = build_customization_inquiry(request, recommendation, content, details)
    st.success("已生成结构化定制需求单，未确认信息已列入商家问题清单。")
    st.json(inquiry, expanded=False)
    st.download_button(
        "下载需求单 JSON",
        data=inquiry_to_json(inquiry),
        file_name=f"{inquiry['inquiry_id']}.json",
        mime="application/json",
        key=f"download_{recommendation.product.product_id}",
    )


def _render_recommendation(
    rank: int,
    recommendation: Recommendation,
    request: GiftRequest,
    details: InquiryDetails,
    bundle: DataBundle,
    *,
    participating_dimensions: frozenset[str] | None = None,
    conflicts: tuple[str, ...] = (),
    allow_inquiry: bool = True,
) -> None:
    product = recommendation.product
    with st.container(border=True):
        st.markdown(f"### {rank}. {product.product_name_zh}")
        st.caption(product.product_name_en)
        metric_left, metric_mid, metric_right = st.columns(3)
        metric_left.metric("当前匹配分", f"{recommendation.total_score:.1f} / 100")
        metric_mid.metric(
            "演示单价", f"{_money(product.price_min_fen)}–{_money(product.price_max_fen)}"
        )
        metric_right.metric("演示制作周期", f"{product.lead_time_days} 天")
        if conflicts:
            st.warning("替代方案存在冲突：" + "；".join(conflicts))
        st.markdown("#### 推荐理由")
        for reason in _recommendation_reasons(recommendation, participating_dimensions):
            st.markdown(f"- {reason}")
        with st.expander("查看各维度得分", expanded=True):
            st.dataframe(
                [
                    {
                        "维度": DIMENSION_LABELS[key],
                        "得分": (
                            value.score
                            if participating_dimensions is None or key in participating_dimensions
                            else "—"
                        ),
                        "满分": (
                            value.max_score
                            if participating_dimensions is None or key in participating_dimensions
                            else "—"
                        ),
                        "解释": (
                            value.explanation
                            if participating_dimensions is None or key in participating_dimensions
                            else "未提供，不参与本轮个性化评分。"
                        ),
                    }
                    for key, value in recommendation.score_breakdown.items()
                ],
                hide_index=True,
                width="stretch",
            )
        matched = [TAG_LABELS.get(tag, tag) for tag in recommendation.matched_tags]
        st.markdown(f"**匹配标签：** {'、'.join(matched) if matched else '无精确标签命中'}")
        st.markdown("**风险与待确认事项：**")
        for risk in recommendation.risks:
            st.warning(risk)
        content = generate_bilingual_content(product, bundle.product_texts)
        st.markdown("#### 双语文化介绍")
        zh_tab, en_tab = st.tabs(("中文", "English"))
        with zh_tab:
            st.text(content.zh.text)
        with en_tab:
            st.text(content.en.text)
        if allow_inquiry and st.button(
            "生成定制需求单", key=f"inquiry_{product.product_id}", width="stretch"
        ):
            st.session_state["active_inquiry_product"] = product.product_id
        if not allow_inquiry:
            st.caption("补充预算和数量后可生成更完整的定制需求单。")
        if allow_inquiry and st.session_state.get("active_inquiry_product") == product.product_id:
            _render_inquiry(recommendation, request, details, bundle)
        st.caption(product.demo_disclaimer)


def _render_results(bundle: DataBundle) -> None:
    progressive = st.session_state.get("progressive_result")
    response = (
        progressive.response
        if isinstance(progressive, ProgressiveRecommendationResult)
        else st.session_state.get("recommendation_response")
    )
    request = st.session_state.get("gift_request")
    details = st.session_state.get("inquiry_details")
    if response is None or request is None or details is None:
        return
    st.divider()
    st.header("推荐结果")
    participating: frozenset[str] | None = None
    allow_inquiry = True
    if isinstance(progressive, ProgressiveRecommendationResult):
        mode_col, coverage_col, confidence_col = st.columns(3)
        mode_col.metric("当前推荐类型", MODE_LABELS[progressive.mode])
        coverage_col.metric("信息覆盖度", f"{progressive.information_coverage:.0%}")
        confidence_col.metric("推荐置信度", progressive.confidence_level)
        participating = frozenset(progressive.participating_dimensions)
        allow_inquiry = not {
            "budget_per_item",
            "quantity",
        }.intersection(progressive.missing_fields)
        if progressive.missing_fields:
            st.caption(
                "尚未提供："
                + "、".join(FIELD_LABELS[field] for field in progressive.missing_fields)
                + "。这些信息未被视为不匹配。"
            )
        if progressive.mode.value == "exploring":
            st.info("当前结果用于帮助了解可选方向，并非基于完整采购条件的最终推荐。")
    if not response.has_eligible_products:
        st.error("当前没有满足全部明确条件的现有产品。")
        st.markdown("#### 主要冲突原因")
        for conflict in response.primary_conflicts:
            st.markdown(f"- {conflict}")
        st.markdown("#### 可以调整的条件")
        for suggestion in response.adjustment_suggestions:
            st.markdown(f"- {suggestion}")
        if isinstance(progressive, ProgressiveRecommendationResult) and progressive.alternatives:
            st.markdown("#### 接近条件的替代方案")
            st.caption("以下产品存在明确约束冲突，不属于完全匹配产品。")
            for rank, alternative in enumerate(progressive.alternatives, start=1):
                alternative_request = progressive.request_by_product[
                    alternative.recommendation.product.product_id
                ]
                _render_recommendation(
                    rank,
                    alternative.recommendation,
                    alternative_request,
                    details,
                    bundle,
                    participating_dimensions=participating,
                    conflicts=alternative.conflicts,
                    allow_inquiry=False,
                )
        st.markdown("#### 定制方向（概念草案）")
        st.caption("如果现有产品均不合格，可以把当前需求整理成待商家评估的概念方案。")
        if st.button("生成定制方案", key="generate_customization_concept"):
            st.session_state["customization_concept"] = build_customization_concept(
                request, details, response
            )
        concept = st.session_state.get("customization_concept")
        if concept:
            st.warning(CONCEPT_DISCLAIMER)
            st.json(concept, expanded=False)
        return
    st.success(f"找到 {len(response.recommendations)} 件当前可推荐产品。")
    for rank, recommendation in enumerate(response.recommendations, start=1):
        recommendation_request = (
            progressive.request_by_product[recommendation.product.product_id]
            if isinstance(progressive, ProgressiveRecommendationResult)
            else request
        )
        _render_recommendation(
            rank,
            recommendation,
            recommendation_request,
            details,
            bundle,
            participating_dimensions=participating,
            allow_inquiry=allow_inquiry,
        )


def _switch_to_detailed_form() -> None:
    st.session_state["input_mode"] = "详细表单"


def _conversation_advisor(products: tuple[Product, ...]) -> None:
    """Render and advance the stateful conversational advisor."""
    st.subheader("飞颐礼遇 AI 顾问")
    st.caption("先根据现有信息给出建议；你可以继续补充需求，让结果逐步更准确。")
    parser_label = st.radio(
        "对话解析方式",
        ("自动（优先 DeepSeek）", "确定性演示模式"),
        horizontal=True,
        key="dialogue_parser_choice",
    )
    mode = "auto" if parser_label.startswith("自动") else "deterministic_demo"
    state = st.session_state.get("conversation_state")
    if not isinstance(state, ConversationState):
        state = new_conversation()
        st.session_state["conversation_state"] = state

    control_left, control_mid, control_right = st.columns(3)
    if control_left.button("修改需求", width="stretch", key="dialogue_revise"):
        state = request_revision(state)
        st.session_state["conversation_state"] = state
        for key in (
            "recommendation_response",
            "progressive_result",
            "gift_request",
            "inquiry_details",
            "customization_concept",
        ):
            st.session_state.pop(key, None)
    if control_mid.button("重新开始", width="stretch", key="dialogue_restart"):
        state = new_conversation()
        st.session_state["conversation_state"] = state
        for key in (
            "recommendation_response",
            "progressive_result",
            "gift_request",
            "inquiry_details",
            "customization_concept",
        ):
            st.session_state.pop(key, None)
    control_right.button(
        "切换详细表单",
        width="stretch",
        key="dialogue_to_form",
        on_click=_switch_to_detailed_form,
    )

    if not state.messages:
        with st.chat_message("assistant"):
            st.write(
                "请描述礼品需求，例如赠送对象、场景、预算和数量；"
                "有明确的交期、Logo 或海外运输要求也请说明。"
            )
            st.caption("示例：想给外国朋友送一件有中国特色的周年礼物，预算暂时还没确定。")
    for message in state.messages:
        with st.chat_message(message.role):
            st.write(message.content)

    if state.accumulated_request is not None:
        with st.expander("查看当前结构化需求", expanded=True):
            summary_left, summary_mid, summary_right = st.columns(3)
            summary_left.metric(
                "推荐类型",
                {
                    "exploring": "探索推荐",
                    "guided": "引导推荐",
                    "constrained": "约束推荐",
                }.get(state.recommendation_mode, state.recommendation_mode),
            )
            summary_mid.metric("信息覆盖度", f"{state.information_coverage:.0%}")
            summary_right.metric("已识别字段", len(state.known_fields))
            st.json(parsed_request_payload(state.accumulated_request), expanded=False)
            if state.uncertain_fields:
                st.info("存在不确定字段：" + "、".join(state.uncertain_fields))
            if state.unknown_fields:
                st.caption(
                    "尚未提供："
                    + "、".join(FIELD_LABELS.get(field, field) for field in state.unknown_fields)
                )
    if state.clarification_questions and st.button(
        "跳过问题，查看当前推荐", key="skip_dialogue_question", width="stretch"
    ):
        state = skip_suggested_question(state)
        st.session_state["conversation_state"] = state
        st.rerun()

    prompt = st.chat_input(
        "描述需求或补充上一轮信息",
        key="dialogue_chat_input",
    )
    if not prompt:
        return
    try:
        turn = process_turn(state, prompt, mode=mode)
    except RequestValidationError as exc:
        st.error(str(exc))
        return
    state = turn.state
    st.session_state["conversation_state"] = state
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        st.write(turn.assistant_message)
    if turn.used_parser_mode == "deterministic_demo":
        st.warning("当前使用演示解析模式；请核对结构化字段，必要时继续用对话修正。")
    else:
        st.success("本轮使用 DeepSeek 对话解析，结果已通过本地字段校验。")

    if turn.recommended_action != "recommend_products":
        return
    assert state.accumulated_request is not None
    progressive = recommend_progressively(products, state.accumulated_request)
    details = to_inquiry_details(state.accumulated_request)
    if progressive.response.recommendations:
        first_product_id = progressive.response.recommendations[0].product.product_id
    else:
        first_product_id = next(iter(progressive.request_by_product))
    request = progressive.request_by_product[first_product_id]
    st.session_state["gift_request"] = request
    st.session_state["inquiry_details"] = details
    st.session_state["confirmed_customer_request"] = state.accumulated_request
    st.session_state["progressive_result"] = progressive
    st.session_state["recommendation_response"] = progressive.response
    st.session_state["conversation_state"] = mark_recommendations_shown(state)
    st.session_state.pop("customization_concept", None)
    st.session_state.pop("active_inquiry_product", None)
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="飞颐礼遇｜AI 非遗礼品顾问", page_icon="🎁", layout="wide")
    _apply_modern_theme()
    _render_hero()
    try:
        bundle, products = load_catalog()
    except DataValidationError as exc:
        st.error(f"演示数据加载失败：{exc}")
        st.stop()

    st.markdown("### 选择体验方式")
    input_mode = st.radio(
        "需求输入方式", ("AI礼品顾问", "详细表单"), horizontal=True, key="input_mode"
    )
    form_result: tuple[GiftRequest, InquiryDetails] | None
    if input_mode == "AI礼品顾问":
        _conversation_advisor(products)
        form_result = None
    else:
        form_result = _detailed_request_form()
    if form_result is not None:
        request, details = form_result
        st.session_state["gift_request"] = request
        st.session_state["inquiry_details"] = details
        st.session_state["recommendation_response"] = recommend(products, request)
        st.session_state.pop("progressive_result", None)
        st.session_state.pop("active_inquiry_product", None)
    _render_results(bundle)


if __name__ == "__main__":
    main()
