"""Streamlit demonstration interface for HeritageLink AI."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from heritagelink.content import generate_bilingual_content
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.inquiry import (
    InquiryDetails,
    build_customization_inquiry,
    inquiry_to_json,
)
from heritagelink.models import DataBundle, GiftRequest, Product, Recommendation
from heritagelink.recommender import recommend
from heritagelink.request_parser import (
    OUTPUT_LANGUAGES,
    ParsedCustomerRequest,
    RequestValidationError,
    parse_request,
    to_business_request,
    validate_parsed_payload,
)

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "demo"
DISCLAIMER = "当前产品、价格、产能、材料、交期和运输信息仅用于MVP演示，不代表飞颐铁画真实商业承诺。"

CUSTOMER_TYPES = ("企业客户", "政府/高校/文化机构", "个人客户", "海外客户")
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


@st.cache_resource
def load_catalog() -> tuple[DataBundle, tuple[Product, ...]]:
    """Load validated local demo data once for the Streamlit process."""
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _recommendation_reasons(recommendation: Recommendation) -> tuple[str, ...]:
    ranked = sorted(
        recommendation.score_breakdown.values(),
        key=lambda dimension: (-dimension.score, -dimension.max_score, dimension.explanation),
    )
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
            output_language = st.selectbox("输出语言", OUTPUT_LANGUAGES, index=2)

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


def _smart_parse_entry() -> None:
    st.subheader("智能描述")
    st.caption("解析结果不会直接推荐；请先逐项检查、修改并确认。")
    text = st.text_area(
        "请描述礼品需求",
        height=130,
        placeholder="例如：我想给30位美国合作伙伴准备周年纪念礼物……",
        key="smart_request_text",
    )
    parser_choice = st.radio(
        "解析方式",
        ("自动（优先 DeepSeek）", "确定性演示解析"),
        horizontal=True,
        key="parser_choice",
    )
    if st.button("AI解析需求", type="primary", key="parse_request_button"):
        try:
            selected_mode = "demo" if parser_choice == "确定性演示解析" else "auto"
            st.session_state["parsed_customer_request"] = parse_request(text, mode=selected_mode)
        except RequestValidationError as exc:
            st.error(str(exc))


def _smart_confirmation_form() -> tuple[GiftRequest, InquiryDetails] | None:
    parsed = st.session_state.get("parsed_customer_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        return None
    if parsed.parser_mode == "demo":
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

    customer_options = ("待确认", *CUSTOMER_TYPES)
    recipient_options = ("待确认", *RECIPIENTS.values())
    scene_options = ("待确认", *OCCASIONS.values())
    language_options = ("待确认", *OUTPUT_LANGUAGES)
    style_options = tuple(dict.fromkeys((*STYLES.values(), *parsed.style_preferences)))
    meaning_options = tuple(dict.fromkeys((*MEANINGS.values(), *parsed.symbolism_preferences)))
    with st.form("smart_confirmation_form"):
        st.markdown("#### 请检查并修改解析结果")
        left, right = st.columns(2)
        with left:
            customer_type = st.selectbox(
                "客户类型",
                customer_options,
                index=customer_options.index(parsed.customer_type or "待确认"),
                key="smart_customer_type",
            )
            recipient = st.selectbox(
                "赠礼对象",
                recipient_options,
                index=recipient_options.index(parsed.recipient or "待确认"),
                key="smart_recipient",
            )
            budget = st.text_input(
                "绝对单件预算上限（人民币元）",
                value="" if parsed.budget_per_item is None else f"{parsed.budget_per_item:g}",
                key="smart_budget",
            )
            quantity = st.text_input(
                "采购数量",
                value="" if parsed.quantity is None else str(parsed.quantity),
                key="smart_quantity",
            )
            scene = st.selectbox(
                "使用场景",
                scene_options,
                index=scene_options.index(parsed.scene or "待确认"),
                key="smart_scene",
            )
            styles = st.multiselect(
                "风格偏好",
                style_options,
                default=parsed.style_preferences,
                key="smart_styles",
            )
            meanings = st.multiselect(
                "文化寓意偏好",
                meaning_options,
                default=parsed.symbolism_preferences,
                key="smart_meanings",
            )
        with right:
            customization = st.selectbox(
                "是否需要定制",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(_bool_choice(parsed.customization_required)),
                key="smart_customization",
            )
            logo = st.selectbox(
                "是否需要 Logo",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(_bool_choice(parsed.logo_required)),
                key="smart_logo",
            )
            destination = st.text_input(
                "目的国家或地区",
                value=parsed.destination_country or "",
                key="smart_destination",
            )
            international = st.selectbox(
                "是否必须国际运输",
                ("待确认", "是", "否"),
                index=("待确认", "是", "否").index(
                    _bool_choice(parsed.international_shipping_required)
                ),
                key="smart_international",
            )
            delivery = st.text_input(
                "交付天数",
                value=(
                    ""
                    if parsed.required_delivery_days is None
                    else str(parsed.required_delivery_days)
                ),
                key="smart_delivery",
            )
            output_language = st.selectbox(
                "输出语言",
                language_options,
                index=language_options.index(parsed.output_language or "待确认"),
                key="smart_language",
            )
            theme = st.text_input("定制主题", value=parsed.requested_theme or "")
            requested_text = st.text_input("题字内容", value=parsed.requested_text or "")
            packaging = st.text_area("包装要求", value=parsed.packaging_requirement or "")
        confirmed = st.form_submit_button("开始推荐", type="primary", width="stretch")
    if not confirmed:
        return None

    try:
        payload: dict[str, Any] = {
            "customer_type": None if customer_type == "待确认" else customer_type,
            "recipient": None if recipient == "待确认" else recipient,
            "budget_per_item": _parse_optional_float(budget, "单件预算"),
            "quantity": _parse_optional_int(quantity, "采购数量"),
            "scene": None if scene == "待确认" else scene,
            "style_preferences": list(styles),
            "symbolism_preferences": list(meanings),
            "customization_required": _choice_bool(customization),
            "logo_required": _choice_bool(logo),
            "destination_country": destination.strip() or None,
            "international_shipping_required": _choice_bool(international),
            "required_delivery_days": _parse_optional_int(delivery, "交付天数"),
            "output_language": None if output_language == "待确认" else output_language,
            "requested_theme": theme.strip() or None,
            "requested_text": requested_text.strip() or None,
            "packaging_requirement": packaging.strip() or None,
            "uncertain_fields": [],
            "missing_fields": [],
            "clarification_questions": [],
        }
        confirmed_parse = validate_parsed_payload(
            payload,
            raw_user_text=parsed.raw_user_text,
            parser_mode=parsed.parser_mode,
        )
        return to_business_request(confirmed_parse)
    except RequestValidationError as exc:
        st.error(str(exc))
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
) -> None:
    product = recommendation.product
    with st.container(border=True):
        st.markdown(f"### {rank}. {product.product_name_zh}")
        st.caption(product.product_name_en)
        metric_left, metric_mid, metric_right = st.columns(3)
        metric_left.metric("综合匹配分", f"{recommendation.total_score:.1f} / 100")
        metric_mid.metric(
            "演示单价", f"{_money(product.price_min_fen)}–{_money(product.price_max_fen)}"
        )
        metric_right.metric("演示制作周期", f"{product.lead_time_days} 天")
        st.markdown("#### 推荐理由")
        for reason in _recommendation_reasons(recommendation):
            st.markdown(f"- {reason}")
        with st.expander("查看各维度得分", expanded=True):
            st.dataframe(
                [
                    {
                        "维度": DIMENSION_LABELS[key],
                        "得分": value.score,
                        "满分": value.max_score,
                        "解释": value.explanation,
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
        if st.button("生成定制需求单", key=f"inquiry_{product.product_id}", width="stretch"):
            st.session_state["active_inquiry_product"] = product.product_id
        if st.session_state.get("active_inquiry_product") == product.product_id:
            _render_inquiry(recommendation, request, details, bundle)
        st.caption(product.demo_disclaimer)


def _render_results(bundle: DataBundle) -> None:
    response = st.session_state.get("recommendation_response")
    request = st.session_state.get("gift_request")
    details = st.session_state.get("inquiry_details")
    if response is None or request is None or details is None:
        return
    st.divider()
    st.header("推荐结果")
    if not response.has_eligible_products:
        st.error("没有合格产品，本次不会强行推荐。")
        st.markdown("#### 主要冲突原因")
        for conflict in response.primary_conflicts:
            st.markdown(f"- {conflict}")
        st.markdown("#### 可以调整的条件")
        for suggestion in response.adjustment_suggestions:
            st.markdown(f"- {suggestion}")
        return
    st.success(f"找到 {len(response.recommendations)} 件符合硬性条件的演示产品。")
    for rank, recommendation in enumerate(response.recommendations, start=1):
        _render_recommendation(rank, recommendation, request, details, bundle)


def main() -> None:
    st.set_page_config(page_title="HeritageLink AI｜非遗礼遇", page_icon="🎁", layout="wide")
    st.title("HeritageLink AI｜非遗礼遇")
    st.markdown("把自然语言或详细表单转成可解释推荐和商家可执行的定制需求单。")
    st.error(DISCLAIMER)
    st.info("DeepSeek 只解析客户需求；价格、数量、交期、定制和运输仍由原规则引擎判断。")
    try:
        bundle, products = load_catalog()
    except DataValidationError as exc:
        st.error(f"演示数据加载失败：{exc}")
        st.stop()

    input_mode = st.radio(
        "需求输入方式", ("详细表单", "智能描述"), horizontal=True, key="input_mode"
    )
    form_result: tuple[GiftRequest, InquiryDetails] | None
    if input_mode == "智能描述":
        _smart_parse_entry()
        form_result = _smart_confirmation_form()
    else:
        form_result = _detailed_request_form()
    if form_result is not None:
        request, details = form_result
        st.session_state["gift_request"] = request
        st.session_state["inquiry_details"] = details
        st.session_state["recommendation_response"] = recommend(products, request)
        st.session_state.pop("active_inquiry_product", None)
    _render_results(bundle)


if __name__ == "__main__":
    main()
