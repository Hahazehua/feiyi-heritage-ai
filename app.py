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
from heritagelink.artisan_studio import (
    build_passport,
    confirm_facts,
    create_draft,
    enrich_draft,
    merge_artisan_values,
    simulate_review_approval,
    submit_for_review,
    update_bilingual_draft,
)
from heritagelink.catalog import CatalogDataError, HeritageReferenceItem, load_reference_catalog
from heritagelink.catalog_eligibility import is_recommendation_eligible
from heritagelink.comparison_models import ProductComparisonResult
from heritagelink.config import deepseek_is_configured
from heritagelink.content import BilingualContent
from heritagelink.conversation_state import (
    ConversationState,
    new_conversation,
)
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.heritage_passport import build_catalog_passports
from heritagelink.heritage_passport_models import (
    ArtisanProductDraft,
    HeritagePassport,
    PublicationStatus,
)
from heritagelink.inquiry import inquiry_to_json
from heritagelink.llm_client import DeepSeekClient
from heritagelink.models import DataBundle, Product, Recommendation
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.choice_repository import ChoiceRepository
from heritagelink.repositories.memory_artisan_draft_repository import (
    MemoryArtisanDraftRepository,
)
from heritagelink.request_parser import (
    ParsedCustomerRequest,
    RequestValidationError,
)
from heritagelink.shopping_turn_router import route_shopping_turn
from heritagelink.ui.artisan_studio import (
    render_artisan_hero,
    render_artisan_journey,
    render_artisan_progress,
    render_artisan_section,
)
from heritagelink.ui.catalog_gallery import render_catalog_gallery
from heritagelink.ui.comparison import render_product_comparison
from heritagelink.ui.components import badges, product_image, render_hero
from heritagelink.ui.heritage_passport import render_heritage_passport
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

QUICK_STARTS = (
    "送海外合作伙伴",
    "送教授或长辈",
    "企业周年纪念",
    "我还没有明确想法",
)
QUICK_TEXT = {
    "送海外合作伙伴": "我想给海外合作伙伴准备一份有中国文化特色的礼物。",
    "送教授或长辈": "我想给教授或长辈准备一份典雅、有文化故事的礼物。",
    "企业周年纪念": "我们正在准备企业周年纪念礼品。",
    "我还没有明确想法": "我还没有明确想法，想先听听你的建议。",
}

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


@st.cache_resource(show_spinner=False)
def _configured_artisan_repository() -> MemoryArtisanDraftRepository:
    return MemoryArtisanDraftRepository()


def _artisan_repository() -> MemoryArtisanDraftRepository:
    override = st.session_state.get("_artisan_draft_repository_override")
    if override is not None:
        return override
    return _configured_artisan_repository()


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
    st.session_state.setdefault("application_execution_trace", ())
    st.session_state.setdefault("comparison_history", ())
    st.session_state.setdefault("artisan_session_id", new_anonymous_session_id())
    requested_mode = str(st.query_params.get("mode", "")).casefold()
    st.session_state["app_mode"] = "artisan" if requested_mode == "artisan" else "buyer"
    st.session_state.setdefault("artisan_stage", "landing")
    st.session_state.setdefault("artisan_draft", None)
    st.session_state.setdefault("artisan_passport", None)
    st.session_state.setdefault("artisan_application_trace", ())
    st.session_state.setdefault("artisan_ai_status", "idle")
    st.session_state.setdefault("artisan_friendly_error", None)


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
        "comparison_result",
        "comparison_history",
        "application_execution_trace",
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
        comparison_result=st.session_state.get("comparison_result"),
        comparison_history=st.session_state.get("comparison_history", ()),
    )


def _catalog_snapshot() -> CatalogSnapshot:
    bundle, products = load_catalog()
    total = len(load_heritage_reference_catalog())
    formally_recommendable = sum(is_recommendation_eligible(product) for product in products)
    return CatalogSnapshot(
        bundle=bundle,
        products=products,
        catalog_total=total,
        formally_recommendable=formally_recommendable,
        reference_only=max(0, total - formally_recommendable),
        repository=_repository(),
    )


def _render_mode_switcher() -> None:
    """Use one shared header without executing both application branches."""
    st.markdown(
        '<div class="hl-mode-label">HAHA · Heritage Artisans, Horizons Ahead</div>',
        unsafe_allow_html=True,
    )
    buyer, artisan = st.columns(2)
    if buyer.button(
        "我是买家",
        key="switch_to_buyer",
        type="primary" if st.session_state["app_mode"] == "buyer" else "secondary",
        width="stretch",
    ):
        if "mode" in st.query_params:
            del st.query_params["mode"]
        st.session_state["app_mode"] = "buyer"
        st.rerun()
    if artisan.button(
        "我是手艺人",
        key="switch_to_artisan",
        type="primary" if st.session_state["app_mode"] == "artisan" else "secondary",
        width="stretch",
    ):
        st.query_params["mode"] = "artisan"
        st.session_state["app_mode"] = "artisan"
        st.rerun()


