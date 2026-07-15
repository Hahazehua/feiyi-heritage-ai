from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_real_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never discover a local key or call the real OpenAI-compatible API."""
    # A placeholder prevents python-dotenv from loading a developer's real local key.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("自动化测试禁止真实 DeepSeek 网络请求")

    monkeypatch.setattr(
        "openai.resources.chat.completions.Completions.create",
        fail_network,
    )
