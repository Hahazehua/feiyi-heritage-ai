"""Five-stage Streamlit experience for 飞颐礼遇（HeritageLink AI）."""

from __future__ import annotations

from dataclasses import asdict
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import streamlit as st

from heritagelink.catalog import CatalogDataError, HeritageReferenceItem, load_reference_catalog
from heritagelink.content import BilingualContent, generate_bilingual_content
from heritagelink.conversation_state import ConversationState, new_conversation
from heritagelink.customization_concept import (
    CONCEPT_DISCLAIMER,
    build_customization_concept,
)
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.dialogue_manager import process_turn
from heritagelink.inquiry import (
    InquiryDetails,
    InquiryRequestContext,
    build_customization_inquiry,
    inquiry_to_json,
)
from heritagelink.models import DataBundle, GiftRequest, Product, Recommendation
from heritagelink.progressive_recommender import (
    MODE_LABELS,
    ProgressiveRecommendationResult,
    recommend_progressively,
)
from heritagelink.request_parser import (
    ParsedCustomerRequest,
    RequestValidationError,
    to_inquiry_details,
)
from heritagelink.ui.catalog_gallery import render_catalog_gallery
from heritagelink.ui.components import (
    badges,
    product_image,
    render_hero,
    render_progress,
    section_intro,
)
from heritagelink.ui.inquiry_summary import render_copyable_summary
from heritagelink.ui.product_card import render_product_card
from heritagelink.ui.requirements import (
    CUSTOMER_TYPES,
    MEANINGS,
    RECIPIENTS,
    SCENES,
    STYLES,
    parsed_from_widgets,
    render_requirement_summary,
    render_structured_form,
)
from heritagelink.ui.theme import apply_theme

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "demo"
REFERENCE_CATALOG_PATH = ROOT / "data" / "catalog" / "heritage_products.csv"

STAGES = ("describe", "confirm", "recommend", "culture", "inquiry", "catalog")
EXAMPLES = (
    "为 20 位海外合作伙伴准备每份 300 元左右的中国文化礼物。",
    "为外籍教授选择一件有文化故事、便于携带的感谢礼物。",
    "为企业周年活动准备支持 Logo 定制的非遗礼品。",
)
DEMO_CASE = (
    "企业计划为20位美国商务合作伙伴准备商务答谢礼物，每件预算300元，"
    "希望风格典雅、现代，可以加公司Logo，21天内完成，并提供中英文文化介绍。"
)

TAG_LABELS = {
    **{value: key for key, value in RECIPIENTS.items()},
    **{value: key for key, value in SCENES.items()},
    **{value: key for key, value in STYLES.items()},
    **{value: key for key, value in MEANINGS.items()},
    "customization:inscription": "支持题字",
    "customization:packaging": "支持包装定制",
    "customization:logo": "支持 Logo",
}


@st.cache_resource(show_spinner=False)
def load_catalog() -> tuple[DataBundle, tuple[Product, ...]]:
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


@st.cache_data(show_spinner=False)
def load_heritage_reference_catalog() -> tuple[HeritageReferenceItem, ...]:
    return load_reference_catalog(REFERENCE_CATALOG_PATH, project_root=ROOT)


def _init_state() -> None:
    st.session_state.setdefault("ui_stage", "describe")
    st.session_state.setdefault("hero_request_text", "")
    st.session_state.setdefault("entry_mode", "AI 描述需求")
    st.session_state.setdefault("dialogue_mode", "deterministic_demo")


def _set_stage(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"未知页面阶段：{stage}")
    st.session_state["ui_stage"] = stage


def _clear_after_parse() -> None:
    for key in (
        "progressive_result",
        "recommendation_response",
        "gift_request",
        "inquiry_details",
        "culture_product_id",
        "selected_product_id",
        "customization_inquiry",
        "customization_concept",
    ):
        st.session_state.pop(key, None)


def _restart() -> None:
    for key in list(st.session_state):
        if key not in {"entry_mode", "dialogue_parser_choice"}:
            del st.session_state[key]
    st.session_state["ui_stage"] = "describe"
    st.session_state["hero_request_text"] = ""


