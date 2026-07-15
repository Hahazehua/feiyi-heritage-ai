from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_real_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never discover a local key or call the real OpenAI-compatible API."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("自动化测试禁止真实 DeepSeek 网络请求")

    monkeypatch.setattr(
        "openai.resources.chat.completions.Completions.create",
        fail_network,
    )