def _new_artisan_draft() -> ArtisanProductDraft:
    draft = create_draft(st.session_state["artisan_session_id"], {})
    st.session_state["artisan_draft"] = draft
    st.session_state["artisan_passport"] = None
    st.session_state["artisan_ai_status"] = "idle"
    st.session_state["artisan_friendly_error"] = None
    return draft


def _current_artisan_draft() -> ArtisanProductDraft:
    draft = st.session_state.get("artisan_draft")
    return draft if isinstance(draft, ArtisanProductDraft) else _new_artisan_draft()


def _parse_optional_int(value: str, label: str, *, multiplier: int = 1) -> int | None:
    normalized = value.strip()
    if not normalized or normalized in {"暂不确定", "unknown"}:
        return None
    try:
        parsed = int(Decimal(normalized) * multiplier)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError(f"{label}请输入数字，或留空表示暂不确定") from exc
    if parsed < 0:
        raise ValueError(f"{label}不能为负数")
    return parsed


def _choice_to_bool(value: str) -> bool | None:
    return {"支持": True, "不支持": False}.get(value)


def _split_values(value: str) -> tuple[str, ...] | None:
    values = tuple(item.strip() for item in re.split(r"[、,，;；]", value) if item.strip())
    return values or None


def _fact_value(draft: ArtisanProductDraft, field_name: str, default: Any = "") -> Any:
    fact = draft.facts_by_name.get(field_name)
    return default if fact is None or fact.value is None else fact.value


def _merge_artisan_step(values: dict[str, Any]) -> ArtisanProductDraft:
    draft = _current_artisan_draft()
    updated = merge_artisan_values(draft, values)
    st.session_state["artisan_draft"] = updated
    return updated


def _resolved_merge(draft: ArtisanProductDraft, values: dict[str, Any]) -> ArtisanProductDraft:
    """Review edits are explicit choices, unlike progressive intake merges."""
    resolutions = {
        name: value
        for name, value in values.items()
        if name in draft.facts_by_name and value is not None
    }
    return merge_artisan_values(draft, values, resolutions=resolutions)


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
    if result.application_trace:
        st.session_state["application_execution_trace"] = result.application_trace
    elif state.comparison_result is None:
        st.session_state["application_execution_trace"] = ()
    st.session_state["comparison_result"] = state.comparison_result
    st.session_state["comparison_history"] = state.comparison_history


def _run_agent(
    action: RequestedAction,
    *,
    text: str = "",
    source: str = "chat",
    product_id: str | None = None,
    product_ids: tuple[str, ...] = (),
    comparison_focus: tuple[str, ...] = (),
    focus_recipient: str | None = None,
    focus_scene: str | None = None,
    focus_styles: tuple[str, ...] = (),
    focus_symbolism: tuple[str, ...] = (),
    focus_customization: tuple[str, ...] = (),
    focus_international: bool | None = None,
    structured_request: ParsedCustomerRequest | None = None,
) -> AgentTurnResult:
    turn = UserTurn(
        message_id=f"turn-{len(_agent_state().conversation_state.raw_user_texts) + 1}",
        text=text,
        submitted_at=datetime.now(UTC),
        requested_action=action,
        source=source,
        product_id=product_id,
        product_ids=product_ids,
        comparison_focus=comparison_focus,
        focus_recipient=focus_recipient,
        focus_scene=focus_scene,
        focus_styles=focus_styles,
        focus_symbolism=focus_symbolism,
        focus_customization=focus_customization,
        focus_international=focus_international,
        structured_request=structured_request,
    )
    result = run_agent_turn(turn, _agent_state(), _catalog_snapshot(), _agent_runtime())
    _apply_agent_result(result)
    return result


def _process_message(message: str, *, entry_source: str = "chat") -> None:
    try:
        if entry_source == "recommend_now":
            route_action = RequestedAction.RECOMMEND_NOW
            product_id = None
            product_ids: tuple[str, ...] = ()
            focus: tuple[str, ...] = ()
            focus_recipient = None
            focus_scene = None
            focus_styles: tuple[str, ...] = ()
            focus_symbolism: tuple[str, ...] = ()
            focus_customization: tuple[str, ...] = ()
            focus_international = None
        else:
            result = st.session_state.get("progressive_result")
            response = (
                result.response if isinstance(result, ProgressiveRecommendationResult) else None
            )
            route = route_shopping_turn(message, response)
            route_action = route.action
            product_id = route.product_id
            product_ids = route.product_ids
            focus = route.focus_dimensions
            focus_recipient = route.focus_recipient
            focus_scene = route.focus_scene
            focus_styles = route.focus_styles
            focus_symbolism = route.focus_symbolism
            focus_customization = route.focus_customization
            focus_international = route.focus_international
        _run_agent(
            route_action,
            text=message,
            source=entry_source,
            product_id=product_id,
            product_ids=product_ids,
            comparison_focus=focus,
            focus_recipient=focus_recipient,
            focus_scene=focus_scene,
            focus_styles=focus_styles,
            focus_symbolism=focus_symbolism,
            focus_customization=focus_customization,
            focus_international=focus_international,
        )
    except (RequestValidationError, DataValidationError, ValueError) as exc:
        st.session_state["friendly_error"] = str(exc)