def _clear_form_widget_state(prefix: str) -> None:
    for key in tuple(st.session_state):
        if key.startswith(f"{prefix}_"):
            del st.session_state[key]


def _merge_conversation_follow_up() -> None:
    conversation = st.session_state.get("conversation_state")
    follow_up = str(st.session_state.get("conversation_follow_up", ""))
    if not isinstance(conversation, ConversationState):
        st.session_state["dialogue_error"] = "当前没有可继续的对话。"
        return
    try:
        turn = process_turn(
            conversation,
            follow_up,
            mode=st.session_state.get("dialogue_mode", "deterministic_demo"),
        )
    except RequestValidationError as exc:
        st.session_state["dialogue_error"] = str(exc)
        return
    updated = turn.state.accumulated_request
    if updated is None:
        st.session_state["dialogue_error"] = "本轮未形成可校验的需求更新。"
        return
    _clear_after_parse()
    _clear_form_widget_state("confirm")
    st.session_state.pop("dialogue_error", None)
    st.session_state["conversation_follow_up"] = ""
    st.session_state["conversation_state"] = turn.state
    st.session_state["pending_request"] = updated


def _confirm_and_recommend() -> None:
    parsed = st.session_state.get("pending_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        st.session_state["confirm_error"] = "当前没有可确认的结构化需求。"
        return
    try:
        confirmed = parsed_from_widgets("confirm", parsed)
        _, products = load_catalog()
        progressive = recommend_progressively(products, confirmed)
    except (RequestValidationError, DataValidationError) as exc:
        st.session_state["confirm_error"] = str(exc)
        return
    _clear_after_parse()
    st.session_state.pop("confirm_error", None)
    st.session_state["pending_request"] = confirmed
    st.session_state["confirmed_customer_request"] = confirmed
    st.session_state["progressive_result"] = progressive
    st.session_state["recommendation_response"] = progressive.response
    st.session_state["inquiry_details"] = to_inquiry_details(confirmed)
    if progressive.request_by_product:
        first_id = next(iter(progressive.request_by_product))
        st.session_state["gift_request"] = progressive.request_by_product[first_id]
    _set_stage("recommend")


def _choose_example(text: str) -> None:
    st.session_state["hero_request_text"] = text


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _money_or_pending(fen: int | None) -> str:
    return _money(fen) if fen is not None else "待确认"


def _yuan_to_fen(value: float) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_FLOOR))


def _inquiry_context(parsed: ParsedCustomerRequest, request: GiftRequest) -> InquiryRequestContext:
    """Keep the recommendation proxy separate from customer-confirmed inquiry facts."""

    def known(field_name: str) -> bool:
        return field_name not in parsed.uncertain_fields

    budget_is_known = parsed.budget_per_item is not None and known("budget_per_item")
    budget_max_fen = request.unit_budget_max_fen if budget_is_known else None
    total_budget_max_fen = (
        _yuan_to_fen(parsed.total_budget)
        if parsed.total_budget is not None and known("total_budget")
        else budget_max_fen * parsed.quantity
        if budget_max_fen is not None and parsed.quantity is not None and known("quantity")
        else None
    )
    return InquiryRequestContext(
        unit_budget_max_fen=budget_max_fen,
        budget_total_max_fen=total_budget_max_fen,
        quantity=parsed.quantity if known("quantity") else None,
        recipient_tags=((parsed.recipient,) if parsed.recipient and known("recipient") else ()),
        occasion_tags=((parsed.scene,) if parsed.scene and known("scene") else ()),
        style_tags=(parsed.style_preferences if known("style_preferences") else ()),
        meaning_tags=(parsed.symbolism_preferences if known("symbolism_preferences") else ()),
        customization_required=(
            parsed.customization_required if known("customization_required") else None
        ),
        required_customization_types=(
            parsed.customization_types if known("customization_types") else ()
        ),
        logo_required=parsed.logo_required if known("logo_required") else None,
        international_shipping_required=(
            parsed.international_shipping_required
            if known("international_shipping_required")
            else None
        ),
        available_lead_days=(
            parsed.required_delivery_days if known("required_delivery_days") else None
        ),
    )


