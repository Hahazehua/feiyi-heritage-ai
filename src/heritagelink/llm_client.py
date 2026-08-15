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

COMPARISON_SYSTEM_PROMPT = """You are explaining a structured product comparison.
Use only facts in the supplied JSON. Do not invent price, material, customization,
shipping, delivery, capacity, heritage status, or certification. Unknown information
must remain unknown. Explain trade-offs briefly and never claim universal superiority.
Return one JSON object with exactly one string field named explanation.
"""

RECOMMENDATION_SYSTEM_PROMPT = """You are phrasing why each recommended gift fits a
buyer's stated request. The ranking and scoring are already decided; your task is
wording, not judgement. Use only facts in the supplied JSON, including its matched
tags and dimension explanations. Do not invent price, material, dimensions, lead
time, capacity, heritage status, certification, symbolism, or history, and do not
add cultural claims of any kind. Do not re-rank, compare against products that are
not supplied, or contradict the supplied scores. Unknown information must remain
unknown. Write at most three sentences per product, in the language named by the
language field. Return one JSON object with exactly one field named explanations,
whose value maps each supplied product_id to its paragraph.
"""

ARTISAN_EXTRACTION_SYSTEM_PROMPT = """You structure an artisan's own product notes.
Use only values explicitly present in the supplied JSON. Return one JSON object and
only these optional fields: product_name_zh, product_name_en, craft_name, region,
symbolism, suggested_gifting_contexts, customization, logo_supported, price_min_fen,
price_max_fen, currency. Omit unknown values. Do not infer certification, artisan
identity, material, price, MOQ, capacity, lead time, shipping, customization, or any
commercial promise. All output is an unverified candidate for human review.
"""

ARTISAN_BILINGUAL_SYSTEM_PROMPT = """You write a grounded bilingual draft for an
artisan to review. Use only the supplied structured facts, preserve unknowns, and do
not invent cultural history, certification, identity, material, price, customization,
shipping, capacity, delivery, or merchant promises. Return exactly these ten string
fields: overview_zh, overview_en, craft_background_zh, craft_background_en,
cultural_meaning_zh, cultural_meaning_en, gifting_contexts_zh, gifting_contexts_en,
customization_zh, customization_en. Clearly state when information needs confirmation.
"""

GROWTH_MARKET_SYSTEM_PROMPT = """You are HAHA's Market Intelligence specialist.
Return a product-grounded opportunity assessment, not market research. Use only the
verified_facts supplied in JSON. Never invent market size, growth, demand, buyer
statistics, competitors, sales, conversion benchmarks, certification, commercial
capacity, or logistics. Return one JSON object with opportunities (a list of objects
containing segment, fit_score 0-100, reasons, risks), recommended_segment, and summary.
Generate two to four opportunities. Unknown facts must appear as risks, not claims.
"""

GROWTH_STRATEGY_SYSTEM_PROMPT = """You are HAHA's Marketing Strategist. Strategy is
downstream from the supplied market analysis. Use only verified_facts. Return one JSON
object with campaign_goal, target_audience, positioning, value_proposition,
key_messages, content_angles, recommended_channels, cta, risks, things_to_avoid, and
reasoning_summary. Never invent certification, artisan identity, price, inventory,
capacity, lead time, customization, shipping, endorsement, or cultural history.
"""

GROWTH_CREATIVE_SYSTEM_PROMPT = """You are HAHA's Creative specialist. Execute the
supplied strategy without changing its positioning. Use only verified_facts and source
URLs. Return one JSON object with an assets list. Each asset must contain asset_id,
channel, asset_type, content, cta, and claims. Each claim must contain claim_text and
field_name mapped to a supplied verified fact. Never invent certification, artisan
identity, price, inventory, capacity, lead time, customization, shipping, endorsement,
historical age, or superlatives. Unknown facts must be omitted from public copy.
"""


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

    def explain_comparison(self, comparison: dict[str, object]) -> str:
        """Render one grounded narrative from a prevalidated structured comparison."""
        payload = self._extract_json(
            COMPARISON_SYSTEM_PROMPT,
            json.dumps(comparison, ensure_ascii=False),
        )
        if set(payload) != {"explanation"}:
            raise LLMInvalidJSONError("比较说明必须只包含 explanation 字段。")
        explanation = payload["explanation"]
        if not isinstance(explanation, str) or not explanation.strip():
            raise LLMInvalidJSONError("比较说明 explanation 必须是非空字符串。")
        return explanation.strip()

    def explain_recommendations(self, payload: dict[str, object]) -> dict[str, str]:
        """Phrase prescored recommendations, one paragraph per product id.

        Every shown product is explained in a single call: one round trip keeps
        the buyer screen responsive where per-card calls would stall it.
        """
        decoded = self._extract_json(
            RECOMMENDATION_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )
        if set(decoded) != {"explanations"}:
            raise LLMInvalidJSONError("推荐解释必须只包含 explanations 字段。")
        explanations = decoded["explanations"]
        if not isinstance(explanations, dict) or not explanations:
            raise LLMInvalidJSONError("推荐解释 explanations 必须是非空对象。")
        resolved: dict[str, str] = {}
        for product_id, text in explanations.items():
            if not isinstance(text, str) or not text.strip():
                raise LLMInvalidJSONError("每条推荐解释必须是非空字符串。")
            resolved[str(product_id)] = text.strip()
        return resolved

    def extract_artisan_draft(self, payload: dict[str, object]) -> dict[str, object]:
        """Extract bounded onboarding candidates; callers keep them pending review."""
        return self._extract_json(
            ARTISAN_EXTRACTION_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )

    def write_artisan_bilingual(self, payload: dict[str, object]) -> dict[str, object]:
        """Create grounded bilingual copy without upgrading any fact status."""
        return self._extract_json(
            ARTISAN_BILINGUAL_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )

    def analyze_growth_market(self, payload: dict[str, object]) -> dict[str, object]:
        """Return a bounded, product-grounded opportunity assessment."""
        return self._extract_json(
            GROWTH_MARKET_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )

    def build_growth_strategy(self, payload: dict[str, object]) -> dict[str, object]:
        """Return a strategy that cannot upgrade missing product facts."""
        return self._extract_json(
            GROWTH_STRATEGY_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )

    def generate_growth_campaign(self, payload: dict[str, object]) -> dict[str, object]:
        """Generate multi-channel copy from verified facts and an approved strategy."""
        return self._extract_json(
            GROWTH_CREATIVE_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )

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
