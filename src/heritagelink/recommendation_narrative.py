"""Turn prescored recommendations into readable "why this fits" copy.

The scoring in :mod:`heritagelink.recommender` already decides what matched and
by how much; it just reads as a scoreboard.  This module hands that verdict to
the language model for phrasing only, and never for judgement — the payload
carries the dimension explanations and matched tags verbatim, and the prompt
forbids adding price, material, provenance or cultural claims.

When no key is configured, or the call fails for any reason, the deterministic
scoreboard is returned instead, so the buyer screen renders identically minus
the prose.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from heritagelink.catalog import HeritageReferenceItem
from heritagelink.comparison_models import ExplanationSource
from heritagelink.config import DeepSeekConfig
from heritagelink.llm_client import DeepSeekClient, LLMClientError, MissingAPIKeyError
from heritagelink.models import Recommendation

LOGGER = logging.getLogger(__name__)

# Explaining beyond the first few costs latency the buyer screen cannot spend,
# and nobody reads past them during a demo.
MAX_EXPLAINED = 3

# This call sits on the path to the recommendation screen, so the whole budget
# is what a person will watch: one attempt, no retry, twelve seconds. Six with
# a retry had the same worst case but gave a legitimately slow generation — six
# paragraphs across three products — no room to finish. Prose is an
# enhancement; the scoreboard renders either way.
EXPLANATION_TIMEOUT_SECONDS = 12.0
EXPLANATION_MAX_ATTEMPTS = 1


def _time_boxed_client() -> DeepSeekClient:
    """A client that gives up quickly, because the buyer is waiting."""
    config = DeepSeekConfig.from_env()
    if not config.is_configured:
        raise MissingAPIKeyError("未配置 DeepSeek API Key，推荐解释使用确定性评分。")
    return DeepSeekClient(
        replace(config, timeout_seconds=EXPLANATION_TIMEOUT_SECONDS),
        max_attempts=EXPLANATION_MAX_ATTEMPTS,
    )


def build_payload(
    recommendations: Sequence[Recommendation],
    *,
    request_summary: str,
    language: str,
    participating: Iterable[str],
    references: Mapping[str, HeritageReferenceItem] | None = None,
) -> dict[str, object]:
    """Collect the grounded facts the model is allowed to draw on.

    Depth has to come from more sourced material, not a longer leash: asked for
    detail with only a scoreboard to work from, a model pads. The museum block
    is what it can legitimately expand on, and every field in it is a CC0
    museum record with an accession number behind it.
    """
    keys = set(participating)
    lookup = references or {}
    products: list[dict[str, object]] = []
    for recommendation in recommendations[:MAX_EXPLAINED]:
        product_id = recommendation.product.product_id
        dimensions = [
            {
                "dimension": key,
                "score": round(float(dimension.score), 2),
                "max_score": dimension.max_score,
                "explanation": dimension.explanation,
            }
            for key, dimension in recommendation.score_breakdown.items()
            if key in keys
        ]
        product: dict[str, object] = {
            "product_id": product_id,
            "product_name": recommendation.product.product_name_zh,
            "total_score": round(float(recommendation.total_score), 2),
            "matched_tags": list(recommendation.matched_tags),
            "risks": list(recommendation.risks),
            "dimensions": dimensions,
        }
        reference = lookup.get(product_id)
        if reference is not None:
            product["museum_reference"] = {
                "holding_institution": reference.source_name,
                "accession_number": reference.source_object_number,
                "object_name": reference.product_name_zh,
                "craft": reference.craft_category_zh,
                "period": reference.period_text,
                "region": reference.region_text,
                "material": reference.material_text,
            }
        products.append(product)
    return {
        "language": language,
        "buyer_request": request_summary,
        "products": products,
    }


def explain(
    recommendations: Sequence[Recommendation],
    *,
    request_summary: str,
    language: str,
    participating: Iterable[str],
    references: Mapping[str, HeritageReferenceItem] | None = None,
    client: DeepSeekClient | None = None,
) -> tuple[dict[str, str], ExplanationSource]:
    """Return product_id -> paragraph, and which source produced it.

    A partial response is treated as success for the ids it does cover; callers
    fall back to the scoreboard for anything missing.
    """
    if not recommendations:
        return {}, ExplanationSource.DETERMINISTIC_FALLBACK

    payload = build_payload(
        recommendations,
        request_summary=request_summary,
        language=language,
        participating=participating,
        references=references,
    )
    if not payload["products"]:
        return {}, ExplanationSource.DETERMINISTIC_FALLBACK

    try:
        resolved = (client or _time_boxed_client()).explain_recommendations(payload)
    except LLMClientError as error:
        # Never surface the provider error: a missing key is a normal
        # configuration, not a failure the buyer should read about.
        LOGGER.info("推荐解释回退到确定性评分：%s", type(error).__name__)
        return {}, ExplanationSource.DETERMINISTIC_FALLBACK
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("推荐解释意外失败，回退到确定性评分。")
        return {}, ExplanationSource.DETERMINISTIC_FALLBACK

    wanted = {item["product_id"] for item in payload["products"]}  # type: ignore[index]
    explanations = {
        product_id: text for product_id, text in resolved.items() if product_id in wanted
    }
    if not explanations:
        return {}, ExplanationSource.DETERMINISTIC_FALLBACK
    return explanations, ExplanationSource.LLM


__all__ = ["MAX_EXPLAINED", "build_payload", "explain"]