def _known_customer_fields(parsed: ParsedCustomerRequest) -> frozenset[str]:
    values = {
        "budget_per_item": parsed.budget_per_item,
        "quantity": parsed.quantity,
        "customization_required": parsed.customization_required,
        "logo_required": parsed.logo_required,
        "required_delivery_days": parsed.required_delivery_days,
        "international_shipping_required": parsed.international_shipping_required,
    }
    return frozenset(
        field
        for field, value in values.items()
        if value is not None and field not in parsed.uncertain_fields
    )


def _render_describe() -> None:
    render_hero()
    render_progress("describe")
    browse_col, _ = st.columns([1, 2])
    if browse_col.button(
        "浏览 20 件非遗礼赠产品",
        key="open_reference_catalog",
        width="stretch",
    ):
        _set_stage("catalog")
        st.rerun()
    mode = st.radio(
        "选择需求录入方式",
        ("AI 描述需求", "精准填写需求"),
        horizontal=True,
        key="entry_mode",
        label_visibility="collapsed",
    )
    if mode == "精准填写需求":
        section_intro("PRECISE INPUT", "精准填写礼赠需求", "先填写关键条件，其他偏好可以按需展开。")
        if render_structured_form(prefix="detail", submit_label="确认这些需求"):
            try:
                parsed = parsed_from_widgets("detail")
            except RequestValidationError as exc:
                st.error(str(exc))
            else:
                _clear_after_parse()
                st.session_state.pop("conversation_state", None)
                st.session_state["pending_request"] = parsed
                _set_stage("confirm")
                st.rerun()
        return

    st.markdown("### 用一句话，说出这次礼赠需求")
    example_columns = st.columns(3)
    for column, example in zip(example_columns, EXAMPLES, strict=True):
        column.button(
            example,
            key=f"example_{EXAMPLES.index(example)}",
            on_click=_choose_example,
            args=(example,),
            width="stretch",
        )
    st.text_area(
        "礼赠需求描述",
        key="hero_request_text",
        height=150,
        placeholder="例如：给 20 位美国合作伙伴准备商务答谢礼物，每件预算 500 元……",
        label_visibility="collapsed",
    )
    parser_label = st.radio(
        "解析方式",
        ("自动（优先 DeepSeek）", "确定性演示模式"),
        horizontal=True,
        key="dialogue_parser_choice",
    )
    primary, demo = st.columns([2, 1])
    start = primary.button("开始智能选礼", type="primary", width="stretch")
    demo_clicked = demo.button(
        "体验企业海外礼赠案例",
        width="stretch",
        on_click=_choose_example,
        args=(DEMO_CASE,),
    )
    if demo_clicked:
        start = True
    if not start:
        return
    text = st.session_state.get("hero_request_text", "")
    mode_code = (
        "deterministic_demo"
        if demo_clicked
        else "auto"
        if parser_label.startswith("自动")
        else "deterministic_demo"
    )
    try:
        with st.spinner("正在理解礼赠需求…"):
            turn = process_turn(new_conversation(), text, mode=mode_code)
    except RequestValidationError as exc:
        st.error(str(exc))
        return
    parsed = turn.state.accumulated_request
    if parsed is None:
        st.error("暂时无法形成结构化需求，请修改描述后重试。")
        return
    _clear_after_parse()
    st.session_state["conversation_state"] = turn.state
    st.session_state["dialogue_mode"] = mode_code
    st.session_state["pending_request"] = parsed
    _set_stage("confirm")
    st.rerun()


