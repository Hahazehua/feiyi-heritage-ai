from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from heritagelink.agent_models import (
    AgentOverallStatus,
    AgentRuntimeConfig,
    AgentSessionState,
    AgentTurnResult,
    CatalogSnapshot,
    RequestedAction,
    SkillStatus,
    UserTurn,
)
from heritagelink.agent_orchestrator import run_agent_turn
from heritagelink.agent_trace import is_review_mode_enabled
from heritagelink.conversation_state import new_conversation
from heritagelink.data_loader import build_products, load_data
from heritagelink.repositories.memory_choice_repository import MemoryChoiceRepository
from heritagelink.shopping_turn_router import route_shopping_turn

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 7, 31, 8, tzinfo=UTC)
NORMAL = "给30位美国合作伙伴准备周年礼品，每件预算1000元，需要Logo，30天内完成。"
CONFLICT = "500件，每件100元，必须Logo，3天交付并寄往美国。"


@pytest.fixture
def catalog() -> CatalogSnapshot:
    bundle = load_data(ROOT / "data" / "demo")
    return CatalogSnapshot(
        bundle=bundle,
        products=build_products(bundle),
        catalog_total=50,
        formally_recommendable=20,
        reference_only=30,
        repository=MemoryChoiceRepository(),
    )


def _state(*, consent: bool = False) -> AgentSessionState:
    return AgentSessionState(
        anonymous_session_id="anon_orchestration_test",
        conversation_state=new_conversation(),
        session_started_at=NOW,
        consent_state=consent,
    )


def _turn(
    action: RequestedAction,
    *,
    text: str = "",
    product_id: str | None = None,
    product_ids: tuple[str, ...] = (),
    comparison_focus: tuple[str, ...] = (),
) -> UserTurn:
    return UserTurn(
        message_id=f"test-{action.value}",
        text=text,
        submitted_at=NOW,
        requested_action=action,
        product_id=product_id,
        product_ids=product_ids,
        comparison_focus=comparison_focus,
    )


def _run_recommendation(
    catalog: CatalogSnapshot,
    *,
    text: str = NORMAL,
    consent: bool = False,
) -> AgentTurnResult:
    return run_agent_turn(
        _turn(RequestedAction.RECOMMEND_NOW, text=text),
        _state(consent=consent),
        catalog,
        AgentRuntimeConfig(llm_enabled=False, analytics_enabled=True),
    )


def test_unified_entry_returns_typed_state_stable_order_and_safe_fallback(
    catalog: CatalogSnapshot,
) -> None:
    result = _run_recommendation(catalog)

    assert isinstance(result, AgentTurnResult)
    assert result.updated_session_state.accumulated_request is not None
    assert [item.sequence_number for item in result.execution_trace] == list(range(1, 8))
    assert len({item.skill_id for item in result.execution_trace}) == 7
    assert all(item.duration_ms >= 0 for item in result.execution_trace)
    assert result.execution_trace[0].status is SkillStatus.FALLBACK
    assert result.execution_trace[0].fallback_reason == "deterministic_parser"
    assert result.execution_trace[-1].status is SkillStatus.SKIPPED


def test_same_input_and_state_keep_business_result_and_trace_shape_stable(
    catalog: CatalogSnapshot,
) -> None:
    first = _run_recommendation(catalog)
    second = _run_recommendation(catalog)

    assert (
        first.updated_session_state.accumulated_request
        == second.updated_session_state.accumulated_request
    )
    assert [item.product.product_id for item in first.recommendation_response.recommendations] == [
        item.product.product_id for item in second.recommendation_response.recommendations
    ]
    assert [(item.skill_id, item.status) for item in first.execution_trace] == [
        (item.skill_id, item.status) for item in second.execution_trace
    ]


def test_one_question_gate_and_immediate_recommendation_gate(catalog: CatalogSnapshot) -> None:
    clarification = run_agent_turn(
        _turn(RequestedAction.CONTINUE_CONVERSATION, text="我想准备一份礼物"),
        _state(),
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )
    immediate = _run_recommendation(catalog, text="我还没有明确想法")

    assert clarification.overall_status is AgentOverallStatus.WAITING_FOR_USER
    assert clarification.clarification_question
    assert clarification.clarification_question.count("？") <= 1
    assert immediate.execution_trace[1].status is SkillStatus.SUCCESS
    assert immediate.execution_trace[2].status is SkillStatus.SUCCESS


def test_hard_conflict_returns_zero_and_blocks_product_skills(catalog: CatalogSnapshot) -> None:
    result = _run_recommendation(catalog, text=CONFLICT)

    assert result.overall_status is AgentOverallStatus.NO_MATCH
    assert result.recommendation_response is not None
    assert not result.recommendation_response.recommendations
    assert result.execution_trace[3].status is SkillStatus.SKIPPED
    assert result.execution_trace[4].status is SkillStatus.SKIPPED


