"""Validated, UI-independent state for the conversational gift advisor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from heritagelink.request_parser import ParsedCustomerRequest


class ConversationStage(StrEnum):
    EXPLORING = "exploring"
    PROVISIONAL_RECOMMENDATION = "provisional_recommendation"
    REFINING = "refining"
    CONFIRMED_RECOMMENDATION = "confirmed_recommendation"
    COLLECTING = "collecting"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_TO_RECOMMEND = "ready_to_recommend"
    SHOWING_RECOMMENDATIONS = "showing_recommendations"
    CUSTOMIZATION_BRIEF = "customization_brief"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """One displayable chat message."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"user", "assistant"}:
            raise ValueError("conversation message role 必须是 user 或 assistant")
        if not self.content.strip():
            raise ValueError("conversation message content 不能为空")


@dataclass(frozen=True, slots=True)
class ConversationState:
    """Complete state required to safely resume a Streamlit conversation."""

    conversation_id: str
    messages: tuple[ConversationMessage, ...] = ()
    raw_user_texts: tuple[str, ...] = ()
    accumulated_request: ParsedCustomerRequest | None = None
    missing_blocking_fields: tuple[str, ...] = ()
    missing_optional_fields: tuple[str, ...] = ()
    uncertain_fields: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()
    current_stage: ConversationStage = ConversationStage.COLLECTING
    ready_to_recommend: bool = False
    user_confirmed_fields: frozenset[str] = field(default_factory=frozenset)
    last_recommendation_signature: str | None = None
    clarification_rounds: int = 0
    asked_fields: frozenset[str] = field(default_factory=frozenset)
    manual_form_required: bool = False
    recommendation_mode: str = "exploring"
    information_coverage: float = 0.0
    known_fields: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.conversation_id.strip():
            raise ValueError("conversation_id 不能为空")
        if self.clarification_rounds < 0:
            raise ValueError("clarification_rounds 不能为负数")
        if not 0 <= self.information_coverage <= 1:
            raise ValueError("information_coverage 必须在 0 到 1 之间")
        if self.ready_to_recommend and self.accumulated_request is None:
            raise ValueError("没有 accumulated_request 时不能标记为可推荐")


def new_conversation() -> ConversationState:
    """Create a fresh local conversation without persistence or personal data."""
    return ConversationState(conversation_id=f"conv_demo_{uuid4().hex[:12]}")
