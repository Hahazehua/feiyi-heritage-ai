"""Typed contracts shared by the HeritageLink Agent and its seven Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from heritagelink.analytics_models import RecommendationEvent, SelectionEvent
from heritagelink.content import BilingualContent
from heritagelink.conversation_state import ConversationMessage, ConversationState
from heritagelink.models import DataBundle, Product, RecommendationResponse
from heritagelink.progressive_recommender import ProgressiveRecommendationResult
from heritagelink.recommendation_context import RecommendationContext
from heritagelink.repositories.choice_repository import ChoiceRepository
from heritagelink.request_parser import ParsedCustomerRequest


class RequestedAction(StrEnum):
    CONTINUE_CONVERSATION = "continue_conversation"
    RECOMMEND_NOW = "recommend_now"
    ADJUST_REQUIREMENT = "adjust_requirement"
    SELECT_PRODUCT = "select_product"
    GENERATE_PLAN = "generate_plan"
    RESTART = "restart"


class SkillStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FALLBACK = "fallback"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    FAILED_SAFE = "failed_safe"


class AgentOverallStatus(StrEnum):
    COMPLETED = "completed"
    WAITING_FOR_USER = "waiting_for_user"
    NO_MATCH = "no_match"
    DEGRADED = "degraded"
    FAILED_SAFE = "failed_safe"


@dataclass(frozen=True, slots=True)
class UserTurn:
    message_id: str
    text: str
    submitted_at: datetime
    requested_action: RequestedAction
    source: str = "chat"
    product_id: str | None = None
    structured_request: ParsedCustomerRequest | None = None

    def __post_init__(self) -> None:
        if not self.message_id.strip() or not self.source.strip():
            raise ValueError("message_id 和 source 不能为空")
        if self.submitted_at.tzinfo is None:
            raise ValueError("submitted_at 必须包含时区")


@dataclass(frozen=True, slots=True)
class AgentRuntimeConfig:
    review_mode_enabled: bool = False
    llm_enabled: bool = True
    analytics_enabled: bool = False
    maximum_clarification_turns: int = 5
    app_version: str = "0.1.0"
    trace_level: str = "safe_summary"

    def __post_init__(self) -> None:
        if self.maximum_clarification_turns < 0:
            raise ValueError("maximum_clarification_turns 不能为负数")
        if self.trace_level not in {"off", "safe_summary"}:
            raise ValueError("trace_level 仅支持 off 或 safe_summary")


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    bundle: DataBundle
    products: tuple[Product, ...]
    catalog_total: int
    formally_recommendable: int
    reference_only: int
    repository: ChoiceRepository | None = None


@dataclass(frozen=True, slots=True)
class SafetyCheckResult:
    check_id: str
    passed: bool
    summary: str


@dataclass(frozen=True, slots=True)
class SkillExecutionTrace:
    trace_id: str
    skill_id: str
    skill_name: str
    sequence_number: int
    status: SkillStatus
    trigger_reason: str
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    fallback_used: bool
    fallback_reason: str | None
    safety_checks: tuple[SafetyCheckResult, ...]
    duration_ms: float
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class AgentSessionState:
    """Wrap the existing conversation state instead of creating a competing state."""

    anonymous_session_id: str
    conversation_state: ConversationState
    session_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    entry_source: str = "direct"
    user_overrides: frozenset[str] = field(default_factory=frozenset)
    recommendation_context: RecommendationContext | None = None
    recommendation_result: ProgressiveRecommendationResult | None = None
    recommendation_event: RecommendationEvent | None = None
    selected_product_id: str | None = None
    selection_event: SelectionEvent | None = None
    grounded_content: BilingualContent | None = None
    final_plan: dict[str, Any] | None = None
    consent_state: bool = False

    @property
    def messages(self) -> tuple[ConversationMessage, ...]:
        return self.conversation_state.messages

    @property
    def accumulated_request(self) -> ParsedCustomerRequest | None:
        return self.conversation_state.accumulated_request

    @property
    def inferred_fields(self) -> tuple[str, ...]:
        if self.recommendation_context is None:
            return ()
        return tuple(self.recommendation_context.inferred_fields)

    @property
    def clarification_turn_count(self) -> int:
        return self.conversation_state.clarification_rounds

    @property
    def current_stage(self) -> str:
        return self.conversation_state.current_stage.value

    @property
    def last_recommendation_signature(self) -> str | None:
        return self.conversation_state.last_recommendation_signature


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    customer_response: str
    updated_session_state: AgentSessionState
    recommendation_response: RecommendationResponse | None
    clarification_question: str | None
    final_plan: dict[str, Any] | None
    available_actions: tuple[RequestedAction, ...]
    execution_trace: tuple[SkillExecutionTrace, ...]
    overall_status: AgentOverallStatus