def test_selection_plan_and_no_consent_capture_are_gated(catalog: CatalogSnapshot) -> None:
    recommendation = _run_recommendation(catalog)
    product_id = recommendation.recommendation_response.recommendations[0].product.product_id
    selected = run_agent_turn(
        _turn(RequestedAction.SELECT_PRODUCT, product_id=product_id),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False, analytics_enabled=True),
    )
    planned = run_agent_turn(
        _turn(RequestedAction.GENERATE_PLAN),
        selected.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False, analytics_enabled=True),
    )

    assert selected.execution_trace[3].status is SkillStatus.SUCCESS
    assert selected.execution_trace[4].status is SkillStatus.SKIPPED
    assert selected.execution_trace[5].output_summary["capture_status"] == "skipped_no_consent"
    assert planned.execution_trace[4].status is SkillStatus.SUCCESS
    assert planned.final_plan
    assert planned.execution_trace[5].status is SkillStatus.SKIPPED


def test_consent_saves_and_unavailable_storage_degrades_without_blocking(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog, consent=True)
    product_id = recommendation.recommendation_response.recommendations[0].product.product_id
    saved = run_agent_turn(
        _turn(RequestedAction.SELECT_PRODUCT, product_id=product_id),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False, analytics_enabled=True),
    )
    unavailable = run_agent_turn(
        _turn(RequestedAction.SELECT_PRODUCT, product_id=product_id),
        recommendation.updated_session_state,
        CatalogSnapshot(
            bundle=catalog.bundle,
            products=catalog.products,
            catalog_total=50,
            formally_recommendable=20,
            reference_only=30,
            repository=None,
        ),
        AgentRuntimeConfig(llm_enabled=False, analytics_enabled=True),
    )

    assert saved.execution_trace[5].output_summary["capture_status"] == "saved"
    assert unavailable.execution_trace[5].status is SkillStatus.DEGRADED
    assert unavailable.overall_status is AgentOverallStatus.COMPLETED


def test_trace_excludes_raw_chat_pii_secrets_and_storage_details(
    catalog: CatalogSnapshot,
) -> None:
    raw = "联系我 jane@example.com 或 13800138000；给合作伙伴周年礼物"
    result = _run_recommendation(catalog, text=raw)
    serialized = json.dumps([asdict(item) for item in result.execution_trace], default=str)

    for forbidden in (
        raw,
        "jane@example.com",
        "13800138000",
        "api_key",
        "system prompt",
        "postgresql://",
        "sqlite:///",
    ):
        assert forbidden.lower() not in serialized.lower()


def test_review_mode_requires_environment_and_query_parameter() -> None:
    assert not is_review_mode_enabled({}, {})
    assert not is_review_mode_enabled({"review_mode": "1"}, {})
    assert not is_review_mode_enabled({}, {"AGENT_REVIEW_MODE_ENABLED": "true"})
    assert is_review_mode_enabled({"review_mode": "1"}, {"AGENT_REVIEW_MODE_ENABLED": "true"})
    protected = {
        "AGENT_REVIEW_MODE_ENABLED": "true",
        "AGENT_REVIEW_TOKEN": "review-secret",
    }
    assert not is_review_mode_enabled({"review_mode": "1"}, protected)
    assert not is_review_mode_enabled({"review_mode": "1", "review_token": "wrong"}, protected)
    assert is_review_mode_enabled({"review_mode": "1", "review_token": "review-secret"}, protected)


def test_app_source_uses_unified_entry_without_direct_skill_orchestration() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "run_agent_turn(" in source
    for forbidden in (
        "process_turn(",
        "recommend_progressively(",
        "generate_bilingual_content(",
        "build_customization_inquiry(",
        "persist_recommendation_choice(",
    ):
        assert forbidden not in source


