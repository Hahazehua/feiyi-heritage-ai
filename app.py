"""Single-page conversational gift advisor for HAHA｜飞颐礼遇."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from heritagelink import recommendation_narrative
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
from heritagelink.campaign_service import create_campaign_repository
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
from heritagelink.dialogue_manager import recommendation_signature
from heritagelink.growth_grounding import (
    build_catalog_growth_context,
    build_draft_growth_context,
)
from heritagelink.growth_models import GrowthOutputSource
from heritagelink.heritage_passport import build_catalog_passports
from heritagelink.heritage_passport_models import (
    ArtisanProductDraft,
    HeritagePassport,
    PublicationStatus,
)
from heritagelink.i18n import (
    LANGUAGE_SESSION_KEY,
    Language,
    get_language,
    localize_literal,
    normalize_language,
    t,
)
from heritagelink.inquiry import inquiry_to_json
from heritagelink.llm_client import DeepSeekClient
from heritagelink.models import DataBundle, Product, Recommendation
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.campaign_repository import CampaignRepository
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
from heritagelink.ui.catalog_gallery import render_catalog_gallery, render_partner_works
from heritagelink.ui.comparison import render_product_comparison
from heritagelink.ui.components import badges, product_image
from heritagelink.ui.demo_tour import clamp_step, render_demo_tour
from heritagelink.ui.entry import render_entry_screen
from heritagelink.ui.footer import render_footer
from heritagelink.ui.growth_studio import render_growth_studio_app
from heritagelink.ui.header import render_global_header
from heritagelink.ui.heritage_passport import render_heritage_passport
from heritagelink.ui.home import render_about_page, render_buyer_hero, render_platform_story
from heritagelink.ui.product_card import render_product_card
from heritagelink.ui.requirements import (
    MEANINGS,
    OPTION_LABELS_EN,
    RECIPIENTS,
    SCENES,
    STYLES,
    parsed_from_widgets,
    render_structured_form,
)
from heritagelink.ui.system import render_metric_strip
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

QUICK_START_TRANSLATION_KEYS = (
    ("buyer.quick.overseas", "buyer.quick.overseas_text"),
    ("buyer.quick.professor", "buyer.quick.professor_text"),
    ("buyer.quick.anniversary", "buyer.quick.anniversary_text"),
    ("buyer.quick.explore", "buyer.quick.explore_text"),
)
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


@st.cache_data(show_spinner=False)
def _reference_by_demo_product() -> dict[str, HeritageReferenceItem]:
    """Index the museum catalogue by the sale product it backs.

    heritage_products.csv carries demo_product_id for exactly this join, which
    is what lets a product card cite the accession number behind its image.
    """
    return {
        item.demo_product_id: item
        for item in load_heritage_reference_catalog()
        if item.demo_product_id
    }


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


@st.cache_resource(show_spinner=False)
def _configured_campaign_repository() -> CampaignRepository:
    try:
        return create_campaign_repository(os.getenv("CAMPAIGN_DATABASE_URL"))
    except Exception:
        LOGGER.exception("Growth campaign storage initialization failed; using memory storage")
        return create_campaign_repository(None)


def _campaign_repository() -> CampaignRepository:
    override = st.session_state.get("_campaign_repository_override")
    if override is not None:
        return override
    return _configured_campaign_repository()


def _init_state() -> None:
    settings = AnalyticsSettings.from_env()
    requested_language = str(st.query_params.get("lang", ""))
    st.session_state.setdefault(
        LANGUAGE_SESSION_KEY,
        normalize_language(requested_language).value
        if requested_language
        else Language.ZH_CN.value,
    )
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
    # The URL decides which surface is showing — session state only remembers
    # it. Deriving it the other way round let browser Back rewrite the address
    # bar while the page kept rendering the side the visitor had just left, and
    # it is also what makes ?mode= a real deep link for reviewers.
    requested_mode = str(st.query_params.get("mode", "")).casefold()
    requested_page = str(st.query_params.get("page", "")).casefold()
    role = requested_mode if requested_mode in {"artisan", "buyer"} else None
    st.session_state["entry_role"] = role
    st.session_state["app_mode"] = role or "buyer"
    st.session_state["app_page"] = "about" if requested_page == "about" else (role or "buyer")
    st.session_state.setdefault("artisan_stage", "landing")
    st.session_state.setdefault("artisan_draft", None)
    st.session_state.setdefault("artisan_passport", None)
    st.session_state.setdefault("artisan_application_trace", ())
    st.session_state.setdefault("artisan_ai_status", "idle")
    st.session_state.setdefault("artisan_friendly_error", None)
    st.session_state.setdefault("artisan_workspace", "onboarding")
    st.session_state.setdefault("growth_run_state", None)
    st.session_state.setdefault("growth_campaign", None)
    st.session_state.setdefault("growth_context", None)
    st.session_state.setdefault("growth_execution_trace", ())
    st.session_state.setdefault(
        "competition_demo",
        str(st.query_params.get("demo", "")) == "1",
    )
    st.session_state.setdefault("competition_demo_step", 1)


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
    """Count the catalogue from the products themselves.

    These figures used to be derived from the museum reference table, which
    worked while the two were one-to-one. They no longer are: a product can
    exist without a museum record, so reference_only was being inferred as a
    remainder and drifting away from the number of actual reference rows.
    """
    bundle, products = load_catalog()
    formally_recommendable = sum(is_recommendation_eligible(product) for product in products)
    reference_only = sum(product.catalog_role == "catalog_reference" for product in products)
    return CatalogSnapshot(
        bundle=bundle,
        products=products,
        catalog_total=len(products),
        formally_recommendable=formally_recommendable,
        reference_only=reference_only,
        repository=_repository(),
    )


def _enter_role(role: str) -> None:
    """Commit an entry choice to the URL.

    Only the query parameter is written: _init_state derives every piece of
    navigation state from it on the next run, so there is one source of truth
    and Back stays meaningful.
    """
    st.query_params["mode"] = role
    if "page" in st.query_params:
        del st.query_params["page"]
    if st.session_state.get("competition_demo"):
        st.session_state["competition_demo_step"] = 3 if role == "artisan" else 1


def _render_footer_navigation() -> None:
    """Render the footer and act on its two secondary destinations."""
    action = render_footer(on_about=st.session_state.get("app_page") == "about")
    if action.show_about:
        st.query_params["page"] = "about"
        st.rerun()
    if action.switch_role:
        # Clearing the parameters is the whole operation: _init_state reads the
        # empty URL on the next run and falls back to the chooser.
        for key in ("mode", "page"):
            if key in st.query_params:
                del st.query_params[key]
        st.rerun()


def _render_mode_switcher() -> None:
    """Render the masthead and act on the competition demo controls."""
    action = render_global_header(
        role=str(st.session_state.get("entry_role") or st.session_state["app_mode"]),
        demo_active=bool(st.session_state.get("competition_demo")),
    )
    if action.toggle_demo:
        enabled = not bool(st.session_state.get("competition_demo"))
        st.session_state["competition_demo"] = enabled
        st.session_state["competition_demo_step"] = 1
        if enabled:
            st.query_params["demo"] = "1"
        elif "demo" in st.query_params:
            del st.query_params["demo"]
        st.rerun()
    if action.reset_demo:
        _reset_competition_demo()
        st.rerun()


def _reset_competition_demo() -> None:
    """Restore predictable UI state without deleting saved campaigns or repositories."""
    if "mode" in st.query_params:
        del st.query_params["mode"]
    if "page" in st.query_params:
        del st.query_params["page"]
    st.session_state["app_mode"] = "buyer"
    st.session_state["app_page"] = "buyer"
    st.session_state["competition_demo_step"] = 1
    st.session_state["conversation_state"] = new_conversation()
    st.session_state["growth_run_state"] = None
    st.session_state["growth_campaign"] = None
    st.session_state["growth_context"] = None
    st.session_state["growth_execution_trace"] = ()
    _clear_downstream()


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


def _choice_label(value: str) -> str:
    return {
        "暂不确定": t("artisan.option.unknown"),
        "支持": t("artisan.option.supported"),
        "不支持": t("artisan.option.not_supported"),
    }.get(value, value)


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
        if st.session_state.get("competition_demo") and st.session_state.get(
            "recommendation_response"
        ):
            st.session_state["competition_demo_step"] = 2
    except (RequestValidationError, DataValidationError, ValueError) as exc:
        st.session_state["friendly_error"] = str(exc)


def _render_artisan_story() -> None:
    render_artisan_section(
        t("artisan.story.kicker"),
        t("artisan.story.title"),
        t("artisan.story.copy"),
    )
    draft = _current_artisan_draft()
    with st.form("artisan_story_form", border=True):
        product_name = st.text_input(
            t("artisan.field.product_name"),
            value=str(_fact_value(draft, "product_name_zh")),
            key="artisan_story_product_name",
        )
        craft_category = st.text_input(
            t("artisan.field.craft"),
            value=str(_fact_value(draft, "craft_name")),
            key="artisan_story_craft_category",
        )
        region = st.text_input(
            t("artisan.field.region"),
            value=str(_fact_value(draft, "region")),
            key="artisan_story_region",
        )
        description = st.text_area(
            t("artisan.field.description"),
            value=str(_fact_value(draft, "free_description")),
            placeholder=t("artisan.field.description_example"),
            height=150,
            key="artisan_story_description",
        )
        image = st.file_uploader(
            t("artisan.field.image"),
            type=("jpg", "jpeg", "png", "webp"),
            key="artisan_story_image",
        )
        submitted = st.form_submit_button(
            t("artisan.story.continue"),
            type="primary",
            width="stretch",
        )
    if submitted:
        if not product_name.strip() and not description.strip():
            st.info(t("artisan.story.required"))
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
        t("artisan.commercial.kicker"),
        t("artisan.commercial.title"),
        t("artisan.commercial.copy"),
    )
    draft = _current_artisan_draft()
    with st.form("artisan_commercial_form", border=True):
        price_min = st.text_input(
            t("artisan.field.price_min"),
            value=(
                str(int(_fact_value(draft, "price_min_fen", 0)) // 100)
                if _fact_value(draft, "price_min_fen", None) is not None
                else ""
            ),
            key="artisan_commercial_price_min",
        )
        price_max = st.text_input(
            t("artisan.field.price_max"),
            value=(
                str(int(_fact_value(draft, "price_max_fen", 0)) // 100)
                if _fact_value(draft, "price_max_fen", None) is not None
                else ""
            ),
            key="artisan_commercial_price_max",
        )
        currency = st.selectbox(
            t("artisan.field.currency"),
            ("CNY", "USD", "暂不确定"),
            format_func=_choice_label,
            key="artisan_commercial_currency",
        )
        moq = st.text_input(t("artisan.field.moq"), key="artisan_commercial_moq")
        lead_time = st.text_input(
            t("artisan.field.lead_time"),
            key="artisan_commercial_lead_time",
        )
        customization = st.text_input(
            t("artisan.field.customization"),
            placeholder=t("artisan.field.customization_example"),
            key="artisan_commercial_customization",
        )
        logo = st.selectbox(
            t("artisan.field.logo"),
            ("暂不确定", "支持", "不支持"),
            format_func=_choice_label,
            key="artisan_commercial_logo",
        )
        packaging = st.text_input(t("artisan.field.packaging"), key="artisan_commercial_packaging")
        dimensions = st.text_input(
            t("artisan.field.dimensions"), key="artisan_commercial_dimensions"
        )
        materials = st.text_input(t("artisan.field.materials"), key="artisan_commercial_materials")
        domestic = st.selectbox(
            t("artisan.field.domestic_shipping"),
            ("暂不确定", "支持", "不支持"),
            format_func=_choice_label,
            key="artisan_commercial_domestic_shipping",
        )
        international = st.selectbox(
            t("artisan.field.international_shipping"),
            ("暂不确定", "支持", "不支持"),
            format_func=_choice_label,
            key="artisan_commercial_international_shipping",
        )
        capacity = st.text_input(
            t("artisan.field.capacity"),
            key="artisan_commercial_capacity",
        )
        submitted = st.form_submit_button(
            t("artisan.commercial.continue"),
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
        t("artisan.culture.kicker"),
        t("artisan.culture.title"),
        t("artisan.culture.copy"),
    )
    draft = _current_artisan_draft()
    with st.form("artisan_culture_form", border=True):
        craft_name = st.text_input(
            t("artisan.field.craft_name"),
            value=str(_fact_value(draft, "craft_name")),
            key="artisan_culture_craft_name",
        )
        heritage_item = st.text_input(
            t("artisan.field.heritage_item"), key="artisan_culture_heritage_item"
        )
        region = st.text_input(
            t("artisan.field.region"),
            value=str(_fact_value(draft, "region")),
            key="artisan_culture_region",
        )
        background = st.text_area(
            t("artisan.field.cultural_background"),
            height=130,
            key="artisan_culture_background",
        )
        symbolism = st.text_input(
            t("artisan.field.symbolism"),
            placeholder=t("artisan.field.symbolism_example"),
            key="artisan_culture_symbolism",
        )
        process = st.text_area(t("artisan.field.process"), key="artisan_culture_process")
        cultural_url = st.text_input(
            t("artisan.field.cultural_url"),
            key="artisan_culture_cultural_source_url",
        )
        merchant_url = st.text_input(
            t("artisan.field.merchant_url"),
            key="artisan_culture_merchant_source_url",
        )
        other_url = st.text_input(
            t("artisan.field.other_url"),
            key="artisan_culture_other_reference_url",
        )
        submitted = st.form_submit_button(
            t("artisan.culture.continue"),
            type="primary",
            width="stretch",
        )
    if submitted:
        urls = (cultural_url, merchant_url, other_url)
        if any(url and not url.startswith("https://") for url in urls):
            st.info(t("artisan.culture.url_error"))
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


def _artisan_fact_labels() -> dict[str, str]:
    return {
        **ARTISAN_FACT_LABELS,
        "product_name_zh": t("artisan.field.product_name"),
        "product_name_en": t("artisan.field.product_name_en"),
        "craft_name": t("artisan.field.craft_name"),
        "heritage_item": t("artisan.field.heritage_item"),
        "region": t("artisan.field.region"),
        "cultural_background": t("artisan.field.cultural_background"),
        "symbolism": t("artisan.field.symbolism"),
        "craft_process": t("artisan.field.process"),
        "currency": t("artisan.field.currency"),
        "moq": t("passport.moq"),
        "lead_time_days": t("passport.lead_time"),
        "customization": t("passport.customization"),
        "logo_supported": t("artisan.field.logo"),
        "packaging": t("artisan.field.packaging"),
        "dimensions": t("artisan.field.dimensions"),
        "materials": t("artisan.field.materials"),
        "domestic_shipping": t("artisan.field.domestic_shipping"),
        "international_shipping": t("artisan.field.international_shipping"),
        "quantity_capacity": t("artisan.field.capacity"),
        "cultural_source_url": t("artisan.field.cultural_url"),
        "merchant_source_url": t("artisan.field.merchant_url"),
        "other_reference_url": t("artisan.field.other_url"),
    }


def _render_artisan_profile_metrics(draft: ArtisanProductDraft) -> None:
    visible = tuple(
        fact
        for fact in draft.facts
        if fact.field_name in _artisan_fact_labels() and fact.field_name != "free_description"
    )
    known = tuple(fact for fact in visible if fact.value not in (None, "", (), []))
    confirmed = tuple(fact for fact in known if fact.verification_status.value == "confirmed")
    pending = tuple(fact for fact in known if fact.verification_status.value == "pending_review")
    unknown = len(visible) - len(known)
    completeness = round(len(known) / max(1, len(visible)) * 100)
    render_metric_strip(
        (
            (t("artisan.profile_completeness"), f"{completeness}%", None),
            (t("artisan.verified_fields"), str(len(confirmed)), None),
            (t("artisan.pending_fields"), str(len(pending)), None),
            (t("artisan.unknown_fields"), str(unknown), None),
        )
    )
    st.caption(t("artisan.completeness_note"))


def _fact_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return t("artisan.option.supported") if value else t("artisan.option.not_supported")
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
        supported_values = {"支持", t("artisan.option.supported")}
        unsupported_values = {"不支持", t("artisan.option.not_supported")}
        if normalized not in supported_values | unsupported_values:
            raise ValueError(_artisan_fact_labels().get(field_name, field_name))
        return normalized in supported_values
    if isinstance(original, int) or field_name in {
        "price_min_fen",
        "price_max_fen",
        "moq",
        "lead_time_days",
        "quantity_capacity",
    }:
        return _parse_optional_int(normalized, _artisan_fact_labels().get(field_name, field_name))
    if isinstance(original, (tuple, list, set, frozenset)) or field_name in {
        "symbolism",
        "customization",
    }:
        return _split_values(normalized)
    return normalized


def _render_artisan_review() -> None:
    render_artisan_section(
        t("artisan.review.kicker"),
        t("artisan.review.title"),
        t("artisan.review.copy"),
    )
    if st.session_state.get("artisan_ai_status") == "fallback":
        st.info(t("artisan.review.ai_fallback"))
    draft = _current_artisan_draft()
    _render_artisan_profile_metrics(draft)
    unresolved = tuple(conflict for conflict in draft.conflicts if not conflict.is_resolved)
    if unresolved:
        st.warning(t("artisan.review.conflict"))
        for conflict in unresolved:
            label = _artisan_fact_labels().get(conflict.field_name, conflict.field_name)
            choice = st.radio(
                label,
                (t("artisan.review.keep_current"), t("artisan.review.use_incoming")),
                key=f"artisan_conflict_{draft.updated_at.timestamp()}_{conflict.field_name}",
                captions=(
                    _fact_to_text(conflict.current_value),
                    _fact_to_text(conflict.incoming_value),
                ),
            )
            if st.button(
                t("artisan.review.confirm_choice", label=label),
                key=f"artisan_conflict_resolve_{draft.updated_at.timestamp()}_{conflict.field_name}",
                width="stretch",
            ):
                selected = (
                    conflict.current_value
                    if choice == t("artisan.review.keep_current")
                    else conflict.incoming_value
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
        if fact.field_name in _artisan_fact_labels() and fact.field_name != "free_description"
    )
    with st.form(f"artisan_review_form_{draft.updated_at.timestamp()}", border=True):
        edited: dict[str, str] = {}
        confirmed: list[str] = []
        for fact in facts:
            label = _artisan_fact_labels()[fact.field_name]
            edited[fact.field_name] = st.text_input(
                label,
                value=_fact_to_text(fact.value),
                key=f"artisan_review_{draft.updated_at.timestamp()}_{fact.field_name}",
            )
            if fact.value is not None and st.checkbox(
                t("artisan.review.confirm_field"),
                value=fact.verification_status.value == "confirmed",
                key=f"artisan_confirm_{draft.updated_at.timestamp()}_{fact.field_name}",
            ):
                confirmed.append(fact.field_name)

        bilingual = draft.bilingual_draft
        if bilingual is not None:
            st.markdown(f"### {t('artisan.review.bilingual')}")
            overview_zh = st.text_area(
                t("artisan.review.overview_zh"),
                value=bilingual.overview_zh,
                height=100,
                key=f"artisan_review_{draft.updated_at.timestamp()}_overview_zh",
            )
            overview_en = st.text_area(
                t("artisan.review.overview_en"),
                value=bilingual.overview_en,
                height=100,
                key=f"artisan_review_{draft.updated_at.timestamp()}_overview_en",
            )
            cultural_zh = st.text_area(
                t("artisan.review.cultural_zh"),
                value=bilingual.cultural_meaning_zh,
                height=90,
                key=f"artisan_review_{draft.updated_at.timestamp()}_cultural_meaning_zh",
            )
            cultural_en = st.text_area(
                t("artisan.review.cultural_en"),
                value=bilingual.cultural_meaning_en,
                height=90,
                key=f"artisan_review_{draft.updated_at.timestamp()}_cultural_meaning_en",
            )
            confirm_bilingual = st.checkbox(
                t("artisan.review.confirm_bilingual"),
                key=f"artisan_confirm_{draft.updated_at.timestamp()}_bilingual",
            )
        else:
            overview_zh = overview_en = cultural_zh = cultural_en = ""
            confirm_bilingual = False
        submitted = st.form_submit_button(
            t("artisan.review.submit"),
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
        t("passport.eyebrow"),
        t("artisan.passport.title"),
        t("artisan.passport.copy"),
    )
    _render_artisan_profile_metrics(_current_artisan_draft())
    render_heritage_passport(passport, audience="artisan")
    if st.button(t("artisan.passport.submit"), type="primary", width="stretch"):
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
    st.success(t("artisan.submitted"))
    st.markdown(f"## {t('artisan.submitted.next')}")
    st.write(t("artisan.submitted.copy"))
    render_heritage_passport(build_passport(draft), audience="artisan", compact=True)
    if is_review_mode_enabled(st.query_params) and st.button(
        t("artisan.submitted.simulate_review"),
        width="stretch",
    ):
        reviewed = simulate_review_approval(draft, review_authorized=True)
        _artisan_repository().save(reviewed)
        st.session_state["artisan_draft"] = reviewed
        st.session_state["artisan_passport"] = build_passport(reviewed)
        if reviewed.publication_status is PublicationStatus.RECOMMENDABLE:
            st.info(t("artisan.submitted.recommendable_demo"))
        else:
            st.info(t("artisan.submitted.reference_demo"))
    if st.button(t("artisan.add_another"), type="primary", width="stretch"):
        _reset_artisan_flow()
        st.rerun()


def _growth_context_options() -> dict[str, Any]:
    bundle, products = load_catalog()
    passports = build_catalog_passports(products, bundle)
    contexts = {
        product.product_id: build_catalog_growth_context(product, passports[product.product_id])
        for product in products
        if is_recommendation_eligible(product)
    }
    draft = st.session_state.get("artisan_draft")
    if isinstance(draft, ArtisanProductDraft) and draft.facts:
        context = build_draft_growth_context(draft)
        contexts[context.product_id] = context
    return contexts


def _growth_client(output_source: GrowthOutputSource) -> DeepSeekClient | None:
    if output_source is not GrowthOutputSource.LIVE_AI:
        return None
    if os.getenv("LLM_ENABLED", "true").lower() != "true" or not deepseek_is_configured():
        return None
    try:
        return DeepSeekClient.from_env()
    except Exception:
        return None


def _render_growth_studio() -> None:
    render_growth_studio_app(
        _growth_context_options(),
        _campaign_repository(),
        _growth_client,
    )


def _render_artisan_app() -> None:
    onboarding_column, growth_column = st.columns(2)
    if onboarding_column.button(
        t("artisan.workspace_onboarding"),
        key="artisan_workspace_onboarding",
        type=(
            "primary" if st.session_state.get("artisan_workspace") == "onboarding" else "secondary"
        ),
        width="stretch",
    ):
        st.session_state["artisan_workspace"] = "onboarding"
        st.rerun()
    if growth_column.button(
        t("artisan.workspace_growth"),
        key="artisan_workspace_growth",
        type=("primary" if st.session_state.get("artisan_workspace") == "growth" else "secondary"),
        width="stretch",
    ):
        st.session_state["artisan_workspace"] = "growth"
        if st.session_state.get("competition_demo"):
            st.session_state["competition_demo_step"] = 4
        st.rerun()
    if st.session_state.get("artisan_workspace") == "growth":
        _render_growth_studio()
        return
    render_artisan_hero()
    stage = st.session_state.get("artisan_stage", "landing")
    render_artisan_progress(stage)
    if stage == "landing":
        render_artisan_journey()
        if st.button(t("artisan.start"), type="primary", width="stretch"):
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
        return t("buyer.form.needed") if value else t("buyer.form.not_needed")
    reverse = {code: label for label, code in (mapping or {}).items()}
    if isinstance(value, tuple):
        labels = [reverse.get(str(item), str(item)) for item in value]
        if get_language() == Language.EN_US:
            labels = [OPTION_LABELS_EN.get(label, label) for label in labels]
        return " · ".join(labels)
    label = reverse.get(str(value), str(value))
    return OPTION_LABELS_EN.get(label, label) if get_language() == Language.EN_US else label


def _direction_summary(context: RecommendationContext) -> str:
    if get_language() == Language.EN_US:
        return t("buyer.summary.direction_ready")
    return context.direction_summary


def _summary_items(parsed: ParsedCustomerRequest) -> list[tuple[str, str]]:
    rows = (
        (t("buyer.summary.recipient"), _friendly_value(parsed.recipient, RECIPIENTS)),
        (t("buyer.summary.scene"), _friendly_value(parsed.scene, SCENES)),
        (
            t("buyer.summary.budget"),
            f"¥{parsed.budget_per_item:,.0f}" if parsed.budget_per_item else None,
        ),
        (
            t("buyer.summary.quantity"),
            t("buyer.summary.items", count=parsed.quantity) if parsed.quantity else None,
        ),
        (t("buyer.summary.style"), _friendly_value(parsed.style_preferences, STYLES)),
        (t("buyer.summary.meaning"), _friendly_value(parsed.symbolism_preferences, MEANINGS)),
        (t("buyer.summary.customization"), _friendly_value(parsed.customization_required)),
        ("Logo", _friendly_value(parsed.logo_required)),
        (
            t("buyer.summary.delivery"),
            t("buyer.summary.days", days=parsed.required_delivery_days)
            if parsed.required_delivery_days
            else None,
        ),
        (t("buyer.summary.destination"), parsed.destination),
    )
    return [(label, value) for label, value in rows if value]


def _render_conversation() -> None:
    st.markdown(f"## {t('buyer.advisor_title')}")
    state = st.session_state["conversation_state"]
    with st.chat_message("assistant"):
        st.write(t("buyer.welcome"))
    for message in state.messages:
        with st.chat_message(message.role):
            st.write(localize_literal(message.content))
    if not state.raw_user_texts:
        columns = st.columns(2)
        for index, (label_key, text_key) in enumerate(QUICK_START_TRANSLATION_KEYS):
            label = t(label_key)
            if columns[index % 2].button(label, key=f"quick_{index}", width="stretch"):
                _process_message(
                    t(text_key, language=Language.ZH_CN),
                    entry_source=f"quick:{label_key}",
                )
                st.rerun()
    prompt = st.chat_input(t("buyer.chat_placeholder"))
    if prompt:
        _process_message(prompt)
        st.rerun()
    if state.raw_user_texts:
        recommend, restart = st.columns(2)
        if recommend.button(t("buyer.recommend_now"), type="primary", width="stretch"):
            _process_message(
                t("buyer.recommend_now_prompt", language=Language.ZH_CN),
                entry_source="recommend_now",
            )
            st.rerun()
        if restart.button(t("buyer.restart"), width="stretch"):
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
    st.markdown(f"## {t('buyer.summary.title')}")
    items = _summary_items(display)
    if items:
        tags = "".join(f"<span>{escape(label)}：{escape(value)}</span>" for label, value in items)
        st.markdown(f'<div class="hl-summary">{tags}</div>', unsafe_allow_html=True)
    else:
        st.caption(t("buyer.summary.empty"))
    if isinstance(context, RecommendationContext):
        st.write(_direction_summary(context))
    edit, rematch = st.columns(2)
    if edit.button(t("buyer.summary.edit"), width="stretch"):
        st.session_state["show_requirement_editor"] = not st.session_state.get(
            "show_requirement_editor", False
        )
        st.rerun()
    if rematch.button(t("buyer.summary.rematch"), width="stretch"):
        state = st.session_state["conversation_state"]
        st.session_state["conversation_state"] = replace(state, ready_to_recommend=True)
        _generate_recommendations()
        st.rerun()
    if st.session_state.get("show_requirement_editor"):
        with st.container(border=True):
            st.caption(t("buyer.summary.edit_help"))
            if render_structured_form(
                prefix="advisor_edit",
                parsed=display,
                submit_label=t("buyer.summary.save_rematch"),
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


def _recommendation_explanations(
    recommendations: Sequence[Recommendation],
    context: RecommendationContext,
    participating: frozenset[str],
    references: dict[str, HeritageReferenceItem],
) -> dict[str, str]:
    """Phrase the top recommendations once per distinct result set.

    Streamlit reruns the whole script on every interaction, so without the
    session cache each checkbox tick would pay for another LLM call.
    """
    if not recommendations:
        return {}
    language = get_language().value
    signature = "|".join(
        (
            recommendation_signature(context.effective_request),
            language,
            *(item.product.product_id for item in recommendations),
        )
    )
    cached = st.session_state.get("recommendation_explanations")
    if isinstance(cached, dict) and cached.get("signature") == signature:
        return dict(cached.get("explanations", {}))

    explanations, source = recommendation_narrative.explain(
        recommendations,
        request_summary=_direction_summary(context),
        language=language,
        participating=participating,
        references=references,
    )
    st.session_state["recommendation_explanations"] = {
        "signature": signature,
        "explanations": explanations,
        "source": source.value,
    }
    return explanations


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
        st.markdown(f"## {t('buyer.results.title', count=count)}")
        st.write(t("buyer.results.copy"))
    with action:
        if count >= 2 and st.button(
            t("buyer.results.compare_all", count=count),
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
        t("buyer.analytics.label"),
        key="analytics_consent",
        help=t("buyer.analytics.help"),
    )
    if not response.recommendations:
        st.info(t("buyer.results.empty"))
        return
    participating = frozenset(result.participating_dimensions)
    parsed = context.effective_request
    selected_id = st.session_state.get("selected_product_id")
    passports = build_catalog_passports(products, bundle)
    references = _reference_by_demo_product()
    explanations = _recommendation_explanations(
        response.recommendations, context, participating, references
    )
    for rank, recommendation in enumerate(response.recommendations, start=1):
        request = result.request_by_product[recommendation.product.product_id]
        card_action = render_product_card(
            rank,
            recommendation,
            request,
            participating,
            _known_customer_fields(parsed),
            passports.get(recommendation.product.product_id),
            explanations.get(recommendation.product.product_id),
            references.get(recommendation.product.product_id),
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
            t("buyer.comparison.select"),
            key="comparison_select_recommended",
            type="primary",
            width="stretch",
        ):
            _select_product(recommended_id)
            st.rerun()
        if continue_comparing.button(
            t("buyer.comparison.continue"),
            key="comparison_continue",
            width="stretch",
        ):
            st.session_state["comparison_prompt_hint"] = t("buyer.comparison.hint")
            st.rerun()
        if adjust.button(
            t("buyer.comparison.adjust"),
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
        text=t("buyer.comparison.prompt"),
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
    st.markdown(f"## {t('buyer.selected.title')}")
    with st.container(border=True):
        image, detail = st.columns([1, 1.5])
        with image:
            product_image(recommendation.product.image_path, recommendation.product.image_alt_zh)
        with detail:
            product_name = (
                recommendation.product.product_name_en
                if get_language() == Language.EN_US
                else recommendation.product.product_name_zh
            )
            st.markdown(f"### {product_name}")
            st.write(_direction_summary(context))
            budget = context.effective_request.budget_per_item
            budget_fen = _yuan_to_fen(budget) if budget else None
            st.write(
                t(
                    "buyer.selected.quantity_budget",
                    quantity=context.effective_request.quantity
                    or t("buyer.selected.quantity_later"),
                    budget=_money(budget_fen),
                )
            )
        change, generate = st.columns(2)
        if change.button(t("buyer.selected.change"), width="stretch"):
            st.session_state.pop("selected_product_id", None)
            st.session_state.pop("selection_event", None)
            st.session_state.pop("customization_inquiry", None)
            st.rerun()
        if generate.button(t("buyer.selected.generate"), type="primary", width="stretch"):
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
        f'<small>{before}<a href="{url}" target="_blank">{t("buyer.source_link")}</a>'
        f"{after}</small>",
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
    st.markdown(f"## {t('buyer.plan.title')}")
    badges([(t("buyer.plan.selected"), "ok"), (t("buyer.plan.adjustable"), "wait")])
    st.markdown(f"### {t('buyer.plan.customization')}")
    st.write(f"{t('buyer.plan.theme')}: {parsed.requested_theme or _direction_summary(context)}")
    logo = t("buyer.plan.logo_yes") if parsed.logo_required else t("buyer.plan.logo_optional")
    st.write(f"{t('buyer.plan.logo')}: {logo}")
    inscription = parsed.requested_text or t("buyer.plan.inscription_default")
    st.write(f"{t('buyer.plan.inscription')}: {inscription}")
    packaging = parsed.packaging_requirement or t("buyer.plan.packaging_default")
    st.write(f"{t('buyer.plan.packaging')}: {packaging}")
    zh, en = st.tabs((t("buyer.plan.zh_story"), t("buyer.plan.en_story")))
    with zh:
        st.write(content.zh.cultural_story)
        _render_source_note(content.zh.source_note)
    with en:
        st.write(content.en.cultural_story)
        _render_source_note(content.en.source_note)
    st.markdown(f"### {t('buyer.plan.next')}")
    st.write(t("buyer.plan.next_copy"))
    st.download_button(
        t("buyer.plan.download"),
        data=inquiry_to_json(inquiry),
        file_name=f"{inquiry['inquiry_id']}.json",
        mime="application/json",
        width="stretch",
    )


def _render_secondary_form() -> None:
    with st.expander(t("buyer.direct_form")):
        if render_structured_form(prefix="direct", submit_label=t("buyer.direct_submit")):
            try:
                parsed = parsed_from_widgets("direct")
            except RequestValidationError as exc:
                st.info(str(exc))
            else:
                _accept_structured_request(parsed)
                st.rerun()


def _render_catalog() -> None:
    with st.expander(t("buyer.catalog")):
        try:
            items = load_heritage_reference_catalog()
            bundle, products = load_catalog()
            # Partner work is a second source with no museum record behind it,
            # so it gets its own group rather than sitting among rows that all
            # carry an accession number.
            museum_backed = frozenset(item.demo_product_id for item in items)
            render_partner_works(products, bundle.product_texts, museum_backed)
            render_catalog_gallery(
                items,
                products_by_id={product.product_id: product for product in products},
                project_root=ROOT,
            )
        except CatalogDataError:
            st.info(t("buyer.catalog_error"))


def _render_service_note() -> None:
    with st.expander(t("buyer.data_note")):
        st.write(t("buyer.demo_note"))


def _render_agent_trace() -> None:
    if not is_review_mode_enabled(st.query_params):
        return
    traces = (
        st.session_state.get("growth_execution_trace", ())
        if st.session_state.get("app_mode") == "artisan"
        and st.session_state.get("artisan_workspace") == "growth"
        else st.session_state.get("agent_execution_trace", ())
    )
    if st.session_state.get("app_mode") == "artisan":
        application_traces = (
            ()
            if st.session_state.get("artisan_workspace") == "growth"
            else st.session_state.get("artisan_application_trace", ())
        )
    else:
        application_traces = st.session_state.get("application_execution_trace", ())
    st.markdown(f"## {t('trace.title')}")
    if not traces and not application_traces:
        st.caption(t("trace.empty"))
        return
    for trace in traces:
        icon = "✓" if trace.status.value in {"success", "fallback"} else "–"
        with st.expander(
            f"{icon} Skill {trace.sequence_number}：{trace.skill_name} · {trace.status.value}"
        ):
            st.write(f"{t('trace.reason')}：{trace.trigger_reason}")
            st.json(
                {t("trace.input"): trace.input_summary, t("trace.output"): trace.output_summary}
            )
            if trace.fallback_used:
                st.write(f"{t('trace.fallback')}：{trace.fallback_reason or t('common.ready')}")
            st.write(f"{t('trace.duration')}：{trace.duration_ms:.3f} ms")
            for check in trace.safety_checks:
                marker = "✓" if check.passed else "!"
                st.write(f"{marker} {check.check_id}：{check.summary}")
    if application_traces:
        st.markdown(f"### {t('trace.application_actions')}")
    for trace in application_traces:
        with st.expander(
            t(
                "trace.application_action",
                action=trace.action_id,
                status=trace.status.value,
            )
        ):
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

    # Nothing else renders until a side is chosen: the two audiences use
    # different products, and mixing their navigation is what made the earlier
    # single surface read as a demo rather than a site.
    if not st.session_state.get("entry_role"):
        chosen = render_entry_screen()
        if chosen:
            _enter_role(chosen)
            st.rerun()
        return

    _render_mode_switcher()
    if st.session_state.get("competition_demo"):
        requested = render_demo_tour(int(st.session_state.get("competition_demo_step", 1)))
        if requested is not None:
            st.session_state["competition_demo_step"] = clamp_step(requested)
            st.rerun()
    try:
        bundle, products = load_catalog()
    except DataValidationError:
        st.info(t("buyer.load_error"))
        st.stop()
    if st.session_state.get("app_page") == "about":
        render_about_page()
    elif st.session_state["app_mode"] == "artisan":
        _render_artisan_app()
    else:
        render_buyer_hero()
        state = st.session_state.get("conversation_state")
        if isinstance(state, ConversationState) and not state.raw_user_texts:
            render_platform_story()
        _render_conversation()
        _render_secondary_form()
        _render_requirement_summary()
        _render_recommendations(bundle, products)
        _render_catalog()
        _render_service_note()
    _render_agent_trace()
    _render_footer_navigation()


if __name__ == "__main__":
    main()
