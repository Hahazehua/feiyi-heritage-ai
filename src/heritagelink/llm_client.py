"""Small, mock-friendly client for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

import json
from typing import Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

from heritagelink.config import DeepSeekConfig
from heritagelink.dialogue_prompt import DIALOGUE_SYSTEM_PROMPT


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


class _CompletionsClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _ChatClient(Protocol):
    completions: _CompletionsClient


class _OpenAICompatibleClient(Protocol):
    chat: _ChatClient


SYSTEM_PROMPT = """你是飞颐礼遇的礼品需求字段提取器。
只提取用户明确表达或可直接判断的事实，禁止猜测预算、数量、交期、风格、包装，
也禁止推测商家的产能、价格、材料或运输能力。输出必须是一个 JSON 对象，不能输出解释、
Markdown、推理过程或额外文字。缺失信息使用 null 或空列表并加入 missing_fields；有歧义的
字段加入 uncertain_fields，并给出 clarification_questions。

受控值：budget_type 只能是 per_item/total；customer_type 只能是
corporate/institution/individual/overseas；output_language 只能是 zh/en/bilingual 或 null。
recipient、scene、style_preferences、symbolism_preferences 尽量使用以下业务标签：
business_partner/institution/employee/elder/family/friend/newlywed/teacher/collector；
business_gift/commemoration/wedding/anniversary/housewarming/birthday/festival/graduation/
appreciation/collection/exhibition；traditional/modern/minimal/grand/elegant/festive/warm；
heritage/prosperity/blessing/harmony/longevity/resilience/remembrance/gratitude/union。

完整目标 JSON 示例：
{
  "customer_type": "corporate",
  "budget_type": "per_item",
  "total_budget": 30000,
  "budget_per_item": 1000,
  "recipient": "business_partner",
  "quantity": 30,
  "scene": "anniversary",
  "style_preferences": [],
  "symbolism_preferences": ["heritage"],
  "customization_required": true,
  "customization_types": ["logo"],
  "logo_required": true,
  "destination": "United States",
  "international_shipping_required": true,
  "required_delivery_days": 30,
  "output_language": "bilingual",
  "requested_theme": "安徽文化",
  "requested_text": null,
  "packaging_requirement": null,
  "additional_notes": null,
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
        config = DeepSeekConfig.from_env()
        if not config.is_configured:
            raise MissingAPIKeyError("未配置 DeepSeek API Key，将使用演示解析模式。")
        return cls(config)

    def extract_request(self, text: str) -> dict[str, Any]:
        """Return one decoded JSON object or a sanitized domain exception."""
        if not text.strip():
            raise ValueError("礼品需求描述不能为空。")

        return self._extract_json(SYSTEM_PROMPT, text.strip())

    def extract_dialogue_turn(
        self,
        *,
        messages: list[dict[str, str]],
        accumulated_request: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract one bounded dialogue action without exposing model reasoning."""
        user_payload = json.dumps(
            {
                "conversation_messages": messages,
                "accumulated_request": accumulated_request,
            },
            ensure_ascii=False,
        )
        return self._extract_json(DIALOGUE_SYSTEM_PROMPT, user_payload)

    def _extract_json(self, system_prompt: str, user_content: str) -> dict[str, Any]:
        """Call the compatible JSON endpoint with one bounded safe retry."""

        last_transient: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
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
