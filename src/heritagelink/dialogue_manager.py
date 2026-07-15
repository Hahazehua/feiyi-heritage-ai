"""Multi-turn requirement collection and deterministic clarification policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal, Protocol

from heritagelink.conversation_state import (
    ConversationMessage,
    ConversationStage,
    ConversationState,
)
from heritagelink.llm_client import DeepSeekClient, LLMClientError
from heritagelink.progressive_recommender import (
    known_and_missing_fields,
    recommendation_mode,
)
from heritagelink.request_parser import (
    REQUEST_FIELDS,
    ParsedCustomerRequest,
    RequestValidationError,
    demo_parse_request,
    validate_parsed_payload,
)

DialogueMode = Literal["auto", "deepseek", "deterministic_demo"]
RecommendedAction = Literal[
    "ask_clarification",
    "recommend_products",
    "show_editable_summary",
    "generate_customization_brief",
    "fallback_to_manual_form",
]

CORE_BLOCKING_FIELDS = ("budget_per_item", "quantity", "recipient", "scene")
SUGGESTED_CONSTRAINT_FIELDS = (
    "required_delivery_days",
    "logo_required",
    "international_shipping_required",
)
OPTIONAL_FIELDS = (
    "style_preferences",
    "symbolism_preferences",
    "packaging_requirement",
    "requested_theme",
    "requested_text",
    "additional_notes",
)
ALLOWED_ACTIONS = frozenset(
    {
        "ask_clarification",
        "recommend_products",
        "show_editable_summary",
        "generate_customization_brief",
        "fallback_to_manual_form",
    }
)
QUESTION_GROUPS = (
    (
        ("budget_per_item", "quantity"),
        "这批礼品大约需要多少件，单件预算是多少？",
    ),
    (("recipient",), "主要赠送给哪类对象？"),
    (("scene",), "这批礼品主要用于什么场景？"),
    (("required_delivery_days",), "如果交期是硬性要求，希望多少天内完成？"),
    (("logo_required",), "是否必须加入 Logo 或其他定制内容？"),
    (
        ("international_shipping_required",),
        "是否必须寄往海外；如果是，目的国家或地区是哪里？",
    ),
    (("style_preferences", "symbolism_preferences"), "偏好的风格或文化寓意是什么？"),
    (
        ("packaging_requirement", "requested_theme", "requested_text"),
        "是否有包装、主题或题字方面的偏好？",
    ),
    (("additional_notes",), "还有其他希望商家注意的要求吗？"),
)


class DialogueClient(Protocol):
    def extract_dialogue_turn(
        self,
        *,
        messages: list[dict[str, str]],
        accumulated_request: dict[str, Any],
    ) -> dict[str, Any]: ...


class DialogueValidationError(ValueError):
    """Raised for untrusted dialogue-model envelopes."""


@dataclass(frozen=True, slots=True)
class ValidatedDialogueEnvelope:
    assistant_message: str
    extracted_fields: dict[str, Any]
    next_question: str | None
    recommended_action: RecommendedAction
    confidence_by_field: dict[str, float]


@dataclass(frozen=True, slots=True)
class DialogueTurnResult:
    state: ConversationState
    assistant_message: str
    next_question: str | None
    recommended_action: RecommendedAction
    used_parser_mode: str


def process_turn(
    state: ConversationState,
    user_message: str,
    *,
    mode: DialogueMode = "auto",
    client: DialogueClient | None = None,
) -> DialogueTurnResult:
    """Merge one user turn, ask at most one question, and decide local readiness."""
    cleaned = user_message.strip()
    if not cleaned:
        raise RequestValidationError("对话内容不能为空。")
    if len(cleaned) > 3000:
        raise RequestValidationError("单轮对话不能超过 3000 个字符。")
    if mode not in {"auto", "deepseek", "deterministic_demo"}:
        raise RequestValidationError(f"不支持的对话模式：{mode}")

    envelope: ValidatedDialogueEnvelope | None = None
    parser_mode = "deterministic_demo"
    if mode != "deterministic_demo":
        try:
            active_client = client or DeepSeekClient.from_env()
            raw_envelope = active_client.extract_dialogue_turn(
                messages=[
                    {"role": message.role, "content": message.content} for message in state.messages
                ]
                + [{"role": "user", "content": cleaned}],
                accumulated_request=(
                    parsed_request_payload(state.accumulated_request)
                    if state.accumulated_request
                    else {}
                ),
            )
            envelope = validate_dialogue_envelope(raw_envelope)
            turn_request = validate_parsed_payload(
                envelope.extracted_fields,
                raw_user_text=cleaned,
                parser_mode="deepseek",
            )
            parser_mode = "deepseek"
        except (LLMClientError, DialogueValidationError, RequestValidationError):
            turn_request = demo_parse_request(cleaned)
    else:
        turn_request = demo_parse_request(cleaned)

    accumulated = merge_requests(state.accumulated_request, turn_request, state.raw_user_texts)
    missing_blocking = blocking_fields(accumulated)
    uncertain = accumulated.uncertain_fields
    missing_optional = tuple(
        field for field in OPTIONAL_FIELDS if _is_missing(getattr(accumulated, field))
    )
    missing_constraints = tuple(
        field_name
        for field_name in SUGGESTED_CONSTRAINT_FIELDS
        if _is_missing(getattr(accumulated, field_name))
    )
    question_candidates = tuple(
        dict.fromkeys((*missing_blocking, *missing_constraints, *missing_optional))
    )
    confirmed = state.user_confirmed_fields | frozenset(_provided_fields(turn_request))
    raw_texts = (*state.raw_user_texts, cleaned)
    user_entry = ConversationMessage("user", cleaned)

    signature = recommendation_signature(accumulated)
    action = (
        "recommend_products"
        if signature != state.last_recommendation_signature
        else "show_editable_summary"
    )
    selected = _select_question(question_candidates, state.asked_fields)
    if selected is None:
        next_question = None
        asked_fields = state.asked_fields
        rounds = state.clarification_rounds
    else:
        fields, local_question = selected
        next_question = _safe_model_question(envelope, local_question)
        asked_fields = state.asked_fields | frozenset(fields)
        rounds = state.clarification_rounds + 1
    mode_value = recommendation_mode(accumulated)
    known_fields, unknown_fields = known_and_missing_fields(accumulated)
    coverage = round(len(known_fields) / (len(known_fields) + len(unknown_fields)), 2)
    if action == "recommend_products":
        assistant = "我先根据目前的信息展示推荐。"
    else:
        assistant = "需求与上次推荐相同，已保留当前结果。"
    if next_question:
        assistant = f"{assistant} 如愿意进一步优化：{next_question}"
    stage = (
        ConversationStage.CONFIRMED_RECOMMENDATION
        if not unknown_fields
        else ConversationStage.PROVISIONAL_RECOMMENDATION
    )
    ready = True
    manual = False

    assistant_entry = ConversationMessage("assistant", assistant)
    new_state = ConversationState(
        conversation_id=state.conversation_id,
        messages=(*state.messages, user_entry, assistant_entry),
        raw_user_texts=raw_texts,
        accumulated_request=accumulated,
        missing_blocking_fields=missing_blocking,
        missing_optional_fields=missing_optional,
        uncertain_fields=uncertain,
        clarification_questions=(next_question,) if next_question else (),
        current_stage=stage,
        ready_to_recommend=ready,
        user_confirmed_fields=confirmed,
        last_recommendation_signature=state.last_recommendation_signature,
        clarification_rounds=rounds,
        asked_fields=asked_fields,
        manual_form_required=manual,
        recommendation_mode=mode_value.value,
        information_coverage=coverage,
        known_fields=known_fields,
        unknown_fields=unknown_fields,
    )
    return DialogueTurnResult(
        state=new_state,
        assistant_message=assistant,
        next_question=next_question,
        recommended_action=action,
        used_parser_mode=parser_mode,
    )


def validate_dialogue_envelope(payload: dict[str, Any]) -> ValidatedDialogueEnvelope:
    """Strictly validate the model envelope; readiness fields remain advisory only."""
    required = {
        "assistant_message",
        "newly_extracted_fields",
        "updated_fields",
        "missing_blocking_fields",
        "missing_optional_fields",
        "uncertain_fields",
        "clarification_questions",
        "next_question",
        "ready_to_recommend",
        "recommended_action",
        "confidence_by_field",
    }
    unknown = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    if unknown or missing:
        raise DialogueValidationError(
            f"对话模型字段不完整或未知：missing={missing}, unknown={unknown}"
        )
    assistant = _required_string(payload["assistant_message"], "assistant_message")
    newly = _field_dict(payload["newly_extracted_fields"], "newly_extracted_fields")
    updated = _field_dict(payload["updated_fields"], "updated_fields")
    for field_name in (
        "missing_blocking_fields",
        "missing_optional_fields",
        "uncertain_fields",
        "clarification_questions",
    ):
        _string_list(payload[field_name], field_name)
    next_question = payload["next_question"]
    if next_question is not None and not isinstance(next_question, str):
        raise DialogueValidationError("next_question 必须是字符串或 null")
    if type(payload["ready_to_recommend"]) is not bool:
        raise DialogueValidationError("ready_to_recommend 必须是布尔值")
    action = payload["recommended_action"]
    if action not in ALLOWED_ACTIONS:
        raise DialogueValidationError("recommended_action 不在受控集合中")
    confidence = payload["confidence_by_field"]
    if not isinstance(confidence, dict):
        raise DialogueValidationError("confidence_by_field 必须是对象")
    normalized_confidence: dict[str, float] = {}
    for field_name, value in confidence.items():
        if (
            field_name not in REQUEST_FIELDS
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise DialogueValidationError("confidence_by_field 包含非法字段或数值")
        if not 0 <= value <= 1:
            raise DialogueValidationError("confidence_by_field 必须在 0 到 1 之间")
        normalized_confidence[field_name] = float(value)
    extracted = {**newly, **updated}
    return ValidatedDialogueEnvelope(
        assistant_message=assistant,
        extracted_fields=extracted,
        next_question=next_question.strip() if isinstance(next_question, str) else None,
        recommended_action=action,
        confidence_by_field=normalized_confidence,
    )


def merge_requests(
    existing: ParsedCustomerRequest | None,
    new: ParsedCustomerRequest,
    prior_raw_texts: tuple[str, ...] = (),
) -> ParsedCustomerRequest:
    """Merge explicit fields from a new turn and locally revalidate the result."""
    payload = parsed_request_payload(existing) if existing else {}
    new_payload = parsed_request_payload(new)
    for field_name, value in new_payload.items():
        if not _is_missing(value):
            if field_name in {
                "style_preferences",
                "symbolism_preferences",
                "customization_types",
            }:
                previous = payload.get(field_name, [])
                payload[field_name] = list(dict.fromkeys([*previous, *value]))
            else:
                payload[field_name] = value
    if new.budget_type == "total" and new.total_budget is not None:
        payload["budget_per_item"] = new.budget_per_item
    elif new.budget_type == "per_item":
        payload["total_budget"] = None
    explicit_new = set(_provided_fields(new))
    uncertain = tuple(
        dict.fromkeys(
            [
                *(
                    field
                    for field in (existing.uncertain_fields if existing else ())
                    if field not in explicit_new
                ),
                *new.uncertain_fields,
            ]
        )
    )
    payload["uncertain_fields"] = list(uncertain)
    payload["missing_fields"] = []
    payload["clarification_questions"] = []
    raw_text = "\n".join((*prior_raw_texts, new.raw_user_text))[-3000:]
    return validate_parsed_payload(
        payload,
        raw_user_text=raw_text,
        parser_mode=new.parser_mode,
    )


def parsed_request_payload(request: ParsedCustomerRequest | None) -> dict[str, Any]:
    """Return only schema fields, converting tuples to JSON-ready lists."""
    if request is None:
        return {}
    values = asdict(request)
    return {
        field_name: (
            list(values[field_name])
            if isinstance(values[field_name], tuple)
            else values[field_name]
        )
        for field_name in REQUEST_FIELDS
    }


def blocking_fields(request: ParsedCustomerRequest) -> tuple[str, ...]:
    """Return locally authoritative blockers; optional preferences never block."""
    return tuple(
        field_name
        for field_name in CORE_BLOCKING_FIELDS
        if _is_missing(getattr(request, field_name))
    )


def recommendation_signature(request: ParsedCustomerRequest) -> str:
    """Create a stable signature of fields that can affect recommendation output."""
    relevant = {
        field_name: parsed_request_payload(request).get(field_name)
        for field_name in (
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
        )
    }
    serialized = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def mark_recommendations_shown(state: ConversationState) -> ConversationState:
    """Record the current signature after the UI invokes the recommendation engine."""
    if state.accumulated_request is None or not state.ready_to_recommend:
        raise ValueError("当前会话尚未准备好推荐")
    return replace(
        state,
        current_stage=ConversationStage.SHOWING_RECOMMENDATIONS,
        last_recommendation_signature=recommendation_signature(state.accumulated_request),
    )


def request_revision(state: ConversationState) -> ConversationState:
    """Invalidate old results while preserving accumulated facts for a correction turn."""
    return replace(
        state,
        current_stage=ConversationStage.COLLECTING,
        ready_to_recommend=False,
        last_recommendation_signature=None,
        messages=(
            *state.messages,
            ConversationMessage("assistant", "请告诉我需要修改哪个条件。"),
        ),
    )


def skip_suggested_question(state: ConversationState) -> ConversationState:
    """Let the user keep current recommendations without answering the optional question."""
    if not state.clarification_questions:
        return state
    return replace(
        state,
        clarification_questions=(),
        messages=(
            *state.messages,
            ConversationMessage("assistant", "好的，可以先查看当前推荐，之后随时补充需求。"),
        ),
    )


def _select_question(
    blockers: tuple[str, ...], asked_fields: frozenset[str]
) -> tuple[tuple[str, ...], str] | None:
    blocker_set = set(blockers)
    for fields, question in QUESTION_GROUPS:
        relevant = tuple(field for field in fields if field in blocker_set)
        if relevant and not set(relevant).issubset(asked_fields):
            return relevant, _specific_question(relevant, question)
    return None


def _specific_question(fields: tuple[str, ...], default: str) -> str:
    if fields == ("budget_per_item",):
        return "如果方便，单件预算大约是多少？"
    if fields == ("quantity",):
        return "这批礼品大约需要多少件？"
    if fields == ("style_preferences",):
        return "有偏好的风格吗，例如传统、现代或简约？"
    if fields == ("symbolism_preferences",):
        return "希望礼品重点表达什么文化寓意？"
    return default


def _safe_model_question(envelope: ValidatedDialogueEnvelope | None, local_question: str) -> str:
    if envelope is None or not envelope.next_question:
        return local_question
    question = envelope.next_question.strip()
    if len(question) > 200 or question.count("？") + question.count("?") > 1:
        return local_question
    return question


def _provided_fields(request: ParsedCustomerRequest) -> tuple[str, ...]:
    payload = parsed_request_payload(request)
    return tuple(field_name for field_name, value in payload.items() if not _is_missing(value))


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == () or value == []


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DialogueValidationError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _field_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DialogueValidationError(f"{field_name} 必须是对象")
    unknown = sorted(set(value) - set(REQUEST_FIELDS))
    if unknown:
        raise DialogueValidationError(f"{field_name} 包含未知字段：{unknown}")
    return dict(value)


def _string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise DialogueValidationError(f"{field_name} 必须是字符串列表")
    return tuple(value)