def _render_confirm() -> None:
    render_progress("confirm")
    parsed = st.session_state.get("pending_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        _set_stage("describe")
        st.rerun()
    section_intro(
        "AI UNDERSTANDING",
        "AI 已理解您的礼赠需求",
        "请核对关键信息。缺失内容可以补充，也可以保留为空并查看探索性推荐。",
    )
    if parsed.parser_mode == "deterministic_demo":
        st.info("当前使用演示解析模式，以下内容仍需由您确认。")
    else:
        st.success("本次使用 AI 解析，结果已经过本地字段校验。")
    conversation = st.session_state.get("conversation_state")
    if isinstance(conversation, ConversationState):
        with st.expander("连续对话记录与补充", expanded=True):
            for message in conversation.messages:
                speaker = "您" if message.role == "user" else "礼赠顾问"
                st.markdown(f"**{speaker}：** {message.content}")
            st.text_input(
                "继续补充或修正需求",
                key="conversation_follow_up",
                placeholder="例如：数量改为 30 件，每件预算不超过 500 元。",
            )
            st.button(
                "合并这条补充",
                key="merge_conversation_follow_up",
                on_click=_merge_conversation_follow_up,
            )
            if error := st.session_state.pop("dialogue_error", None):
                st.error(error)
    render_requirement_summary(parsed)
    if parsed.clarification_questions:
        with st.expander("建议补充的信息", expanded=True):
            for question in parsed.clarification_questions:
                st.write(f"• {question}")
    st.markdown("### 修改或补充信息")
    submitted = render_structured_form(
        prefix="confirm", parsed=parsed, submit_label="保存修改并查看推荐"
    )
    if error := st.session_state.pop("confirm_error", None):
        st.error(error)
    back, confirm = st.columns([1, 2])
    back.button(
        "返回修改需求",
        width="stretch",
        on_click=_set_stage,
        args=("describe",),
    )
    confirm.button(
        "确认并查看推荐",
        type="primary",
        width="stretch",
        on_click=_confirm_and_recommend,
    )
    if submitted:
        _confirm_and_recommend()
        st.rerun()
    with st.expander("开发调试信息", expanded=False):
        st.json(asdict(parsed), expanded=False)


def _render_recommend() -> None:
    render_progress("recommend")
    progressive = st.session_state.get("progressive_result")
    parsed = st.session_state.get("confirmed_customer_request")
    if not isinstance(progressive, ProgressiveRecommendationResult) or not isinstance(
        parsed, ParsedCustomerRequest
    ):
        _set_stage("describe")
        st.rerun()
    section_intro(
        "CURATED FOR YOU",
        "为您推荐的非遗礼赠方案",
        "推荐综合考虑预算、对象、场景、风格、文化寓意、定制、数量和交付条件。",
    )
    response = progressive.response
    overview, coverage, confidence, mode = st.columns(4)
    overview.metric("满足明确硬约束", f"{len(response.recommendations)} 件")
    coverage.metric("需求信息覆盖", f"{progressive.information_coverage:.0%}")
    confidence.metric("当前置信度", progressive.confidence_level)
    mode.metric("推荐方式", MODE_LABELS[progressive.mode])
    with st.expander("查看当前需求摘要"):
        render_requirement_summary(parsed)
    st.button(
        "重新调整需求",
        width="stretch",
        on_click=_set_stage,
        args=("confirm",),
    )
    if not response.recommendations:
        st.error("当前没有满足全部明确条件的现有产品，我们不会强行推荐。")
        conflict_col, suggestion_col = st.columns(2)
        with conflict_col:
            st.markdown("#### 主要冲突")
            for conflict in response.primary_conflicts:
                st.write(f"• {conflict}")
        with suggestion_col:
            st.markdown("#### 可调整方向")
            for suggestion in response.adjustment_suggestions:
                st.write(f"• {suggestion}")
        st.markdown("#### 接近条件的参考方案")
        st.caption("以下方案存在明确冲突，仅用于帮助调整需求，不属于合格推荐。")
        for alternative in progressive.alternatives:
            product = alternative.recommendation.product
            with st.container(border=True):
                st.markdown(f"**{product.product_name_zh}**")
                st.warning("；".join(alternative.conflicts))
        if st.button("生成待商家评估的定制方向"):
            details = to_inquiry_details(parsed)
            request = next(iter(progressive.request_by_product.values()))
            st.session_state["customization_concept"] = build_customization_concept(
                request,
                details,
                response,
                customer_context=_inquiry_context(parsed, request),
            )
        if concept := st.session_state.get("customization_concept"):
            st.warning(CONCEPT_DISCLAIMER)
            st.json(concept, expanded=False)
        return
    participating = frozenset(progressive.participating_dimensions)
    known_customer_fields = _known_customer_fields(parsed)
    for rank, recommendation in enumerate(response.recommendations, start=1):
        request = progressive.request_by_product[recommendation.product.product_id]
        action = render_product_card(
            rank,
            recommendation,
            request,
            participating,
            known_customer_fields,
        )
        if action:
            product_id = recommendation.product.product_id
            st.session_state["culture_product_id"] = product_id
            if action == "select":
                st.session_state["selected_product_id"] = product_id
            _set_stage("culture")
            st.rerun()


def _find_recommendation(product_id: str) -> Recommendation | None:
    progressive = st.session_state.get("progressive_result")
    if not isinstance(progressive, ProgressiveRecommendationResult):
        return None
    return next(
        (
            item
            for item in progressive.response.recommendations
            if item.product.product_id == product_id
        ),
        None,
    )


def _render_culture(bundle: DataBundle) -> None:
    render_progress("culture")
    product_id = st.session_state.get("culture_product_id")
    recommendation = _find_recommendation(str(product_id))
    if recommendation is None:
        _set_stage("recommend")
        st.rerun()
    product = recommendation.product
    content = generate_bilingual_content(product, bundle.product_texts)
    section_intro(
        "CULTURAL STORY",
        product.product_name_zh,
        "从文化表达、工艺资料与定制方向理解这件礼物。所有未完成审核的信息均明确标记。",
    )
    image, overview = st.columns([1, 1.5], gap="large")
    with image:
        product_image(product.image_path, product.image_alt_zh)
    with overview:
        st.caption(product.product_name_en)
        st.markdown(f"### {_money(product.price_min_fen)}–{_money(product.price_max_fen)}")
        st.write(f"尺寸信息：{product.dimensions_text}")
        st.write(f"材料信息：{product.material_text}")
        badges([("基于现有产品资料", "ok"), ("文化文案待商家审核", "wait")])
    zh, en, craft, custom = st.tabs(
        ("中文文化介绍", "English Cultural Story", "工艺与依据", "定制建议")
    )
    with zh:
        st.markdown(f"#### {content.zh.cultural_story}")
        st.write(content.zh.craft_summary)
        st.info(content.zh.meaning_summary)
    with en:
        st.markdown(f"#### {content.en.cultural_story}")
        st.write(content.en.craft_summary)
        st.info(content.en.meaning_summary)
    with craft:
        st.write(f"**工艺信息**　{content.zh.craft_summary}")
        st.write(f"**文化寓意**　{content.zh.meaning_summary}")
        matched_context = "、".join(TAG_LABELS.get(tag, tag) for tag in recommendation.matched_tags)
        st.write(f"**适用对象与场景**　{matched_context or '待用户确认'}")
        with st.expander("查看推荐依据与数据来源"):
            st.write(f"资料说明：{content.zh.source_note}")
            st.write(f"数据版本：{product.data_version}")
            st.write(f"审核状态：{content.zh.review_status}")
            st.caption(f"图片许可：{product.image_license}")
            st.link_button("查看图片参考来源", product.reference_source_url)
            if content.pending_confirmations:
                st.warning("待确认字段：" + "、".join(content.pending_confirmations))
    with custom:
        parsed = st.session_state.get("confirmed_customer_request")
        if isinstance(parsed, ParsedCustomerRequest):
            st.write(f"定制主题：{parsed.requested_theme or '待商家确认'}")
            st.write(f"题字内容：{parsed.requested_text or '待商家确认'}")
            st.write(f"包装要求：{parsed.packaging_requirement or '待商家确认'}")
        st.caption("具体可制作范围、报价与附加工期由商家确认。")
    back, select = st.columns([1, 2])
    back.button(
        "返回查看其他方案",
        width="stretch",
        on_click=_set_stage,
        args=("recommend",),
    )
    selected = st.session_state.get("selected_product_id") == product.product_id
    label = "继续生成商家需求单" if selected else "选择此方案并生成需求单"
    if select.button(label, type="primary", width="stretch"):
        st.session_state["selected_product_id"] = product.product_id
        _set_stage("inquiry")
        st.rerun()


def _build_inquiry_for_selection(
    bundle: DataBundle,
) -> tuple[dict[str, Any], Recommendation, GiftRequest, InquiryDetails, BilingualContent]:
    product_id = str(st.session_state.get("selected_product_id", ""))
    recommendation = _find_recommendation(product_id)
    progressive = st.session_state.get("progressive_result")
    parsed = st.session_state.get("confirmed_customer_request")
    if (
        recommendation is None
        or not isinstance(progressive, ProgressiveRecommendationResult)
        or not isinstance(parsed, ParsedCustomerRequest)
    ):
        raise ValueError("尚未选择有效产品")
    request = progressive.request_by_product[product_id]
    details = to_inquiry_details(parsed)
    content = generate_bilingual_content(recommendation.product, bundle.product_texts)
    cached = st.session_state.get("customization_inquiry")
    if (
        not isinstance(cached, dict)
        or cached.get("selected_products", [{}])[0].get("product_id") != product_id
    ):
        cached = build_customization_inquiry(
            request,
            recommendation,
            content,
            details,
            customer_context=_inquiry_context(parsed, request),
        )
        st.session_state["customization_inquiry"] = cached
    return cached, recommendation, request, details, content


def _inquiry_summary_text(inquiry: dict[str, Any]) -> str:
    snapshot = inquiry["request_snapshot"]
    custom = inquiry["customization_brief"]
    delivery = inquiry["delivery"]
    product = inquiry["selected_products"][0]
    quantity = snapshot["quantity"]
    logo_required = custom["logo_required"]
    return "\n".join(
        (
            f"飞颐礼遇商家需求摘要｜{product['product_name_zh']}",
            f"数量：{f'{quantity} 件' if quantity is not None else '待确认'}",
            f"单件预算上限：{_money_or_pending(snapshot['unit_budget_max_fen'])}",
            f"定制主题：{custom['theme']}",
            f"题字：{custom['inscription']}",
            "Logo："
            + (
                "需要"
                if logo_required is True
                else "不需要"
                if logo_required is False
                else "待确认"
            ),
            f"包装：{custom['packaging']}",
            f"目的地：{delivery['destination']}",
            f"交付要求：{delivery['delivery_requirement']}",
            "待商家确认：" + "；".join(inquiry["open_questions"]),
        )
    )


def _render_inquiry(bundle: DataBundle) -> None:
    render_progress("inquiry")
    try:
        inquiry, recommendation, _request, details, _ = _build_inquiry_for_selection(bundle)
    except ValueError:
        _set_stage("recommend")
        st.rerun()
    section_intro(
        "MERCHANT BRIEF",
        "商家定制需求单",
        "已把客户语言整理为可核对、可下载的商务需求摘要。最终方案由商家确认。",
    )
    st.warning(f"{inquiry['disclaimer_zh']}\n\n{inquiry['disclaimer_en']}")
    product = recommendation.product
    snapshot = inquiry["request_snapshot"]
    customization = inquiry["customization_brief"]
    delivery = inquiry["delivery"]
    with st.container(border=True):
        st.caption("选定方案")
        st.markdown(f"## {product.product_name_zh}")
        st.caption(product.product_name_en)
        first, second, third = st.columns(3)
        first.metric(
            "采购数量",
            f"{snapshot['quantity']} 件" if snapshot["quantity"] is not None else "待确认",
        )
        second.metric("单件预算上限", _money_or_pending(snapshot["unit_budget_max_fen"]))
        third.metric("预算总额上限", _money_or_pending(snapshot["budget_total_max_fen"]))
    request_col, delivery_col = st.columns(2)
    with request_col, st.container(border=True):
        st.markdown("#### 礼赠与定制")
        customer_labels = {code: label for label, code in CUSTOMER_TYPES.items()}
        st.write(f"客户类型：{customer_labels.get(details.customer_type, details.customer_type)}")
        st.write(
            "赠礼对象："
            + (
                "、".join(TAG_LABELS.get(tag, tag) for tag in snapshot["recipient_tags"])
                or "待商家确认"
            )
        )
        st.write(
            "使用场景："
            + (
                "、".join(TAG_LABELS.get(tag, tag) for tag in snapshot["occasion_tags"])
                or "待商家确认"
            )
        )
        st.write(f"定制主题：{details.customization_theme or '待商家确认'}")
        st.write(f"题字内容：{details.inscription_text or '待商家确认'}")
        st.write(f"包装要求：{details.packaging_requirement or '待商家确认'}")
    with delivery_col, st.container(border=True):
        st.markdown("#### 交付与内容")
        destination = {"United States": "美国"}.get(details.destination, details.destination)
        st.write(f"目的地：{destination or '待商家确认'}")
        st.write(
            f"期望交付：{delivery['available_lead_days']} 天内"
            if delivery["available_lead_days"] is not None
            else "期望交付：待商家确认"
        )
        st.write(f"文化介绍：{details.output_language}")
        st.write(
            "Logo："
            + (
                "需要"
                if customization["logo_required"] is True
                else "不需要"
                if customization["logo_required"] is False
                else "待商家确认"
            )
        )
    with st.expander("待商家确认信息", expanded=True):
        for question in inquiry["open_questions"]:
            st.write(f"• {question}")
    summary = _inquiry_summary_text(inquiry)
    render_copyable_summary(summary)
    st.download_button(
        "下载需求单 JSON",
        data=inquiry_to_json(inquiry),
        file_name=f"{inquiry['inquiry_id']}.json",
        mime="application/json",
        width="stretch",
    )
    back, restart = st.columns(2)
    back.button(
        "返回查看其他方案",
        width="stretch",
        on_click=_set_stage,
        args=("recommend",),
    )
    restart.button(
        "重新开始",
        type="primary",
        width="stretch",
        on_click=_restart,
    )
    with st.expander("开发调试信息", expanded=False):
        st.json(inquiry, expanded=False)


def _render_reference_catalog() -> None:
    top_left, top_right = st.columns([2, 1])
    with top_left:
        section_intro(
            "CURATED HERITAGE GIFT CATALOGUE",
            "非遗礼赠产品库",
            "20 件产品均已配置图片、方案价格、交期、文化介绍与推荐标签，"
            "并保留图片许可和原始资料页。",
        )
    top_right.button(
        "返回智能选礼",
        width="stretch",
        on_click=_set_stage,
        args=("describe",),
    )

    st.markdown(
        '<div class="hl-catalog-note"><strong>资料边界</strong> '
        "图片与历史信息来自可追溯的开放馆藏；商品名称、方案价格、数量、交期和定制能力由飞颐礼遇整理，"
        "并作为推荐引擎的结构化产品数据。馆藏原物仅作设计与文化资料参考，并非本平台在售商品。</div>",
        unsafe_allow_html=True,
    )
    try:
        items = load_heritage_reference_catalog()
        _, products = load_catalog()
        products_by_id = {product.product_id: product for product in products}
        missing_products = sorted(
            item.demo_product_id for item in items if item.demo_product_id not in products_by_id
        )
        if missing_products:
            raise CatalogDataError("目录商品关联不存在：" + "、".join(missing_products))
    except CatalogDataError as exc:
        st.error("非遗礼赠产品库暂时无法加载。")
        with st.expander("技术信息"):
            st.code(str(exc))
        return
    render_catalog_gallery(items, products_by_id=products_by_id, project_root=ROOT)


def main() -> None:
    st.set_page_config(
        page_title="飞颐礼遇｜AI 非遗礼品顾问",
        page_icon="礼",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_theme()
    st.caption("MVP 演示数据 / MVP demo data：价格、数量、交期、运输和定制能力均需商家复核。")
    _init_state()
    try:
        bundle, _ = load_catalog()
    except DataValidationError as exc:
        st.error("产品资料暂时无法加载，请检查演示数据后重试。")
        with st.expander("技术信息"):
            st.code(str(exc))
        st.stop()
    stage = st.session_state["ui_stage"]
    if stage == "describe":
        _render_describe()
    elif stage == "confirm":
        _render_confirm()
    elif stage == "recommend":
        _render_recommend()
    elif stage == "culture":
        _render_culture(bundle)
    elif stage == "catalog":
        _render_reference_catalog()
    else:
        _render_inquiry(bundle)


if __name__ == "__main__":
    main()