def test_comparison_is_a_separate_application_action_and_skips_all_seven_skills(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog)
    current = tuple(
        item.product.product_id for item in recommendation.recommendation_response.recommendations
    )
    original_response = recommendation.updated_session_state.recommendation_result.response

    compared = run_agent_turn(
        UserTurn(
            message_id="compare-first-third",
            text="第一个和第三个哪个更适合教授？",
            submitted_at=NOW,
            requested_action=RequestedAction.COMPARE_SELECTED_PRODUCTS,
            product_ids=(current[0], current[2]),
            comparison_focus=("recipient",),
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    skill_ids = {trace.skill_id for trace in compared.execution_trace}
    assert compared.comparison_result is not None
    assert compared.comparison_result.compared_product_ids == (current[0], current[2])
    assert compared.recommendation_response is original_response
    assert len(compared.execution_trace) == 7
    assert all(trace.status is SkillStatus.SKIPPED for trace in compared.execution_trace)
    assert compared.execution_trace[0].skill_id == "understand_gift_request"
    assert compared.execution_trace[-1].skill_id == "analyze_gift_choice_signals"
    assert skill_ids == {
        "understand_gift_request",
        "infer_soft_preferences",
        "recommend_heritage_gifts",
        "compose_grounded_content",
        "build_final_gift_plan",
        "capture_consented_choice",
        "analyze_gift_choice_signals",
    }
    assert len(compared.application_trace) == 1
    assert compared.application_trace[0].action_id == "product_comparison"
    assert "product_comparison" not in skill_ids
    assert compared.application_trace[0].output_summary["original_ranking_preserved"] is True


def test_comparison_context_survives_selection_and_selection_uses_current_result(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog)
    first_id = recommendation.recommendation_response.recommendations[0].product.product_id
    compared = run_agent_turn(
        UserTurn(
            message_id="compare-all-before-select",
            text="帮我比较这三个",
            submitted_at=NOW,
            requested_action=RequestedAction.COMPARE_RECOMMENDATIONS,
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    selected = run_agent_turn(
        _turn(RequestedAction.SELECT_PRODUCT, product_id=first_id),
        compared.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    assert selected.updated_session_state.selected_product_id == first_id
    assert selected.updated_session_state.comparison_result == compared.comparison_result
    assert selected.updated_session_state.comparison_history == (compared.comparison_result,)
    assert selected.overall_status is AgentOverallStatus.COMPLETED


def test_comparison_follow_up_uses_the_recipient_named_in_this_turn(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog, text=NORMAL)
    message = "第一个和第三个哪个更适合教授？"
    route = route_shopping_turn(message, recommendation.recommendation_response)

    compared = run_agent_turn(
        UserTurn(
            message_id="compare-for-professor",
            text=message,
            submitted_at=NOW,
            requested_action=route.action,
            product_ids=route.product_ids,
            comparison_focus=route.focus_dimensions,
            focus_recipient=route.focus_recipient,
            focus_scene=route.focus_scene,
            focus_styles=route.focus_styles,
            focus_symbolism=route.focus_symbolism,
            focus_customization=route.focus_customization,
            focus_international=route.focus_international,
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    assert compared.comparison_result is not None
    assert all(
        item.recipient_fit.state.value == "verified_no" for item in compared.comparison_result.items
    )


def test_comparison_follow_up_honors_the_explicit_dimension_focus(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog, text=NORMAL)
    message = "第一个和第三个哪个文化故事更好讲？"
    route = route_shopping_turn(message, recommendation.recommendation_response)

    compared = run_agent_turn(
        UserTurn(
            message_id="compare-culture-focus",
            text=message,
            submitted_at=NOW,
            requested_action=route.action,
            product_ids=route.product_ids,
            comparison_focus=route.focus_dimensions,
            focus_recipient=route.focus_recipient,
            focus_scene=route.focus_scene,
            focus_styles=route.focus_styles,
            focus_symbolism=route.focus_symbolism,
            focus_customization=route.focus_customization,
            focus_international=route.focus_international,
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    assert compared.comparison_result is not None
    assert compared.comparison_result.comparison_dimensions[0].value == "culture"


def test_refinement_clears_stale_comparison_and_overrides_traditional_with_modern(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(
        catalog,
        text="送给合作伙伴的周年礼物，希望风格传统",
    )
    compared = run_agent_turn(
        UserTurn(
            message_id="compare-before-refine",
            text="帮我比较这三个",
            submitted_at=NOW,
            requested_action=RequestedAction.COMPARE_RECOMMENDATIONS,
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    refined = run_agent_turn(
        UserTurn(
            message_id="refine-modern",
            text="再现代一点",
            submitted_at=NOW,
            requested_action=RequestedAction.REFINE_RECOMMENDATIONS,
        ),
        compared.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    parsed = refined.updated_session_state.accumulated_request
    assert parsed is not None
    assert parsed.style_preferences == ("modern",)
    assert "traditional" not in parsed.style_preferences
    assert "style_preferences" in refined.updated_session_state.user_overrides
    assert refined.updated_session_state.comparison_result is None
    assert refined.recommendation_response is not None
    assert refined.recommendation_response.recommendations


def test_restart_clears_comparison_result_and_session_only_history(
    catalog: CatalogSnapshot,
) -> None:
    recommendation = _run_recommendation(catalog)
    compared = run_agent_turn(
        UserTurn(
            message_id="compare-before-restart",
            text="帮我比较这三个",
            submitted_at=NOW,
            requested_action=RequestedAction.COMPARE_RECOMMENDATIONS,
        ),
        recommendation.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )
    assert compared.updated_session_state.comparison_history

    restarted = run_agent_turn(
        _turn(RequestedAction.RESTART),
        compared.updated_session_state,
        catalog,
        AgentRuntimeConfig(llm_enabled=False),
    )

    assert restarted.updated_session_state.comparison_result is None
    assert restarted.updated_session_state.comparison_history == ()
    assert restarted.updated_session_state.recommendation_result is None
    assert restarted.updated_session_state.selected_product_id is None