def _render_artisan_story() -> None:
    render_artisan_section(
        "STEP 1 · 讲述",
        "先告诉我们，这是一件怎样的作品",
        "不需要一次写得完整。名称、工艺、地区和你最想说的故事就足够开始。",
    )
    draft = _current_artisan_draft()
    with st.form("artisan_story_form", border=True):
        product_name = st.text_input(
            "作品名称",
            value=str(_fact_value(draft, "product_name_zh")),
            key="artisan_story_product_name",
        )
        craft_category = st.text_input(
            "工艺类别",
            value=str(_fact_value(draft, "craft_name")),
            key="artisan_story_craft_category",
        )
        region = st.text_input(
            "所在地区",
            value=str(_fact_value(draft, "region")),
            key="artisan_story_region",
        )
        description = st.text_area(
            "自由描述",
            value=str(_fact_value(draft, "free_description")),
            placeholder=(
                "例如：这是一件芜湖铁画作品，以迎客松为主题，适合作为企业礼赠，也可以加入公司题字。"
            ),
            height=150,
            key="artisan_story_description",
        )
        image = st.file_uploader(
            "产品图片（可选）",
            type=("jpg", "jpeg", "png", "webp"),
            key="artisan_story_image",
        )
        submitted = st.form_submit_button(
            "保存并继续：商业信息",
            type="primary",
            width="stretch",
        )
    if submitted:
        if not product_name.strip() and not description.strip():
            st.info("请先填写作品名称，或用一段自由描述讲讲你的作品。")
            return
        image_bytes = image.getvalue() if image is not None else draft.image_bytes
        image_name = image.name if image is not None else draft.image_name
        if not draft.facts:
            updated = create_draft(
                draft.session_id,
                {
                    "product_name_zh": product_name,
                    "craft_name": craft_category or "unknown",
                    "region": region or "unknown",
                },
                description=description,
                image_name=image_name,
                image_bytes=image_bytes,
            )
        else:
            updated = _resolved_merge(
                draft,
                {
                    "product_name_zh": product_name,
                    "craft_name": craft_category or "unknown",
                    "region": region or "unknown",
                    "free_description": description or "unknown",
                },
            )
            updated = replace(updated, image_name=image_name, image_bytes=image_bytes)
        st.session_state["artisan_draft"] = updated
        st.session_state["artisan_stage"] = "commercial"
        st.rerun()


