"""Single-page conversational gift advisor for HAHA｜飞颐礼遇."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from heritagelink.agent_models import (
    AgentRuntimeConfig,
    AgentSessionState,
    AgentTurnResult,
    CatalogSnapshot,
    RequestedAction,
    UserTurn,
)
from heritagelink.agent_orchestrator import run_agent_turn
from heritagelink.agent_trace import is_review_mode_enabled
from heritagelink.analytics import (
    AnalyticsSettings,
    create_choice_repository,
    new_anonymous_session_id,
)
from heritagelink.catalog import CatalogDataError, HeritageReferenceItem, load_reference_catalog
from heritagelink.content import BilingualContent
from heritagelink.conversation_state import (
    ConversationState,
    new_conversation,
)
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.inquiry import inquiry_to_json
from heritagelink.models import DataBundle, Product, Recommendation
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.choice_repository import ChoiceRepository
from heritagelink.request_parser import (
    ParsedCustomerRequest,
    RequestValidationError,
)
from heritagelink.ui.catalog_gallery import render_catalog_gallery
from heritagelink.ui.components import badges, product_image, render_hero, render_section_header
from heritagelink.ui.inspiration_cards import render_inspiration_cards
from heritagelink.ui.product_card import render_product_card
from heritagelink.ui.requirements import (
    MEANINGS,
    RECIPIENTS,
    SCENES,
    STYLES,
    parsed_from_widgets,
    render_structured_form,
)
from heritagelink.ui.theme import apply_theme

LOGGER = logging.getLogger(__name__)
SOURCE_URL_RE = re.compile(r"https://[^\s；;]+")
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "demo"
REFERENCE_CATALOG_PATH = ROOT / "data" / "catalog" / "heritage_products.csv"

TAG_LABELS = {
    **{value: key for key, value in RECIPIENTS.items()},
    **{value: key for key, value in SCENES.items()},
    **{value: key for key, value in STYLES.items()},
    **{value: key for key, value in MEANINGS.items()},
}


@st.cache_resource(show_spinner=False)
def load_catalog() -> tuple[DataBundle, tuple[Product, ...]]:
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


@st.cache_data(show_spinner=False)
def load_heritage_reference_catalog() -> tuple[HeritageReferenceItem, ...]:
    return load_reference_catalog(REFERENCE_CATALOG_PATH, project_root=ROOT)


@st.cache_resource(show_spinner=False)
def _configured_repository(settings: AnalyticsSettings) -> ChoiceRepository | None:
    try:
        return create_choice_repository(settings)
    except Exception:
        LOGGER.exception("匿名分析存储初始化失败")
        return None


def _repository() -> ChoiceRepository | None:
    override = st.session_state.get("_choice_repository_override")
    if override is not None:
        return override
    return _configured_repository(st.session_state["analytics_settings"])


def _init_state() -> None:
    settings = AnalyticsSettings.from_env()
    st.session_state.setdefault("ui_stage", "advisor")
    st.session_state.setdefault("conversation_state", new_conversation())
    st.session_state.setdefault("anonymous_session_id", new_anonymous_session_id())
    st.session_state.setdefault("session_started_at", datetime.now(UTC))
    st.session_state.setdefault("entry_source", "direct")
    st.session_state.setdefault("analytics_consent", False)
    st.session_state.setdefault("analytics_settings", settings)
    st.session_state.setdefault("show_requirement_editor", False)
    st.session_state.setdefault("agent_execution_trace", ())


def _clear_downstream() -> None:
    for key in (
        "recommendation_context",
        "progressive_result",
        "recommendation_response",
        "recommendation_event",
        "selected_product_id",
        "selection_event",
        "customization_inquiry",
        "grounded_content",
    ):
        st.session_state.pop(key, None)


def _agent_runtime() -> AgentRuntimeConfig:
    settings = st.session_state["analytics_settings"]
    return AgentRuntimeConfig(
        review_mode_enabled=is_review_mode_enabled(st.query_params),
        llm_enabled=os.getenv("LLM_ENABLED", "true").lower() == "true",
        analytics_enabled=settings.enabled,
        maximum_clarification_turns=5,
        app_version=settings.app_version,
    )


def _agent_state() -> AgentSessionState:
    state = st.session_state.get("conversation_state")
    if not isinstance(state, ConversationState):
        state = new_conversation()
    return AgentSessionState(
        anonymous_session_id=st.session_state["anonymous_session_id"],
        conversation_state=state,
        session_started_at=st.session_state["session_started_at"],
        entry_source=st.session_state.get("entry_source", "direct"),
        recommendation_context=st.session_state.get("recommendation_context"),
        recommendation_result=st.session_state.get("progressive_result"),
        recommendation_event=st.session_state.get("recommendation_event"),
        selected_product_id=st.session_state.get("selected_product_id"),
        selection_event=st.session_state.get("selection_event"),
        grounded_content=st.session_state.get("grounded_content"),
        final_plan=st.session_state.get("customization_inquiry"),
        consent_state=bool(st.session_state.get("analytics_consent")),
    )


def _catalog_snapshot() -> CatalogSnapshot:
    bundle, products = load_catalog()
    total = len(load_heritage_reference_catalog())
    return CatalogSnapshot(
        bundle=bundle,
        products=products,
        catalog_total=total,
        formally_recommendable=len(products),
        reference_only=max(0, total - len(products)),
        repository=_repository(),
    )


def _apply_agent_result(result: AgentTurnResult) -> None:
    state = result.updated_session_state
    st.session_state["conversation_state"] = state.conversation_state
    st.session_state["pending_request"] = state.accumulated_request
    st.session_state["entry_source"] = state.entry_source
    st.session_state["recommendation_context"] = state.recommendation_context
    st.session_state["progressive_result"] = state.recommendation_result
    st.session_state["recommendation_response"] = result.recommendation_response
    st.session_state["recommendation_event"] = state.recommendation_event
    st.session_state["selected_product_id"] = state.selected_product_id
    st.session_state["selection_event"] = state.selection_event
    st.session_state["grounded_content"] = state.grounded_content
    st.session_state["customization_inquiry"] = state.final_plan
    st.session_state["agent_execution_trace"] = result.execution_trace


def _run_agent(
    action: RequestedAction,
    *,
    text: str = "",
    source: str = "chat",
    product_id: str | None = None,
    structured_request: ParsedCustomerRequest | None = None,
) -> AgentTurnResult:
    turn = UserTurn(
        message_id=f"turn-{len(_agent_state().conversation_state.raw_user_texts) + 1}",
        text=text,
        submitted_at=datetime.now(UTC),
        requested_action=action,
        source=source,
        product_id=product_id,
        structured_request=structured_request,
    )
    result = run_agent_turn(turn, _agent_state(), _catalog_snapshot(), _agent_runtime())
    _apply_agent_result(result)
    return result


def _process_message(message: str, *, entry_source: str = "chat") -> None:
    try:
        action = (
            RequestedAction.RECOMMEND_NOW
            if entry_source == "recommend_now"
            else RequestedAction.CONTINUE_CONVERSATION
        )
        with st.spinner("正在从传统工艺中寻找合适的选择…"):
            _run_agent(action, text=message, source=entry_source)
    except (RequestValidationError, DataValidationError, ValueError) as exc:
        st.session_state["friendly_error"] = str(exc)


def _generate_recommendations() -> None:
    parsed = st.session_state.get("pending_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        return
    try:
        _run_agent(
            RequestedAction.ADJUST_REQUIREMENT,
            source="rematch",
            structured_request=parsed,
        )
    except (DataValidationError, ValueError):
        st.session_state["friendly_error"] = "产品资料暂时无法加载，请稍后再试。"


def _accept_structured_request(parsed: ParsedCustomerRequest) -> None:
    _run_agent(
        RequestedAction.ADJUST_REQUIREMENT,
        source="structured_form",
        structured_request=parsed,
    )


def _money(fen: int | None) -> str:
    return "可后续沟通" if fen is None else f"¥{fen / 100:,.0f}"


def _yuan_to_fen(value: float) -> int:
    return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_FLOOR))


def _friendly_value(value: Any, mapping: dict[str, str] | None = None) -> str | None:
    if value is None or value == "" or value == ():
        return None
    if isinstance(value, bool):
        return "需要" if value else "不需要"
    reverse = {code: label for label, code in (mapping or {}).items()}
    if isinstance(value, tuple):
        return "、".join(reverse.get(str(item), str(item)) for item in value)
    return reverse.get(str(value), str(value))


def _summary_items(parsed: ParsedCustomerRequest) -> list[tuple[str, str]]:
    rows = (
        ("赠礼对象", _friendly_value(parsed.recipient, RECIPIENTS)),
        ("使用场景", _friendly_value(parsed.scene, SCENES)),
        ("单件预算", f"¥{parsed.budget_per_item:,.0f}" if parsed.budget_per_item else None),
        ("数量", f"{parsed.quantity} 件" if parsed.quantity else None),
        ("风格方向", _friendly_value(parsed.style_preferences, STYLES)),
        ("文化寓意", _friendly_value(parsed.symbolism_preferences, MEANINGS)),
        ("定制要求", _friendly_value(parsed.customization_required)),
        ("Logo", _friendly_value(parsed.logo_required)),
        (
            "交付要求",
            f"{parsed.required_delivery_days} 天内" if parsed.required_delivery_days else None,
        ),
        ("目的地", parsed.destination),
    )
    return [(label, value) for label, value in rows if value]


def _quick_replies(question: str) -> tuple[str, ...]:
    if "预算" in question or "价" in question:
        return ("500元以内", "500–1000元", "1000–3000元", "我还没确定")
    if "风格" in question or "传统" in question:
        return ("庄重典雅", "现代新中式", "更有传统特色", "你帮我决定")
    if "数量" in question:
        return ("1件", "10件左右", "30件左右", "还没确定")
    return ("海外合作伙伴", "教授或老师", "长辈", "朋友")


def _render_conversation() -> None:
    state = st.session_state["conversation_state"]
    if not state.raw_user_texts:
        with st.container(key="landing_composer"):
            prompt = st.chat_input(
                "描述赠礼对象或场景…",
                key="landing_prompt",
            )
            if prompt:
                _process_message(prompt)
                st.rerun()
        render_inspiration_cards(ROOT, _process_message)
        return
    with st.container(key="conversation_thread"):
        render_section_header(
            "礼赠对话",
            kicker="CONVERSATION",
            section="conversation",
        )
        for message in state.messages:
            with st.chat_message(message.role):
                if message.role == "assistant":
                    st.caption("HAHA")
                st.write(message.content)
        if state.clarification_questions:
            st.caption("可以直接回答，也可以快速选择")
            with st.container(key="quick_reply_grid"):
                columns = st.columns(4)
                for index, reply in enumerate(_quick_replies(state.clarification_questions[0])):
                    if columns[index].button(reply, key=f"reply_{index}", width="stretch"):
                        _process_message(reply, entry_source="quick_reply")
                        st.rerun()
        with st.container(key="conversation_actions"):
            recommend, restart = st.columns(2)
            if recommend.button("先看看推荐", type="primary", width="stretch"):
                _process_message("请先为我推荐，我之后再调整。", entry_source="recommend_now")
                st.rerun()
            if restart.button("重新开始", width="stretch"):
                _run_agent(RequestedAction.RESTART, source="restart")
                st.session_state["show_requirement_editor"] = False
                st.rerun()
        if error := st.session_state.pop("friendly_error", None):
            st.info(error)


def _render_sticky_composer() -> None:
    st.markdown('<div class="hl-composer-safe-space"></div>', unsafe_allow_html=True)
    prompt = st.chat_input("继续描述你的想法…", key="conversation_prompt")
    if prompt:
        _process_message(prompt)
        st.rerun()


def _render_requirement_summary() -> None:
    parsed = st.session_state.get("pending_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        return
    context = st.session_state.get("recommendation_context")
    display = context.effective_request if isinstance(context, RecommendationContext) else parsed
    with st.container(key="requirement_summary"):
        render_section_header(
            "当前礼赠方向",
            kicker="GIFT BRIEF",
            section="requirements",
        )
        items = _summary_items(display)
        if items:
            tags = "".join(f"<span>{escape(value)}</span>" for _, value in items)
            st.markdown(f'<div class="hl-summary">{tags}</div>', unsafe_allow_html=True)
        else:
            st.caption("我们先从赠礼对象或场景开始，之后可以随时调整。")
        if isinstance(context, RecommendationContext):
            st.write(context.direction_summary)
        with st.container(key="requirement_actions"):
            edit, rematch = st.columns(2)
            if edit.button("调整需求", width="stretch"):
                st.session_state["show_requirement_editor"] = not st.session_state.get(
                    "show_requirement_editor", False
                )
                st.rerun()
            if rematch.button("重新匹配", width="stretch"):
                state = st.session_state["conversation_state"]
                st.session_state["conversation_state"] = replace(state, ready_to_recommend=True)
                _generate_recommendations()
                st.rerun()
        if st.session_state.get("show_requirement_editor"):
            with st.container(border=True, key="requirement_editor"):
                st.caption("只修改您希望调整的条件，留空项目不会被当作硬性要求。")
                if render_structured_form(
                    prefix="advisor_edit", parsed=display, submit_label="保存并重新匹配"
                ):
                    try:
                        updated = parsed_from_widgets("advisor_edit", display)
                    except RequestValidationError as exc:
                        st.info(str(exc))
                    else:
                        _accept_structured_request(updated)
                        st.session_state["show_requirement_editor"] = False
                        st.rerun()


def _known_customer_fields(parsed: ParsedCustomerRequest) -> frozenset[str]:
    return frozenset(
        name
        for name in (
            "budget_per_item",
            "quantity",
            "customization_required",
            "logo_required",
            "required_delivery_days",
            "international_shipping_required",
        )
        if getattr(parsed, name) is not None and name not in parsed.uncertain_fields
    )


def _render_recommendations(bundle: DataBundle) -> None:
    result = st.session_state.get("progressive_result")
    context = st.session_state.get("recommendation_context")
    event = st.session_state.get("recommendation_event")
    if not isinstance(result, ProgressiveRecommendationResult) or not isinstance(
        context, RecommendationContext
    ):
        return
    response = result.response
    count = len(response.recommendations)
    participating = frozenset(result.participating_dimensions)
    parsed = context.effective_request
    selected_id = st.session_state.get("selected_product_id")
    with st.container(key="recommendation_section"):
        result_state = "items" if response.recommendations else "no-match"
        st.markdown(
            f'<span class="hl-ui-marker" data-ui-result="{result_state}"></span>',
            unsafe_allow_html=True,
        )
        render_section_header(
            f"我为您挑选了 {count} 件更适合这次场景的作品",
            kicker="CURATED FOR YOU",
            copy="每一件都来自当前可推荐目录；您可以选择，也可以继续聊天调整方向。",
            section="recommendations",
        )
        st.checkbox(
            "允许匿名保存本次礼品偏好和选择，用于优化未来推荐。",
            key="analytics_consent",
            help="不保存姓名、联系方式或完整聊天原文；不同意也可以正常使用。",
        )
        if not response.recommendations:
            st.info("目前还没有作品同时满足这些条件。")
            if response.primary_conflicts:
                st.markdown("**主要限制来自：**")
                for conflict in response.primary_conflicts[:3]:
                    st.write(f"• {conflict.split('（', 1)[0]}")
            no_match_actions = (
                ("放宽预算", "可以适当放宽预算，请按接近的方案重新推荐。"),
                ("调整交期", "交期可以放宽，请重新为我匹配。"),
                ("看看接近的方案", "请告诉我哪些条件最值得放宽，以便看看接近的方案。"),
            )
            with st.container(key="no_match_actions"):
                actions = st.columns(3)
                for column, (label, text) in zip(actions, no_match_actions, strict=True):
                    if column.button(label, width="stretch"):
                        _process_message(text, entry_source="no_match_adjustment")
                        st.rerun()
            return
        with st.container(key="recommendation_grid"):
            columns = st.columns(3)
            for rank, recommendation in enumerate(response.recommendations, start=1):
                request = result.request_by_product[recommendation.product.product_id]
                with columns[(rank - 1) % 3]:
                    if render_product_card(
                        rank,
                        recommendation,
                        request,
                        participating,
                        _known_customer_fields(parsed),
                        selected=recommendation.product.product_id == selected_id,
                    ):
                        _select_product(recommendation.product.product_id)
                        st.rerun()
    if selected_id:
        _render_selected_plan(bundle, str(selected_id), event)


def _select_product(product_id: str) -> None:
    _run_agent(
        RequestedAction.SELECT_PRODUCT,
        source="product_card",
        product_id=product_id,
    )


def _find_recommendation(product_id: str) -> Recommendation | None:
    result = st.session_state.get("progressive_result")
    if not isinstance(result, ProgressiveRecommendationResult):
        return None
    return next(
        (item for item in result.response.recommendations if item.product.product_id == product_id),
        None,
    )


def _render_selected_plan(
    bundle: DataBundle, product_id: str, recommendation_event: object
) -> None:
    recommendation = _find_recommendation(product_id)
    context = st.session_state.get("recommendation_context")
    if recommendation is None or not isinstance(context, RecommendationContext):
        return
    with st.container(key="selected_plan"):
        render_section_header(
            "已选礼物",
            kicker="SELECTED GIFT",
            section="selected-plan",
        )
        st.markdown(
            '<div class="hl-selected-copy"><strong>HAHA</strong><br>'
            "这件作品比较符合您目前的礼赠需求。"
            "接下来我可以根据对象、数量和定制要求，整理一份完整的礼品方案。</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True, key="selected_plan_card"):
            image, detail = st.columns([1, 1.5])
            with image:
                product_image(
                    recommendation.product.image_path,
                    recommendation.product.image_alt_zh,
                )
            with detail:
                st.markdown(f"### {recommendation.product.product_name_zh}")
                st.write(context.direction_summary)
                budget = context.effective_request.budget_per_item
                budget_fen = _yuan_to_fen(budget) if budget else None
                st.write(
                    f"数量：{context.effective_request.quantity or '可后续沟通'}　·　"
                    f"单件预算：{_money(budget_fen)}"
                )
            with st.container(key="selected_plan_actions"):
                change, adjust, generate = st.columns(3)
                if change.button("换一件", width="stretch"):
                    st.session_state.pop("selected_product_id", None)
                    st.session_state.pop("selection_event", None)
                    st.session_state.pop("customization_inquiry", None)
                    st.rerun()
                if adjust.button("继续调整", width="stretch"):
                    st.session_state["show_requirement_editor"] = True
                    st.rerun()
                if generate.button("生成我的礼品方案", type="primary", width="stretch"):
                    _run_agent(RequestedAction.GENERATE_PLAN, source="generate_plan")
                    st.rerun()
    inquiry = st.session_state.get("customization_inquiry")
    if isinstance(inquiry, dict):
        _render_final_scheme(bundle, recommendation, inquiry, context)


def _render_source_note(note: str) -> None:
    """Render a source URL without absorbing the following punctuation into the link."""
    match = SOURCE_URL_RE.search(note)
    if not match:
        st.caption(note)
        return
    before = escape(note[: match.start()])
    url = escape(match.group(), quote=True)
    after = escape(note[match.end() :])
    st.markdown(
        f'<small>{before}<a href="{url}" target="_blank">馆藏资料页 / Source</a>{after}</small>',
        unsafe_allow_html=True,
    )


def _render_final_scheme(
    bundle: DataBundle,
    recommendation: Recommendation,
    inquiry: dict[str, Any],
    context: RecommendationContext,
) -> None:
    parsed = context.effective_request
    content = st.session_state.get("grounded_content")
    if not isinstance(content, BilingualContent):
        return
    with st.container(key="final_plan"):
        render_section_header(
            "您的专属礼赠方案",
            kicker="PERSONAL GIFT PLAN",
            section="final-plan",
        )
        badges([("礼品已选定", "ok"), ("可继续调整", "wait")])
        cover, summary = st.columns([1, 1.45])
        with cover:
            product_image(recommendation.product.image_path, recommendation.product.image_alt_zh)
        plan_items = (
            ("产品", recommendation.product.product_name_zh),
            ("适合对象", _friendly_value(parsed.recipient, RECIPIENTS) or "可继续沟通"),
            ("场景", _friendly_value(parsed.scene, SCENES) or "可继续沟通"),
            (
                "预算",
                f"¥{parsed.budget_per_item:,.0f} / 件"
                if parsed.budget_per_item
                else "可继续沟通",
            ),
            (
                "定制方向",
                " · ".join(
                    filter(
                        None,
                        (
                            "Logo" if parsed.logo_required else None,
                            parsed.requested_text,
                            "双语说明卡",
                        ),
                    )
                ),
            ),
            ("下一步", "向商家确认交期和最终报价"),
        )
        with summary:
            markup = "".join(
                '<div class="hl-plan-item">'
                f"<small>{escape(label)}</small>"
                f"<strong>{escape(value or '按需沟通')}</strong></div>"
                for label, value in plan_items
            )
            st.markdown(f'<div class="hl-plan-grid">{markup}</div>', unsafe_allow_html=True)
        st.markdown("### 文化表达")
        zh, en = st.tabs(("中文文化介绍", "English Cultural Story"))
        with zh:
            st.write(content.zh.cultural_story)
            _render_source_note(content.zh.source_note)
        with en:
            st.write(content.en.cultural_story)
            _render_source_note(content.en.source_note)
        with st.container(key="final_plan_actions"):
            download, adjust = st.columns(2)
            with download:
                st.download_button(
                    "下载礼品方案",
                    data=inquiry_to_json(inquiry),
                    file_name=f"{inquiry['inquiry_id']}.json",
                    mime="application/json",
                    width="stretch",
                )
            if adjust.button("继续调整", key="adjust_final_plan", width="stretch"):
                st.session_state["show_requirement_editor"] = True
                st.rerun()


def _render_secondary_form() -> None:
    with st.expander("我想直接填写需求"):
        if render_structured_form(prefix="direct", submit_label="填写完成，开始匹配"):
            try:
                parsed = parsed_from_widgets("direct")
            except RequestValidationError as exc:
                st.info(str(exc))
            else:
                _accept_structured_request(parsed)
                st.rerun()


def _render_catalog() -> None:
    with st.expander("浏览完整礼品目录"):
        try:
            items = load_heritage_reference_catalog()
            _, products = load_catalog()
            render_catalog_gallery(
                items,
                products_by_id={product.product_id: product for product in products},
                project_root=ROOT,
            )
        except CatalogDataError:
            st.info("礼品目录暂时无法加载，请稍后再试。")


def _render_service_note() -> None:
    with st.expander("数据与服务说明"):
        st.write(
            "产品展示依据当前目录资料；实际价格、制作、定制与交付细节以最终服务方案为准。"
            "文化介绍保留资料来源，不使用夸张或虚构的产品事实。"
        )
        st.write(
            "匿名偏好分析完全自愿，不保存姓名、联系方式或完整聊天原文；不同意不会影响推荐和方案生成。"
        )


def _render_agent_trace() -> None:
    if not is_review_mode_enabled(st.query_params):
        return
    traces = st.session_state.get("agent_execution_trace", ())
    st.markdown("## Agent 执行轨迹")
    if not traces:
        st.caption("完成一轮交互后，这里会显示当前会话内的脱敏 Skill 轨迹。")
        return
    for trace in traces:
        icon = "✓" if trace.status.value in {"success", "fallback"} else "–"
        with st.expander(
            f"{icon} Skill {trace.sequence_number}：{trace.skill_name} · {trace.status.value}"
        ):
            st.write(f"调用原因：{trace.trigger_reason}")
            st.json({"输入摘要": trace.input_summary, "输出摘要": trace.output_summary})
            if trace.fallback_used:
                st.write(f"安全回退：{trace.fallback_reason or '已启用'}")
            st.write(f"执行时间：{trace.duration_ms:.3f} ms")
            for check in trace.safety_checks:
                marker = "✓" if check.passed else "!"
                st.write(f"{marker} {check.check_id}：{check.summary}")


def main() -> None:
    st.set_page_config(
        page_title="HAHA｜飞颐礼遇｜AI 非遗出海平台",
        page_icon="礼",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    apply_theme()
    _init_state()
    try:
        bundle, _ = load_catalog()
    except DataValidationError:
        st.info("产品资料暂时无法加载，请稍后再试。")
        st.stop()
    state = st.session_state["conversation_state"]
    render_hero(compact=bool(state.raw_user_texts))
    _render_conversation()
    _render_requirement_summary()
    _render_recommendations(bundle)
    if state.raw_user_texts:
        with st.container(key="secondary_tools"):
            _render_secondary_form()
            _render_catalog()
            _render_service_note()
    _render_agent_trace()
    if state.raw_user_texts:
        _render_sticky_composer()


if __name__ == "__main__":
    main()
