from __future__ import annotations

from dataclasses import replace
from typing import Any

from heritagelink.conversation_state import ConversationStage, new_conversation
from heritagelink.dialogue_manager import (
    mark_recommendations_shown,
    process_turn,
    recommendation_signature,
    validate_dialogue_envelope,
)
from heritagelink.request_parser import demo_parse_request, to_business_request

COMPLETE_TEXT = (
    "给30位美国合作伙伴准备周年纪念礼物，每件预算1000元，30天内完成，需要加公司Logo和中英文介绍。"
)


def _envelope(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "assistant_message": "信息已整理。",
        "newly_extracted_fields": fields,
        "updated_fields": {},
        "missing_blocking_fields": [],
        "missing_optional_fields": [],
        "uncertain_fields": [],
        "clarification_questions": [],
        "next_question": None,
        "ready_to_recommend": True,
        "recommended_action": "recommend_products",
        "confidence_by_field": {name: 0.95 for name in fields},
    }


class FakeDialogueClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls = 0

    def extract_dialogue_turn(self, **_: Any) -> dict[str, Any]:
        self.calls += 1
        return self.payload


def test_complete_request_recommends_and_optional_question_does_not_block() -> None:
    client = FakeDialogueClient(
        _envelope(
            {
                "budget_type": "per_item",
                "budget_per_item": 1000,
                "quantity": 30,
                "recipient": "business_partner",
                "scene": "anniversary",
                "logo_required": True,
                "customization_required": True,
                "customization_types": ["logo"],
                "international_shipping_required": True,
                "destination": "United States",
                "required_delivery_days": 30,
                "style_preferences": [],
                "symbolism_preferences": [],
            }
        )
    )
    result = process_turn(new_conversation(), COMPLETE_TEXT, client=client)

    assert result.recommended_action == "recommend_products"
    assert result.state.ready_to_recommend
    request, _ = to_business_request(result.state.accumulated_request)  # type: ignore[arg-type]
    assert request.logo_required and request.international_shipping_required


def test_budget_and_quantity_are_asked_in_one_high_value_question() -> None:
    result = process_turn(
        new_conversation(), "送给合作伙伴，用于周年纪念", mode="deterministic_demo"
    )

    assert result.recommended_action == "recommend_products"
    assert result.state.ready_to_recommend
    assert result.next_question is not None
    assert "多少件" in result.next_question and "预算" in result.next_question
    assert result.next_question.count("？") == 1


def test_second_turn_merges_new_fields_instead_of_restarting() -> None:
    first = process_turn(
        new_conversation(), "送给合作伙伴，用于周年纪念", mode="deterministic_demo"
    )
    second = process_turn(first.state, "30件，每件预算1000元", mode="deterministic_demo")

    parsed = second.state.accumulated_request
    assert parsed is not None
    assert parsed.recipient == "business_partner"
    assert parsed.scene == "anniversary"
    assert parsed.quantity == 30
    assert parsed.budget_per_item == 1000
    assert second.recommended_action == "recommend_products"


def test_optional_preferences_do_not_block_recommendation() -> None:
    parsed = demo_parse_request("送给30位合作伙伴的周年礼物，每件预算1000元")
    assert parsed.style_preferences == ()
    state = replace(new_conversation(), accumulated_request=parsed)
    result = process_turn(state, "没有其他要求", mode="deterministic_demo")
    assert result.state.ready_to_recommend


def test_same_signature_does_not_repeat_recommendation() -> None:
    first = process_turn(
        new_conversation(),
        COMPLETE_TEXT,
        client=FakeDialogueClient(
            _envelope(
                {
                    "budget_type": "per_item",
                    "budget_per_item": 1000,
                    "quantity": 30,
                    "recipient": "business_partner",
                    "scene": "anniversary",
                    "style_preferences": [],
                    "symbolism_preferences": [],
                }
            )
        ),
    )
    shown = mark_recommendations_shown(first.state)
    repeated = process_turn(shown, "条件不变", mode="deterministic_demo")

    assert repeated.recommended_action == "show_editable_summary"
    assert repeated.state.last_recommendation_signature == shown.last_recommendation_signature


def test_signature_is_stable_and_changes_with_business_condition() -> None:
    request = demo_parse_request("送给30位合作伙伴的周年礼物，每件预算1000元")
    same = demo_parse_request("送给30位合作伙伴的周年礼物，每件预算1000元")
    changed = demo_parse_request("送给31位合作伙伴的周年礼物，每件预算1000元")
    assert recommendation_signature(request) == recommendation_signature(same)
    assert recommendation_signature(request) != recommendation_signature(changed)


def test_unanswered_questions_never_force_manual_form_or_block_results() -> None:
    state = new_conversation()
    asked: set[str] = set()
    for message in ("我想送礼", "暂时不知道", "还没决定", "先跳过", "继续看看"):
        result = process_turn(state, message, mode="deterministic_demo")
        state = result.state
        assert state.ready_to_recommend
        assert not state.manual_form_required
        if result.next_question:
            assert result.next_question not in asked
            asked.add(result.next_question)
    assert state.current_stage == ConversationStage.PROVISIONAL_RECOMMENDATION


def test_invalid_model_envelope_safely_uses_demo_parser() -> None:
    result = process_turn(
        new_conversation(),
        "送给30位合作伙伴的周年礼物，每件预算1000元",
        client=FakeDialogueClient({"unexpected": "value"}),
    )
    assert result.used_parser_mode == "deterministic_demo"
    assert result.state.accumulated_request is not None


def test_dialogue_envelope_rejects_unknown_actions() -> None:
    payload = _envelope({})
    payload["recommended_action"] = "invent_product"
    try:
        validate_dialogue_envelope(payload)
    except ValueError as exc:
        assert "recommended_action" in str(exc)
    else:
        raise AssertionError("invalid action should be rejected")
