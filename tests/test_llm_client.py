from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError

from heritagelink.llm_client import (
    DeepSeekClient,
    DeepSeekConfig,
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


def test_client_requests_json_and_disables_thinking() -> None:
    client, completions = _client([_response('{"quantity": 30}')])

    assert client.extract_request("30份礼品") == {"quantity": 30}
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "JSON" in call["messages"][0]["content"]  # type: ignore[index]
    assert len(completions.calls) == 1


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
    secret = "sk-do-not-leak-123"
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    response = httpx.Response(401, request=request)
    error = AuthenticationError("bad key " + secret, response=response, body=None)
    client, _ = _client([error], key=secret)

    with pytest.raises(LLMAuthenticationError) as caught:
        client.extract_request("礼品")
    assert secret not in str(caught.value)
