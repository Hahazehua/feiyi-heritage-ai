"""Route post-recommendation shopping turns before requirement extraction.

The router deliberately reuses :class:`RequestedAction`.  It does not parse product
facts, score products, or create a second conversational state machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from heritagelink.agent_models import RequestedAction
from heritagelink.models import RecommendationResponse
from heritagelink.request_parser import ParsedCustomerRequest

_ORDINALS = {"一": 1, "二": 2, "两": 2, "三": 3, "1": 1, "2": 2, "3": 3}
_COMPARE_RE = re.compile(r"比较|对比|区别|差异|怎么选|哪(?:一|个|件|款)|更适合|更好")
_SELECT_RE = re.compile(
    r"(?:那(?:我|就)?|我|就)?\s*(?:选|选择|要)\s*(?:第)?([一二两三123])\s*(?:个|件|款)?"
)
_REFINE_RE = re.compile(
    r"再.{0,10}一点|更(?:现代|传统|简约|典雅|大气|喜庆|温暖|便宜)|"
    r"太传统|不太传统|不要太传统|预算.{0,5}(?:改|调|低|高)|"
    r"不(?:太)?在意价格|类似款|换一批|调整"
)
_EXPLAIN_RE = re.compile(r"为什么|怎么样|文化故事|文化表达|适合.{0,8}吗|有什么特点")

_FOCUS_TERMS: tuple[tuple[str, str], ...] = (
    ("教授|老师|长辈", "recipient"),
    ("商务|合作伙伴|客户", "scene"),
    ("文化|故事|寓意|传承", "culture"),
    ("预算|价格|便宜|贵", "budget"),
    ("现代|传统|简约|典雅|大气", "style"),
    ("定制|Logo|logo|题字|包装", "customization"),
    ("海外|国际|运输|寄", "shipping"),
    ("数量|批量", "quantity"),
    ("交期|多久|天内", "lead_time"),
)


@dataclass(frozen=True, slots=True)
class ShoppingTurnRoute:
    """One bounded application action resolved against the current recommendations."""

    action: RequestedAction
    product_id: str | None = None
    product_ids: tuple[str, ...] = ()
    focus_dimensions: tuple[str, ...] = ()
    focus_recipient: str | None = None
    focus_scene: str | None = None
    focus_styles: tuple[str, ...] = ()
    focus_symbolism: tuple[str, ...] = ()
    focus_customization: tuple[str, ...] = ()
    focus_international: bool | None = None


def route_shopping_turn(
    message: str,
    recommendation_response: RecommendationResponse | None,
) -> ShoppingTurnRoute:
    """Resolve selection, comparison, and refinement without touching product ranking."""
    cleaned = message.strip()
    recommendations = (
        recommendation_response.recommendations if recommendation_response is not None else ()
    )
    if not recommendations:
        return ShoppingTurnRoute(RequestedAction.CONTINUE_CONVERSATION)

    focus = tuple(
        code for pattern, code in _FOCUS_TERMS if re.search(pattern, cleaned, re.IGNORECASE)
    )
    focus_values = _focus_values(cleaned)
    comparison_language = bool(_COMPARE_RE.search(cleaned))

    # A selection must be explicit and must not be part of “我要比较第一个…”.
    selection = _SELECT_RE.search(cleaned)
    if selection and not comparison_language:
        index = _ORDINALS[selection.group(1)] - 1
        if 0 <= index < len(recommendations):
            return ShoppingTurnRoute(
                RequestedAction.SELECT_PRODUCT,
                product_id=recommendations[index].product.product_id,
            )

    if comparison_language:
        positions = _ordinal_positions(cleaned)
        product_ids = tuple(
            recommendations[index - 1].product.product_id
            for index in positions
            if 1 <= index <= len(recommendations)
        )
        if len(product_ids) >= 2:
            return ShoppingTurnRoute(
                RequestedAction.COMPARE_SELECTED_PRODUCTS,
                product_ids=product_ids,
                focus_dimensions=focus,
                **focus_values,
            )
        if len(product_ids) == 1:
            return ShoppingTurnRoute(
                RequestedAction.EXPLAIN_DIFFERENCE,
                product_ids=product_ids,
                focus_dimensions=focus,
                **focus_values,
            )
        return ShoppingTurnRoute(
            RequestedAction.COMPARE_RECOMMENDATIONS,
            product_ids=tuple(item.product.product_id for item in recommendations),
            focus_dimensions=focus,
            **focus_values,
        )

    if _REFINE_RE.search(cleaned):
        return ShoppingTurnRoute(RequestedAction.REFINE_RECOMMENDATIONS)

    if _EXPLAIN_RE.search(cleaned):
        return ShoppingTurnRoute(
            RequestedAction.EXPLAIN_DIFFERENCE,
            product_ids=tuple(item.product.product_id for item in recommendations),
            focus_dimensions=focus,
            **focus_values,
        )

    # A new, recognizable shopping constraint after results is a refinement, even
    # when the user did not say “adjust”.  Social messages remain normal dialogue.
    if re.search(
        r"\d+\s*(?:元|件|份|套|天)|送给|用于|需要|不要|风格|寓意|Logo|logo|海外",
        cleaned,
    ):
        return ShoppingTurnRoute(RequestedAction.REFINE_RECOMMENDATIONS)
    return ShoppingTurnRoute(RequestedAction.CONTINUE_CONVERSATION)


def apply_relative_refinement(
    request: ParsedCustomerRequest,
    message: str,
) -> tuple[ParsedCustomerRequest, frozenset[str]]:
    """Apply only explicit relative overrides after the normal validated merge.

    Ordinary multi-turn preferences still accumulate.  Replacement semantics are
    intentionally limited to phrases such as “再现代一点” and “不要太传统”.
    """
    cleaned = message.strip()
    updated = request
    overrides: set[str] = set()

    style_labels = {
        "现代": "modern",
        "传统": "traditional",
        "简约": "minimal",
        "大气": "grand",
        "典雅": "elegant",
        "喜庆": "festive",
        "温暖": "warm",
    }
    relative_style = bool(re.search(r"再|更|改成|换成|偏向|一点|太传统|不太传统", cleaned))
    if relative_style:
        styles = tuple(tag for label, tag in style_labels.items() if label in cleaned)
        if re.search(r"不要太传统|不太传统|太传统", cleaned):
            styles = tuple(tag for tag in styles if tag != "traditional")
            if "modern" not in styles:
                styles = ("modern", *styles)
        if styles:
            updated = replace(updated, style_preferences=tuple(dict.fromkeys(styles)))
            overrides.add("style_preferences")

    if re.search(r"文化故事|文化表达|文化特色|文化传承", cleaned):
        meanings = tuple(dict.fromkeys((*updated.symbolism_preferences, "heritage")))
        updated = replace(updated, symbolism_preferences=meanings)
        overrides.add("symbolism_preferences")

    if re.search(r"不(?:太)?在意价格|预算不限|取消预算", cleaned):
        updated = replace(
            updated,
            budget_type=None,
            total_budget=None,
            budget_per_item=None,
            uncertain_fields=tuple(
                field
                for field in updated.uncertain_fields
                if field not in {"budget_type", "total_budget", "budget_per_item"}
            ),
        )
        overrides.add("budget_per_item")

    return updated, frozenset(overrides)


def asks_for_unspecified_lower_budget(message: str) -> bool:
    """Return true when “cheaper” has no new numeric budget to enforce."""
    return bool(re.search(r"更便宜|预算再低|降低预算|便宜一点", message)) and not bool(
        re.search(r"\d+(?:\.\d+)?\s*(?:元|块)", message)
    )


def _ordinal_positions(message: str) -> tuple[int, ...]:
    positions = [
        _ORDINALS[value] for value in re.findall(r"第\s*([一二两三123])\s*(?:个|件|款)?", message)
    ]
    if not positions and re.search(r"前\s*(?:两|二|2)\s*(?:个|件|款)", message):
        positions = [1, 2]
    return tuple(dict.fromkeys(positions))


def _focus_values(message: str) -> dict[str, object]:
    recipient = next(
        (
            value
            for pattern, value in (
                (r"教授|老师|教师", "teacher"),
                (r"长辈", "elder"),
                (r"商务伙伴|合作伙伴|客户", "business_partner"),
                (r"朋友", "friend"),
                (r"收藏", "collector"),
            )
            if re.search(pattern, message)
        ),
        None,
    )
    scene = next(
        (
            value
            for pattern, value in (
                (r"商务", "business_gift"),
                (r"周年", "anniversary"),
                (r"答谢", "appreciation"),
                (r"学术|拜访", "appreciation"),
                (r"收藏|陈设", "collection"),
            )
            if re.search(pattern, message)
        ),
        None,
    )
    styles = tuple(
        value
        for label, value in (
            ("现代", "modern"),
            ("传统", "traditional"),
            ("简约", "minimal"),
            ("典雅", "elegant"),
            ("大气", "grand"),
        )
        if label in message
    )
    symbolism = ("heritage",) if re.search(r"文化|故事|传承|中国特色", message) else ()
    customization = tuple(
        value
        for pattern, value in (
            (r"Logo|logo", "logo"),
            (r"题字", "inscription"),
            (r"包装|礼盒", "packaging"),
        )
        if re.search(pattern, message)
    )
    international = True if re.search(r"美国|海外|国际", message) else None
    return {
        "focus_recipient": recipient,
        "focus_scene": scene,
        "focus_styles": styles,
        "focus_symbolism": symbolism,
        "focus_customization": customization,
        "focus_international": international,
    }
