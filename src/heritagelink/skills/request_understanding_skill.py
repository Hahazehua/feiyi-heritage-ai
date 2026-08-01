"""Skill 1 wrapper: validate and merge one conversational gift request."""

from __future__ import annotations

from dataclasses import dataclass

from heritagelink.agent_models import AgentRuntimeConfig
from heritagelink.conversation_state import ConversationState
from heritagelink.dialogue_manager import DialogueTurnResult, process_turn


@dataclass(frozen=True, slots=True)
class RequestUnderstandingInput:
    state: ConversationState
    text: str
    runtime: AgentRuntimeConfig


def execute(value: RequestUnderstandingInput) -> DialogueTurnResult:
    mode = "auto" if value.runtime.llm_enabled else "deterministic_demo"
    return process_turn(value.state, value.text, mode=mode)
