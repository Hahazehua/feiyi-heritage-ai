from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError

from heritagelink.config import DEFAULT_DEEPSEEK_MODEL, DeepSeekConfig, deepseek_is_configured
from heritagelink.llm_client import (
    DeepSeekClient,
    LLMAuthenticationError,
    LLMEmptyResponseError,
    LLMInvalidJSONError,
    LLMTimeoutError,
)


class FakeCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _client(
    outcomes: list[object], *, key: str = "test-secret-key"
) -> tuple[DeepSeekClient, FakeCompletions]:
    completions = FakeCompletions(outcomes)
    transport = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = DeepSeekClient(DeepSeekConfig(api_key=key), client=transport)
    return client, completions


def _response(content: str | None) -> object:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_environment_config_is_centralized_and_placeholder_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    config = DeepSeekConfig.from_env()

    assert config.model == DEFAULT_DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert config.is_configured is False
    assert deepseek_is_configured() is False
    assert "your_deepseek_api_key_here" not in repr(config)


def test_client_requests_json_and_disables_thinking() -> None:
    client, completions = _client([_response('{"quantity": 30}')])

    assert client.extract_request("30份礼品") == {"quantity": 30}
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "JSON" in call["messages"][0]["content"]  # type: ignore[index]
    assert len(completions.calls) == 1


def test_dialogue_client_uses_json_envelope_prompt() -> None:
    response = {
        "assistant_message": "请补充预算。",
        "newly_extracted_fields": {"quantity": 30},
    }
    client, completions = _client([_response(json.dumps(response))])

    result = client.extract_dialogue_turn(
        messages=[{"role": "user", "content": "需要30件"}],
        accumulated_request={},
    )

    assert result == response
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert "recommended_action" in call["messages"][0]["content"]  # type: ignore[index]


def test_invalid_json_is_rejected_without_retry() -> None:
    client, completions = _client([_response("not-json")])

    with pytest.raises(LLMInvalidJSONError, match="非法 JSON"):
        client.extract_request("礼品")
    assert len(completions.calls) == 1


def test_empty_response_is_retried_once_then_rejected() -> None:
    client, completions = _client([_response(None), _response("")])

    with pytest.raises(LLMEmptyResponseError, match="空响应"):
        client.extract_request("礼品")
    assert len(completions.calls) == 2


def test_timeout_is_retried_only_once() -> None:
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    client, completions = _client(
        [APITimeoutError(request=request), APITimeoutError(request=request)]
    )

    with pytest.raises(LLMTimeoutError, match="请求超时"):
        client.extract_request("礼品")
    assert len(completions.calls) == 2


def test_authentication_failure_never_leaks_key() -> None:
    secret = "deepseek-test-secret-do-not-leak"
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    response = httpx.Response(401, request=request)
    error = AuthenticationError("bad key " + secret, response=response, body=None)
    client, _ = _client([error], key=secret)

    with pytest.raises(LLMAuthenticationError) as caught:
        client.extract_request("礼品")
    assert secret not in str(caught.value)
