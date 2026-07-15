"""Small, mock-friendly client for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_TOKENS = 1400


class LLMClientError(RuntimeError):
    """Base class for safe, user-facing DeepSeek client failures."""


class MissingAPIKeyError(LLMClientError):
    """Raised when DeepSeek mode is requested without a configured key."""


class LLMAuthenticationError(LLMClientError):
    """Raised for rejected credentials without echoing sensitive details."""


class LLMInsufficientBalanceError(LLMClientError):
    """Raised when the API reports insufficient account balance."""


class LLMTimeoutError(LLMClientError):
    """Raised after the bounded timeout retry is exhausted."""


class LLMNetworkError(LLMClientError):
    """Raised after the bounded network retry is exhausted."""


class LLMEmptyResponseError(LLMClientError):
    """Raised when the API returns no usable assistant content."""


class LLMInvalidJSONError(LLMClientError):
    """Raised when assistant content is not a JSON object."""


class LLMAPIError(LLMClientError):
    """Raised for other API status failures."""


@dataclass(frozen=True, slots=True)
class DeepSeekConfig:
    """DeepSeek configuration loaded without exposing the API key."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = DEFAULT_MAX_TOKENS

    @classmethod
    def from_env(cls) -> DeepSeekConfig:
        """Load local ``.env`` values, with environment variables taking precedence."""
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key or api_key == "your_deepseek_api_key_here":
            raise MissingAPIKeyError("未配置 DeepSeek API Key，将使用演示解析模式。")
        return cls(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        )


class _CompletionsClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _ChatClient(Protocol):
    completions: _CompletionsClient


class _OpenAICompatibleClient(Protocol):
    chat: _ChatClient


SYSTEM_PROMPT = """你是 HeritageLink AI 的礼品需求字段提取器。
只提取用户明确表达或可直接判断的事实，禁止猜测预算、数量、交期、风格、包装，
也禁止推测商家的产能、价格、材料或运输能力。输出必须是一个 JSON 对象，不能输出解释、
Markdown、推理过程或额外文字。缺失信息使用 null 或空列表并加入 missing_fields；有歧义的
字段加入 uncertain_fields，并给出 clarification_questions。

受控值：output_language 只能是“中文”“English”“中英双语”或 null。
recipient、scene、style_preferences、symbolism_preferences 尽量使用以下业务标签：
business_partner/institution/employee/elder/family/friend/newlywed/teacher/collector；
business_gift/commemoration/wedding/anniversary/housewarming/birthday/festival/graduation/
appreciation/collection/exhibition；traditional/modern/minimal/grand/elegant/festive/warm；
heritage/prosperity/blessing/harmony/longevity/resilience/remembrance/gratitude/union。

完整目标 JSON 示例：
{
  "customer_type": "企业客户",
  "recipient": "business_partner",
  "budget_per_item": 1000,
  "quantity": 30,
  "scene": "anniversary",
  "style_preferences": [],
  "symbolism_preferences": ["heritage"],
  "customization_required": true,
  "logo_required": true,
  "destination_country": "United States",
  "international_shipping_required": true,
  "required_delivery_days": 30,
  "output_language": "中英双语",
  "requested_theme": "安徽文化",
  "requested_text": null,
  "packaging_requirement": null,
  "uncertain_fields": ["budget_per_item"],
  "missing_fields": ["requested_text", "packaging_requirement"],
  "clarification_questions": ["1000元是不可超过的单件预算上限吗？"]
}
"""


class DeepSeekClient:
    """Call DeepSeek once, with at most one retry for transient failures."""

    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        client: _OpenAICompatibleClient | None = None,
    ) -> None:
        self.config = config
        self._client = client or OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            max_retries=0,
        )

    @classmethod
    def from_env(cls) -> DeepSeekClient:
        return cls(DeepSeekConfig.from_env())

    def extract_request(self, text: str) -> dict[str, Any]:
        """Return one decoded JSON object or a sanitized domain exception."""
        if not text.strip():
            raise ValueError("礼品需求描述不能为空。")

        last_transient: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text.strip()},
                    ],
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                    max_tokens=self.config.max_tokens,
                    stream=False,
                )
                content = self._response_content(response)
                try:
                    payload = json.loads(content)
                except (json.JSONDecodeError, TypeError) as exc:
                    raise LLMInvalidJSONError("DeepSeek 返回了非法 JSON。") from exc
                if not isinstance(payload, dict):
                    raise LLMInvalidJSONError("DeepSeek 返回内容不是 JSON 对象。")
                return payload
            except AuthenticationError as exc:
                raise LLMAuthenticationError("DeepSeek 认证失败，请检查本地 API Key。") from exc
            except APITimeoutError as exc:
                last_transient = exc
                if attempt == 1:
                    raise LLMTimeoutError("DeepSeek 请求超时，已切换到演示解析模式。") from exc
            except APIConnectionError as exc:
                last_transient = exc
                if attempt == 1:
                    raise LLMNetworkError("DeepSeek 网络连接失败，已切换到演示解析模式。") from exc
            except LLMEmptyResponseError as exc:
                last_transient = exc
                if attempt == 1:
                    raise
            except APIStatusError as exc:
                if exc.status_code == 401:
                    raise LLMAuthenticationError("DeepSeek 认证失败，请检查本地 API Key。") from exc
                if exc.status_code == 402:
                    raise LLMInsufficientBalanceError(
                        "DeepSeek 账户余额不足，已切换到演示解析模式。"
                    ) from exc
                raise LLMAPIError(f"DeepSeek API 暂时不可用（HTTP {exc.status_code}）。") from exc
        raise LLMNetworkError("DeepSeek API 暂时不可用。") from last_transient

    @staticmethod
    def _response_content(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMEmptyResponseError("DeepSeek 返回了空响应。")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMEmptyResponseError("DeepSeek 返回了空响应。")
        return content.strip()