def _render_artisan_commercial() -> None:
    render_artisan_section(
        "STEP 2 · 整理",
        "补充你目前知道的商业信息",
        "所有字段都可以留空。暂不确定比为了完成表单而猜一个答案更可靠。",
    )
    draft = _current_artisan_draft()
    with st.form("artisan_commercial_form", border=True):
        price_min = st.text_input(
            "最低单价（元，可留空）",
            value=(
                str(int(_fact_value(draft, "price_min_fen", 0)) // 100)
                if _fact_value(draft, "price_min_fen", None) is not None
                else ""
            ),
            key="artisan_commercial_price_min",
        )
        price_max = st.text_input(
            "最高单价（元，可留空）",
            value=(
                str(int(_fact_value(draft, "price_max_fen", 0)) // 100)
                if _fact_value(draft, "price_max_fen", None) is not None
                else ""
            ),
            key="artisan_commercial_price_max",
        )
        currency = st.selectbox(
            "币种",
            ("CNY", "USD", "暂不确定"),
            key="artisan_commercial_currency",
        )
        moq = st.text_input("最低起订量（件，可留空）", key="artisan_commercial_moq")
        lead_time = st.text_input(
            "预计制作周期（天，可留空）",
            key="artisan_commercial_lead_time",
        )
        customization = st.text_input(
            "可提供的定制方式",
            placeholder="例如：题字、尺寸、包装",
            key="artisan_commercial_customization",
        )
        logo = st.selectbox(
            "是否支持 Logo",
            ("暂不确定", "支持", "不支持"),
            key="artisan_commercial_logo",
        )
        packaging = st.text_input("包装说明（可留空）", key="artisan_commercial_packaging")
        dimensions = st.text_input("尺寸（可留空）", key="artisan_commercial_dimensions")
        materials = st.text_input("材料（可留空）", key="artisan_commercial_materials")
        domestic = st.selectbox(
            "国内运输",
            ("暂不确定", "支持", "不支持"),
            key="artisan_commercial_domestic_shipping",
        )
        international = st.selectbox(
            "国际运输",
            ("暂不确定", "支持", "不支持"),
            key="artisan_commercial_international_shipping",
        )
        capacity = st.text_input(
            "可承接数量（件，可留空）",
            key="artisan_commercial_capacity",
        )
        submitted = st.form_submit_button(
            "保存并继续：文化与来源",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            values = {
                "price_min_fen": _parse_optional_int(price_min, "最低单价", multiplier=100),
                "price_max_fen": _parse_optional_int(price_max, "最高单价", multiplier=100),
                "currency": None if currency == "暂不确定" else currency,
                "moq": _parse_optional_int(moq, "最低起订量"),
                "lead_time_days": _parse_optional_int(lead_time, "制作周期"),
                "customization": _split_values(customization),
                "logo_supported": _choice_to_bool(logo),
                "packaging": packaging or None,
                "dimensions": dimensions or None,
                "materials": materials or None,
                "domestic_shipping": _choice_to_bool(domestic),
                "international_shipping": _choice_to_bool(international),
                "quantity_capacity": _parse_optional_int(capacity, "可承接数量"),
            }
            minimum = values["price_min_fen"]
            maximum = values["price_max_fen"]
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError("最低单价不能高于最高单价")
            updated = _resolved_merge(draft, values)
            st.session_state["artisan_draft"] = updated
        except ValueError as exc:
            st.info(str(exc))
            return
        st.session_state["artisan_stage"] = "culture"
        st.rerun()


def _render_artisan_culture() -> None:
    render_artisan_section(
        "STEP 3 · 来源",
        "补充文化背景与可追溯来源",
        "AI 只会重组你提供的资料；文化身份、传承关系和商业承诺仍由你确认。",
    )
    draft = _current_artisan_draft()
    with st.form("artisan_culture_form", border=True):
        craft_name = st.text_input(
            "工艺名称",
            value=str(_fact_value(draft, "craft_name")),
            key="artisan_culture_craft_name",
        )
        heritage_item = st.text_input("非遗项目（可留空）", key="artisan_culture_heritage_item")
        region = st.text_input(
            "地域",
            value=str(_fact_value(draft, "region")),
            key="artisan_culture_region",
        )
        background = st.text_area(
            "工艺与文化背景",
            height=130,
            key="artisan_culture_background",
        )
        symbolism = st.text_input(
            "文化寓意",
            placeholder="例如：迎客、友谊、开放",
            key="artisan_culture_symbolism",
        )
        process = st.text_area("制作工序（可留空）", key="artisan_culture_process")
        cultural_url = st.text_input(
            "文化资料链接（HTTPS，可留空）",
            key="artisan_culture_cultural_source_url",
        )
        merchant_url = st.text_input(
            "商家资料链接（HTTPS，可留空）",
            key="artisan_culture_merchant_source_url",
        )
        other_url = st.text_input(
            "其他参考链接（HTTPS，可留空）",
            key="artisan_culture_other_reference_url",
        )
        submitted = st.form_submit_button(
            "AI 协助整理并进入确认",
            type="primary",
            width="stretch",
        )
    if submitted:
        urls = (cultural_url, merchant_url, other_url)
        if any(url and not url.startswith("https://") for url in urls):
            st.info("资料链接请填写完整的 HTTPS 地址，或暂时留空。")
            return
        draft = _resolved_merge(
            draft,
            {
                "craft_name": craft_name or None,
                "heritage_item": heritage_item or None,
                "region": region or None,
                "cultural_background": background or None,
                "symbolism": _split_values(symbolism),
                "craft_process": process or None,
                "cultural_source_url": cultural_url or None,
                "merchant_source_url": merchant_url or None,
                "other_reference_url": other_url or None,
            },
        )
        client = None
        if os.getenv("LLM_ENABLED", "true").lower() == "true" and deepseek_is_configured():
            try:
                client = DeepSeekClient.from_env()
            except Exception:
                client = None
        updated, trace = enrich_draft(draft, client=client)
        st.session_state["artisan_draft"] = updated
        st.session_state["artisan_application_trace"] = (trace,)
        st.session_state["artisan_ai_status"] = trace.status.value
        st.session_state["artisan_stage"] = "review"
        st.rerun()


ARTISAN_FACT_LABELS = {
    "product_name_zh": "作品名称",
    "product_name_en": "英文名称",
    "craft_name": "工艺",
    "heritage_item": "非遗项目",
    "region": "地域",
    "cultural_background": "文化背景",
    "symbolism": "文化寓意",
    "craft_process": "制作工序",
    "price_min_fen": "最低单价（分）",
    "price_max_fen": "最高单价（分）",
    "currency": "币种",
    "moq": "最低起订量",
    "lead_time_days": "制作周期（天）",
    "customization": "定制方式",
    "logo_supported": "Logo 定制",
    "packaging": "包装",
    "dimensions": "尺寸",
    "materials": "材料",
    "domestic_shipping": "国内运输",
    "international_shipping": "国际运输",
    "quantity_capacity": "可承接数量",
    "cultural_source_url": "文化资料链接",
    "merchant_source_url": "商家资料链接",
    "other_reference_url": "其他参考链接",
}


def _fact_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "支持" if value else "不支持"
    if isinstance(value, (tuple, list, set, frozenset)):
        return "、".join(str(item) for item in value)
    return str(value)


def _coerce_review_value(field_name: str, text: str, original: Any) -> Any:
    normalized = text.strip()
    if not normalized:
        return None
    if (
        isinstance(original, bool)
        or field_name.endswith("_shipping")
        or field_name == "logo_supported"
    ):
        if normalized not in {"支持", "不支持"}:
            raise ValueError(f"{ARTISAN_FACT_LABELS.get(field_name, field_name)}请填写支持或不支持")
        return normalized == "支持"
    if isinstance(original, int) or field_name in {
        "price_min_fen",
        "price_max_fen",
        "moq",
        "lead_time_days",
        "quantity_capacity",
    }:
        return _parse_optional_int(normalized, ARTISAN_FACT_LABELS.get(field_name, field_name))
    if isinstance(original, (tuple, list, set, frozenset)) or field_name in {
        "symbolism",
        "customization",
    }:
        return _split_values(normalized)
    return normalized


def _render_artisan_review() -> None:
    render_artisan_section(
        "REVIEW · 人工确认",
        "请确认作品资料",
        "你可以修改每个字段，并只勾选自己能够确认的内容。未勾选字段会继续保持待确认。",
    )
    if st.session_state.get("artisan_ai_status") == "fallback":
        st.info("AI 双语辅助暂时不可用。您仍可以手动完善资料并继续建立文化护照。")
    draft = _current_artisan_draft()
    unresolved = tuple(conflict for conflict in draft.conflicts if not conflict.is_resolved)
    if unresolved:
        st.warning("检测到已有资料与本次输入不同。请先选择保留哪一项，再继续确认。")
        for conflict in unresolved:
            label = ARTISAN_FACT_LABELS.get(conflict.field_name, conflict.field_name)
            choice = st.radio(
                label,
                ("保留当前记录", "采用本次输入"),
                key=f"artisan_conflict_{draft.updated_at.timestamp()}_{conflict.field_name}",
                captions=(
                    _fact_to_text(conflict.current_value),
                    _fact_to_text(conflict.incoming_value),
                ),
            )
            if st.button(
                f"确认{label}选择",
                key=f"artisan_conflict_resolve_{draft.updated_at.timestamp()}_{conflict.field_name}",
                width="stretch",
            ):
                selected = (
                    conflict.current_value if choice == "保留当前记录" else conflict.incoming_value
                )
                resolved = merge_artisan_values(
                    draft,
                    {conflict.field_name: conflict.incoming_value},
                    resolutions={conflict.field_name: selected},
                )
                st.session_state["artisan_draft"] = resolved
                st.rerun()
        return
    facts = tuple(
        fact
        for fact in draft.facts
        if fact.field_name in ARTISAN_FACT_LABELS and fact.field_name != "free_description"
    )
    with st.form(f"artisan_review_form_{draft.updated_at.timestamp()}", border=True):
        edited: dict[str, str] = {}
        confirmed: list[str] = []
        for fact in facts:
            label = ARTISAN_FACT_LABELS[fact.field_name]
            edited[fact.field_name] = st.text_input(
                label,
                value=_fact_to_text(fact.value),
                key=f"artisan_review_{draft.updated_at.timestamp()}_{fact.field_name}",
            )
            if fact.value is not None and st.checkbox(
                "我确认这项资料准确",
                value=fact.verification_status.value == "confirmed",
                key=f"artisan_confirm_{draft.updated_at.timestamp()}_{fact.field_name}",
            ):
                confirmed.append(fact.field_name)

        bilingual = draft.bilingual_draft
        if bilingual is not None:
            st.markdown("### 中英双语草稿")
            overview_zh = st.text_area(
                "中文产品简介",
                value=bilingual.overview_zh,
                height=100,
                key=f"artisan_review_{draft.updated_at.timestamp()}_overview_zh",
            )
            overview_en = st.text_area(
                "English product overview",
                value=bilingual.overview_en,
                height=100,
                key=f"artisan_review_{draft.updated_at.timestamp()}_overview_en",
            )
            cultural_zh = st.text_area(
                "中文文化寓意",
                value=bilingual.cultural_meaning_zh,
                height=90,
                key=f"artisan_review_{draft.updated_at.timestamp()}_cultural_meaning_zh",
            )
            cultural_en = st.text_area(
                "English cultural meaning",
                value=bilingual.cultural_meaning_en,
                height=90,
                key=f"artisan_review_{draft.updated_at.timestamp()}_cultural_meaning_en",
            )
            confirm_bilingual = st.checkbox(
                "我已检查并确认这份双语表达",
                key=f"artisan_confirm_{draft.updated_at.timestamp()}_bilingual",
            )
        else:
            overview_zh = overview_en = cultural_zh = cultural_en = ""
            confirm_bilingual = False
        submitted = st.form_submit_button(
            "确认并生成文化护照",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            values = {
                name: _coerce_review_value(name, text, draft.facts_by_name[name].value)
                for name, text in edited.items()
            }
            updated = _resolved_merge(draft, values)
            if updated.bilingual_draft is not None:
                original = updated.bilingual_draft
                updated = update_bilingual_draft(
                    updated,
                    {
                        "overview_zh": overview_zh,
                        "overview_en": overview_en,
                        "cultural_meaning_zh": cultural_zh,
                        "cultural_meaning_en": cultural_en,
                        "craft_background_zh": original.craft_background_zh,
                        "craft_background_en": original.craft_background_en,
                        "gifting_contexts_zh": original.gifting_contexts_zh,
                        "gifting_contexts_en": original.gifting_contexts_en,
                        "customization_zh": original.customization_zh,
                        "customization_en": original.customization_en,
                    },
                )
            updated = confirm_facts(
                updated,
                tuple(confirmed),
                bilingual_confirmed=confirm_bilingual,
            )
        except ValueError as exc:
            st.info(str(exc))
            return
        passport = build_passport(updated)
        st.session_state["artisan_draft"] = updated
        st.session_state["artisan_passport"] = passport
        st.session_state["artisan_stage"] = "passport"
        st.rerun()


def _render_artisan_passport() -> None:
    passport = st.session_state.get("artisan_passport")
    if not isinstance(passport, HeritagePassport):
        passport = build_passport(_current_artisan_draft())
        st.session_state["artisan_passport"] = passport
    render_artisan_section(
        "HERITAGE PASSPORT",
        "你的非遗文化护照",
        "这里区分文化来源、商家事实和仍待确认的信息。提交审核不会自动发布产品。",
    )
    render_heritage_passport(passport, audience="artisan")
    if st.button("保存并提交审核", type="primary", width="stretch"):
        try:
            draft = submit_for_review(_current_artisan_draft(), _artisan_repository())
        except (RuntimeError, ValueError) as exc:
            st.info(str(exc))
            return
        st.session_state["artisan_draft"] = draft
        st.session_state["artisan_passport"] = build_passport(draft)
        existing_trace = st.session_state.get("artisan_application_trace", ())
        if existing_trace:
            trace = existing_trace[-1]
            st.session_state["artisan_application_trace"] = (
                replace(
                    trace,
                    output_summary={
                        **dict(trace.output_summary),
                        "publication_status": "pending_review",
                        "recommendation_eligibility": False,
                    },
                ),
            )
        st.session_state["artisan_stage"] = "submitted"
        st.rerun()


def _reset_artisan_flow() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("artisan_"):
            del st.session_state[key]
    st.session_state["artisan_stage"] = "landing"
    st.session_state["artisan_draft"] = None
    st.session_state["artisan_passport"] = None
    st.session_state["artisan_application_trace"] = ()
    st.session_state["artisan_ai_status"] = "idle"


def _render_artisan_submitted() -> None:
    draft = _current_artisan_draft()
    st.success("作品资料已保存并提交审核。")
    st.markdown("## 接下来会发生什么")
    st.write(
        "当前资料处于待审核目录，不会自动进入 AI Shopping。平台仍需核验身份、商家信息、"
        "文化来源与商业条件，符合正式资格后才能另行导入推荐目录。"
    )
    render_heritage_passport(build_passport(draft), audience="artisan", compact=True)
    if is_review_mode_enabled(st.query_params) and st.button(
        "模拟审核通过",
        width="stretch",
    ):
        reviewed = simulate_review_approval(draft, review_authorized=True)
        _artisan_repository().save(reviewed)
        st.session_state["artisan_draft"] = reviewed
        st.session_state["artisan_passport"] = build_passport(reviewed)
        if reviewed.publication_status is PublicationStatus.RECOMMENDABLE:
            st.info("演示审核已通过；该记录仍未写入当前 50 件正式目录。")
        else:
            st.info("审核后暂列文化参考；商业资料尚不足以进入正式推荐。")
    if st.button("继续添加作品", type="primary", width="stretch"):
        _reset_artisan_flow()
        st.rerun()


def _render_artisan_app() -> None:
    render_artisan_hero()
    stage = st.session_state.get("artisan_stage", "landing")
    render_artisan_progress(stage)
    if stage == "landing":
        render_artisan_journey()
        if st.button("开始添加作品", type="primary", width="stretch"):
            _new_artisan_draft()
            st.session_state["artisan_stage"] = "story"
            st.rerun()
        return
    if stage == "story":
        _render_artisan_story()
    elif stage == "commercial":
        _render_artisan_commercial()
    elif stage == "culture":
        _render_artisan_culture()
    elif stage == "review":
        _render_artisan_review()
    elif stage == "passport":
        _render_artisan_passport()
    elif stage == "submitted":
        _render_artisan_submitted()


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


def _render_conversation() -> None:
    st.markdown("## AI 礼品顾问")
    state = st.session_state["conversation_state"]
    with st.chat_message("assistant"):
        st.write(
            "您好，我是 HAHA｜飞颐礼遇顾问。您可以先告诉我礼物准备送给谁，"
            "或者描述一个大概的礼赠场景。"
        )
    for message in state.messages:
        with st.chat_message(message.role):
            st.write(message.content)
    if not state.raw_user_texts:
        columns = st.columns(2)
        for index, label in enumerate(QUICK_STARTS):
            if columns[index % 2].button(label, key=f"quick_{index}", width="stretch"):
                _process_message(QUICK_TEXT[label], entry_source=f"quick:{label}")
                st.rerun()
    prompt = st.chat_input("说说这次想送给谁，或输入您的礼赠场景")
    if prompt:
        _process_message(prompt)
        st.rerun()
    if state.raw_user_texts:
        recommend, restart = st.columns(2)
        if recommend.button("先为我推荐", type="primary", width="stretch"):
            _process_message("请先为我推荐，我之后再调整。", entry_source="recommend_now")
            st.rerun()
        if restart.button("重新开始", width="stretch"):
            _run_agent(RequestedAction.RESTART, source="restart")
            st.session_state["show_requirement_editor"] = False
            st.rerun()
    if error := st.session_state.pop("friendly_error", None):
        st.info(error)


def _render_requirement_summary() -> None:
    parsed = st.session_state.get("pending_request")
    if not isinstance(parsed, ParsedCustomerRequest):
        return
    context = st.session_state.get("recommendation_context")
    display = context.effective_request if isinstance(context, RecommendationContext) else parsed
    st.markdown("## 当前需求摘要")
    items = _summary_items(display)
    if items:
        tags = "".join(f"<span>{escape(label)}：{escape(value)}</span>" for label, value in items)
        st.markdown(f'<div class="hl-summary">{tags}</div>', unsafe_allow_html=True)
    else:
        st.caption("我们先从赠礼对象或场景开始，之后可以随时调整。")
    if isinstance(context, RecommendationContext):
        st.write(context.direction_summary)
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
        with st.container(border=True):
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


def _render_recommendations(bundle: DataBundle, products: tuple[Product, ...]) -> None:
    result = st.session_state.get("progressive_result")
    context = st.session_state.get("recommendation_context")
    event = st.session_state.get("recommendation_event")
    if not isinstance(result, ProgressiveRecommendationResult) or not isinstance(
        context, RecommendationContext
    ):
        return
    response = result.response
    count = len(response.recommendations)
    heading, action = st.columns([4, 1.2], vertical_alignment="center")
    with heading:
        st.markdown(f"## 我为您挑选了{count}件更适合这次赠礼的作品")
        st.write("根据赠礼对象、场景和您偏好的文化方向，我为您整理了以下作品。")
    with action:
        if count >= 2 and st.button(
            f"比较这{count}件",
            key="compare_all_recommendations",
            type="primary",
            width="stretch",
        ):
            _compare_products(
                tuple(item.product.product_id for item in response.recommendations),
                source="comparison_button",
            )
            st.rerun()
    st.checkbox(
        "允许匿名保存本次礼品偏好和选择，用于优化未来推荐。",
        key="analytics_consent",
        help="不保存姓名、联系方式或完整聊天原文；不同意也可以正常使用。",
    )
    if not response.recommendations:
        st.info(
            "当前目录中暂时没有同时符合这些条件的作品。您可以调整预算、数量、交付或定制要求后重新匹配。"
        )
        return
    participating = frozenset(result.participating_dimensions)
    parsed = context.effective_request
    selected_id = st.session_state.get("selected_product_id")
    passports = build_catalog_passports(products, bundle)
    for rank, recommendation in enumerate(response.recommendations, start=1):
        request = result.request_by_product[recommendation.product.product_id]
        card_action = render_product_card(
            rank,
            recommendation,
            request,
            participating,
            _known_customer_fields(parsed),
            passports.get(recommendation.product.product_id),
        )
        if card_action == "select":
            _select_product(recommendation.product.product_id)
            st.rerun()
        if card_action == "compare":
            _compare_products(
                tuple(item.product.product_id for item in response.recommendations),
                source="product_card_comparison",
                focus=(recommendation.product.product_id,),
            )
            st.rerun()

    comparison = st.session_state.get("comparison_result")
    if isinstance(comparison, ProductComparisonResult):
        render_product_comparison(comparison)
        choose, continue_comparing, adjust = st.columns(3)
        recommended_id = comparison.recommendation_for_current_user
        if recommended_id and choose.button(
            "选择推荐款",
            key="comparison_select_recommended",
            type="primary",
            width="stretch",
        ):
            _select_product(recommended_id)
            st.rerun()
        if continue_comparing.button(
            "继续比较",
            key="comparison_continue",
            width="stretch",
        ):
            st.session_state["comparison_prompt_hint"] = (
                "可以继续问：第一个和第三个哪个更适合教授？"
            )
            st.rerun()
        if adjust.button(
            "调整需求",
            key="comparison_adjust",
            width="stretch",
        ):
            st.session_state["show_requirement_editor"] = True
            st.rerun()
        if hint := st.session_state.pop("comparison_prompt_hint", None):
            st.info(hint)
    if selected_id:
        _render_selected_plan(bundle, str(selected_id), event)


def _compare_products(
    product_ids: tuple[str, ...],
    *,
    source: str,
    focus: tuple[str, ...] = (),
) -> None:
    _run_agent(
        RequestedAction.COMPARE_SELECTED_PRODUCTS,
        text="请比较当前推荐的作品。",
        source=source,
        product_ids=product_ids,
        comparison_focus=focus,
    )


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
    st.markdown("## 您选择的礼品")
    with st.container(border=True):
        image, detail = st.columns([1, 1.5])
        with image:
            product_image(recommendation.product.image_path, recommendation.product.image_alt_zh)
        with detail:
            st.markdown(f"### {recommendation.product.product_name_zh}")
            st.write(context.direction_summary)
            budget = context.effective_request.budget_per_item
            budget_fen = _yuan_to_fen(budget) if budget else None
            st.write(
                f"数量：{context.effective_request.quantity or '可后续沟通'}　·　"
                f"单件预算：{_money(budget_fen)}"
            )
        change, generate = st.columns(2)
        if change.button("更换产品", width="stretch"):
            st.session_state.pop("selected_product_id", None)
            st.session_state.pop("selection_event", None)
            st.session_state.pop("customization_inquiry", None)
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
    st.markdown("## 您的专属礼品方案")
    badges([("礼品已选定", "ok"), ("可继续调整", "wait")])
    st.markdown("### 推荐定制方向")
    st.write(f"主题方向：{parsed.requested_theme or context.direction_summary}")
    st.write(f"Logo：{'加入企业 Logo' if parsed.logo_required else '可按需要沟通'}")
    st.write(f"题字：{parsed.requested_text or '可结合赠礼场景进一步确定'}")
    st.write(f"包装：{parsed.packaging_requirement or '采用与当前礼赠场景相符的包装方向'}")
    zh, en = st.tabs(("中文文化介绍", "English Cultural Story"))
    with zh:
        st.write(content.zh.cultural_story)
        _render_source_note(content.zh.source_note)
    with en:
        st.write(content.en.cultural_story)
        _render_source_note(content.en.source_note)
    st.markdown("### 下一步")
    st.write("下载方案后，可继续确认具体定制内容、正式价格、制作安排与交付方式。")
    st.download_button(
        "下载方案",
        data=inquiry_to_json(inquiry),
        file_name=f"{inquiry['inquiry_id']}.json",
        mime="application/json",
        width="stretch",
    )


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
    application_traces = (
        st.session_state.get("artisan_application_trace", ())
        if st.session_state.get("app_mode") == "artisan"
        else st.session_state.get("application_execution_trace", ())
    )
    st.markdown("## Agent 执行轨迹")
    if not traces and not application_traces:
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
    if application_traces:
        st.markdown("### Application Actions")
    for trace in application_traces:
        with st.expander(f"Application Action：{trace.action_id} · {trace.status.value}"):
            st.json(
                {
                    "输入摘要": dict(trace.input_summary),
                    "输出摘要": dict(trace.output_summary),
                    "narrative_source": trace.narrative_source.value,
                }
            )
            for check in trace.safety_checks:
                st.write(f"✓ {check}")


def main() -> None:
    st.set_page_config(
        page_title="HAHA｜飞颐礼遇｜AI 非遗出海平台",
        page_icon="礼",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    apply_theme()
    _init_state()
    _render_mode_switcher()
    try:
        bundle, products = load_catalog()
    except DataValidationError:
        st.info("产品资料暂时无法加载，请稍后再试。")
        st.stop()
    if st.session_state["app_mode"] == "artisan":
        _render_artisan_app()
    else:
        render_hero()
        _render_conversation()
        _render_secondary_form()
        _render_requirement_summary()
        _render_recommendations(bundle, products)
        _render_catalog()
        _render_service_note()
    _render_agent_trace()


if __name__ == "__main__":
    main()
