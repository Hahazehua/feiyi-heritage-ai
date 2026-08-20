"""Application-layer Artisan Studio workflow with human-controlled facts."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from heritagelink.comparison_models import (
    ApplicationExecutionTrace,
    ApplicationTraceStatus,
    ExplanationSource,
)
from heritagelink.heritage_passport_models import (
    ArtisanProductDraft,
    BilingualProductDraft,
    FactConflict,
    FactGroup,
    FactSource,
    HeritagePassport,
    ProvenancedFact,
    PublicationStatus,
    SourceReference,
    VerificationStatus,
)

COMMERCIAL_FIELDS = frozenset(
    {
        "price_min_fen",
        "price_max_fen",
        "currency",
        "moq",
        "lead_time_days",
        "customization",
        "logo_supported",
        "packaging",
        "dimensions",
        "materials",
        "domestic_shipping",
        "international_shipping",
        "quantity_capacity",
    }
)
CULTURAL_FIELDS = frozenset(
    {
        "craft_name",
        "heritage_item",
        "region",
        "cultural_background",
        "symbolism",
        "craft_process",
    }
)
CONFLICT_FIELDS = frozenset(
    {
        "price_min_fen",
        "price_max_fen",
        "materials",
        "customization",
        "logo_supported",
        "moq",
        "domestic_shipping",
        "international_shipping",
        "lead_time_days",
    }
)
RECOMMENDABLE_REQUIRED_FIELDS = frozenset(
    {
        "product_name_zh",
        "craft_name",
        "region",
        "cultural_background",
        "price_min_fen",
        "price_max_fen",
        "currency",
        "moq",
        "lead_time_days",
        "materials",
        "customization",
        "logo_supported",
        "domestic_shipping",
        "international_shipping",
        "quantity_capacity",
    }
)
UNKNOWN_TEXT_VALUES = frozenset({"", "unknown", "暂不确定", "待确认", "不清楚", "不知道", "待补充"})


class ArtisanDraftRepository(Protocol):
    def save(self, draft: ArtisanProductDraft) -> None: ...

    def get(self, draft_id: str) -> ArtisanProductDraft | None: ...

    def list_for_session(self, session_id: str) -> tuple[ArtisanProductDraft, ...]: ...


class ArtisanDraftExtractionClient(Protocol):
    def extract_artisan_draft(self, payload: dict[str, object]) -> dict[str, object]: ...

    def write_artisan_bilingual(self, payload: dict[str, object]) -> dict[str, object]: ...


def create_draft(
    session_id: str,
    values: dict[str, Any],
    *,
    description: str = "",
    image_name: str | None = None,
    image_bytes: bytes | None = None,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Create an incomplete, non-recommendable draft from explicit artisan inputs."""
    timestamp = now or datetime.now(UTC)
    normalized = dict(values)
    if description.strip():
        normalized["free_description"] = description.strip()
    facts = tuple(
        _unknown_fact(name) if _is_unknown(value) else _provided_fact(name, value)
        for name, value in normalized.items()
    )
    return ArtisanProductDraft(
        draft_id=f"draft_{uuid4().hex[:12]}",
        session_id=session_id,
        created_at=timestamp,
        updated_at=timestamp,
        facts=facts,
        image_name=image_name,
        image_bytes=image_bytes,
    )


def enrich_draft(
    draft: ArtisanProductDraft,
    *,
    client: ArtisanDraftExtractionClient | None = None,
    now: datetime | None = None,
) -> tuple[ArtisanProductDraft, ApplicationExecutionTrace]:
    """Add bounded candidate fields and bilingual copy; manual fallback always works."""
    started = perf_counter()
    timestamp = now or datetime.now(UTC)
    provided = draft.facts_by_name
    description_fact = provided.get("free_description")
    description = (
        str(description_fact.value)
        if description_fact is not None and not _is_unknown(description_fact.value)
        else ""
    )
    candidates = _deterministic_candidates(description)
    narrative_source = "deterministic_fallback"
    if client is not None:
        try:
            raw = client.extract_artisan_draft(_safe_fact_payload(draft))
            candidates.update(_validate_ai_candidates(raw))
            narrative_source = "llm"
        except Exception:
            narrative_source = "deterministic_fallback"

    facts_by_name = dict(provided)
    for name, value in candidates.items():
        existing = facts_by_name.get(name)
        if (existing is not None and not _is_unknown(existing.value)) or _is_unknown(value):
            continue
        facts_by_name[name] = ProvenancedFact(
            field_name=name,
            value=value,
            group=_fact_group(name),
            source=FactSource.AI_INFERRED,
            verification_status=VerificationStatus.PENDING_REVIEW,
            source_note="AI 根据手艺人提供的描述整理，需人工确认",
        )

    facts = list(facts_by_name.values())

    bilingual = _deterministic_bilingual(tuple(facts))
    if client is not None:
        try:
            bilingual = _validate_bilingual(client.write_artisan_bilingual(_safe_facts(facts)))
            narrative_source = "llm"
        except Exception:
            pass
    updated = replace(draft, facts=tuple(facts), bilingual_draft=bilingual, updated_at=timestamp)
    trace = ApplicationExecutionTrace(
        action_id="artisan_product_onboarding",
        status=(
            ApplicationTraceStatus.FALLBACK
            if narrative_source == "deterministic_fallback"
            else ApplicationTraceStatus.SUCCESS
        ),
        input_summary={
            "provided_field_count": len(draft.facts),
            "image_present": draft.image_bytes is not None,
        },
        output_summary={
            "candidate_field_count": sum(fact.source is FactSource.AI_INFERRED for fact in facts),
            "human_confirmation": "required",
            "publication_status": updated.publication_status.value,
            "recommendation_eligibility": False,
        },
        safety_checks=(
            "ai_inferred_not_confirmed",
            "commercial_promises_require_human_confirmation",
            "draft_not_in_buyer_catalog",
        ),
        narrative_source=(
            ExplanationSource.LLM
            if narrative_source == "llm"
            else ExplanationSource.DETERMINISTIC_FALLBACK
        ),
        duration_ms=max(0.0, round((perf_counter() - started) * 1000, 3)),
    )
    return updated, trace


def merge_artisan_values(
    draft: ArtisanProductDraft,
    incoming: dict[str, Any],
    *,
    resolutions: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Merge explicit values while surfacing protected commercial conflicts."""
    timestamp = now or datetime.now(UTC)
    resolutions = resolutions or {}
    current = draft.facts_by_name
    conflicts: list[FactConflict] = []
    updates: dict[str, ProvenancedFact] = dict(current)
    for name, value in incoming.items():
        if _is_unknown(value):
            if name not in current:
                updates[name] = _unknown_fact(name)
            continue
        existing = current.get(name)
        if (
            existing
            and not _is_unknown(existing.value)
            and name in CONFLICT_FIELDS
            and _normalize(existing.value) != _normalize(value)
        ):
            resolution = resolutions.get(name)
            if resolution is not None and _normalize(resolution) not in {
                _normalize(existing.value),
                _normalize(value),
            }:
                raise ValueError("冲突只能保留当前记录或采用本次输入")
            conflicts.append(FactConflict(name, existing.value, value, resolution))
            if resolution is None:
                continue
            value = resolution
        updates[name] = _provided_fact(name, value)
    touched = set(incoming)
    retained_conflicts = [
        conflict
        for conflict in draft.conflicts
        if conflict.field_name not in touched and not conflict.is_resolved
    ]
    return replace(
        draft,
        facts=tuple(updates.values()),
        conflicts=tuple((*retained_conflicts, *conflicts)),
        updated_at=timestamp,
    )


# A fact the buyer transacts on, or that looks externally checkable, is confirmed
# one at a time. Bulk-confirming those would turn "the artisan vouched for this"
# into "the artisan clicked once", which is the whole point of the review step.
# Descriptive facts the artisan supplied themselves carry less consequence and may
# be confirmed together, so that reducing friction does not cost provenance.
INDIVIDUAL_CONFIRMATION_FIELDS = frozenset(
    {
        "price_min_fen",
        "price_max_fen",
        "currency",
        "moq",
        "lead_time_days",
        "quantity_capacity",
        "domestic_shipping",
        "international_shipping",
        "logo_supported",
        "customization",
        "cultural_source_url",
        "heritage_item",
    }
)


def requires_individual_confirmation(fact: ProvenancedFact) -> bool:
    """Whether this fact has to be confirmed on its own rather than in bulk.

    The line is consequence, not origin. A wrong price or lead time is acted on
    by a buyer; a wrong symbolism tag is not. Holding back every AI-proposed
    field would make the bulk action pointless and leave the artisan doing the
    same field-by-field work under a new name.

    Origin still matters where a model could invent something that looks
    checkable — a source URL, a named ICH project — and those sit in the field
    list above. For everything else the artisan reads the value on screen either
    way, and ``source`` keeps recording that a model proposed it.
    """
    return fact.field_name in INDIVIDUAL_CONFIRMATION_FIELDS


def is_ai_proposed(fact: ProvenancedFact) -> bool:
    """Whether to draw the artisan's eye to this value as a model's suggestion."""
    return fact.source is FactSource.AI_INFERRED


def bulk_confirmable_fields(draft: ArtisanProductDraft) -> tuple[str, ...]:
    """Fields eligible for one combined confirmation action.

    Excludes anything unknown (there is nothing to vouch for), anything already
    confirmed, and anything the rule above holds back for individual review.
    """
    return tuple(
        fact.field_name
        for fact in draft.facts
        if fact.field_name != "free_description"
        and not _is_unknown(fact.value)
        and fact.verification_status is not VerificationStatus.CONFIRMED
        and not requires_individual_confirmation(fact)
    )


def confirm_facts(
    draft: ArtisanProductDraft,
    field_names: tuple[str, ...],
    *,
    bilingual_confirmed: bool = False,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Upgrade selected facts only after one explicit human confirmation action."""
    timestamp = now or datetime.now(UTC)
    selected = set(field_names)
    facts = tuple(
        fact.confirm_by_artisan(timestamp)
        if fact.field_name in selected and not _is_unknown(fact.value)
        else fact
        for fact in draft.facts
    )
    bilingual = draft.bilingual_draft
    if bilingual_confirmed and bilingual is not None:
        bilingual = replace(
            bilingual,
            source=FactSource.ARTISAN_CONFIRMED,
            verification_status=VerificationStatus.CONFIRMED,
        )
    return replace(draft, facts=facts, bilingual_draft=bilingual, updated_at=timestamp)


def update_bilingual_draft(
    draft: ArtisanProductDraft,
    values: dict[str, str],
    *,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Apply explicit edits to AI copy while keeping it pending until confirmation."""
    current = draft.bilingual_draft or _deterministic_bilingual(draft.facts)
    allowed = set(BilingualProductDraft.__dataclass_fields__) - {
        "source",
        "verification_status",
    }
    if set(values) - allowed:
        raise ValueError("双语草稿包含未知字段")
    cleaned = {name: value.strip() for name, value in values.items()}
    if any(not value for value in cleaned.values()):
        raise ValueError("双语草稿内容不能为空")
    updated = replace(
        current,
        **cleaned,
        source=FactSource.ARTISAN_PROVIDED,
        verification_status=VerificationStatus.PENDING_REVIEW,
    )
    return replace(
        draft,
        bilingual_draft=updated,
        updated_at=now or datetime.now(UTC),
    )


def submit_for_review(
    draft: ArtisanProductDraft,
    repository: ArtisanDraftRepository,
    *,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Persist an isolated pending record; never publish it to the buyer catalog."""
    timestamp = now or datetime.now(UTC)
    unresolved = tuple(conflict for conflict in draft.conflicts if not conflict.is_resolved)
    if unresolved:
        raise ValueError("仍有资料冲突未选择保留项")
    required = {"product_name_zh", "craft_name"}
    if any(
        name not in draft.facts_by_name or _is_unknown(draft.facts_by_name[name].value)
        for name in required
    ):
        raise ValueError("提交审核前请补充作品名称和工艺")
    submitted = replace(
        draft,
        publication_status=PublicationStatus.PENDING_REVIEW,
        submitted_at=timestamp,
        updated_at=timestamp,
    )
    repository.save(submitted)
    return submitted


def simulate_review_approval(
    draft: ArtisanProductDraft,
    *,
    review_authorized: bool = False,
    now: datetime | None = None,
) -> ArtisanProductDraft:
    """Demo-only review transition; it still does not insert into canonical CSV data."""
    if not review_authorized:
        raise PermissionError("模拟审核仅可在双门 Review/Demo Mode 中执行")
    if draft.publication_status is not PublicationStatus.PENDING_REVIEW:
        raise ValueError("只有 pending_review 草稿可模拟审核")
    timestamp = now or datetime.now(UTC)
    facts = draft.facts_by_name
    fully_confirmed = all(
        name in facts
        and facts[name].verification_status is VerificationStatus.CONFIRMED
        and not _is_unknown(facts[name].value)
        for name in RECOMMENDABLE_REQUIRED_FIELDS
    )
    has_confirmed_source = any(
        name.endswith("_source_url") and fact.verification_status is VerificationStatus.CONFIRMED
        for name, fact in facts.items()
    )
    publication = (
        PublicationStatus.RECOMMENDABLE
        if fully_confirmed and has_confirmed_source and draft.image_bytes
        else PublicationStatus.REFERENCE_ONLY
    )
    return replace(
        draft,
        publication_status=publication,
        reviewed_at=timestamp,
        updated_at=timestamp,
    )


def build_passport(draft: ArtisanProductDraft) -> HeritagePassport:
    facts = draft.facts_by_name
    product_name = _text(facts, "product_name_zh") or "未命名作品"
    craft_name = _text(facts, "craft_name") or "待补充工艺"
    cultural_sources = tuple(
        SourceReference(
            label,
            str(source_fact.value),
            source=source_fact.source,
            verification_status=source_fact.verification_status,
        )
        for label, name in (
            ("文化资料", "cultural_source_url"),
            ("商家资料", "merchant_source_url"),
            ("其他参考", "other_reference_url"),
        )
        if (source_fact := facts.get(name)) is not None and not _is_unknown(source_fact.value)
    )
    commercial = tuple(fact for fact in draft.facts if fact.group is FactGroup.COMMERCIAL)
    cultural = tuple(fact for fact in draft.facts if fact.group is FactGroup.CULTURAL)
    return HeritagePassport(
        passport_id=f"passport_{draft.draft_id.removeprefix('draft_')}",
        product_id=f"pending_{draft.draft_id.removeprefix('draft_')}",
        artisan_or_merchant_name=_text(facts, "artisan_or_merchant_name"),
        product_name_zh=product_name,
        product_name_en=_text(facts, "product_name_en"),
        craft_name=craft_name,
        region=_text(facts, "region"),
        cultural_background_zh=_text(facts, "cultural_background"),
        cultural_background_en=(
            draft.bilingual_draft.craft_background_en if draft.bilingual_draft else None
        ),
        symbolism=_tuple_value(facts.get("symbolism")),
        cultural_sources=cultural_sources,
        commercial_facts=commercial,
        cultural_verification_status=_aggregate_status(cultural),
        commercial_verification_status=_aggregate_status(commercial),
        publication_status=draft.publication_status,
        reviewed_at=draft.reviewed_at,
        bilingual_content=draft.bilingual_draft,
    )


def _provided_fact(name: str, value: Any) -> ProvenancedFact:
    return ProvenancedFact(
        name,
        value,
        _fact_group(name),
        FactSource.ARTISAN_PROVIDED,
        VerificationStatus.PENDING_REVIEW,
        "手艺人本次录入，等待确认",
    )


def _unknown_fact(name: str) -> ProvenancedFact:
    return ProvenancedFact(
        name,
        None,
        _fact_group(name),
        FactSource.UNKNOWN,
        VerificationStatus.UNKNOWN,
        "尚未提供",
    )


def _fact_group(name: str) -> FactGroup:
    if name in COMMERCIAL_FIELDS:
        return FactGroup.COMMERCIAL
    if name in CULTURAL_FIELDS or name.endswith("_source_url"):
        return FactGroup.CULTURAL
    return FactGroup.IDENTITY


def _deterministic_candidates(description: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "铁画" in description:
        values["craft_name"] = "铁画"
    if "芜湖" in description:
        values["region"] = "安徽 · 芜湖"
    if re.search(r"迎客松|迎客|友谊|开放", description):
        values["symbolism"] = tuple(
            word for word in ("迎客", "友谊", "开放") if word in description or word == "迎客"
        )
    if re.search(r"企业礼赠|企业礼品", description):
        values["suggested_gifting_contexts"] = ("企业礼赠", "文化纪念")
    if re.search(r"Logo|logo", description):
        values["logo_supported"] = True
    if "题字" in description:
        values["customization"] = ("题字",)
    price = re.search(r"(\d{2,6})\s*[–—~-]\s*(\d{2,6})\s*元", description)
    if price:
        values["price_min_fen"] = int(price.group(1)) * 100
        values["price_max_fen"] = int(price.group(2)) * 100
        values["currency"] = "CNY"
    return values


def _deterministic_bilingual(
    facts: tuple[ProvenancedFact, ...],
    *,
    confirmed_only: bool = False,
) -> BilingualProductDraft:
    by_name = {
        fact.field_name: fact.value
        for fact in facts
        if not confirmed_only or fact.verification_status is VerificationStatus.CONFIRMED
    }
    name = str(by_name.get("product_name_zh") or "这件作品")
    craft = str(by_name.get("craft_name") or "传统工艺")
    region = str(by_name.get("region") or "来源地域待补充")
    meanings = "、".join(_tuple_value_raw(by_name.get("symbolism"))) or "文化寓意待确认"
    contexts = (
        "、".join(_tuple_value_raw(by_name.get("suggested_gifting_contexts"))) or "适合场景待确认"
    )
    customization = _confirmed_commercial_display(
        facts,
        "customization",
        "定制能力待确认",
    )
    return BilingualProductDraft(
        overview_zh=f"{name}是一件以{craft}为核心表达的作品。",
        overview_en=(
            f"{name} is a work shaped through {craft}, presented for cross-cultural understanding."
        ),
        craft_background_zh=f"工艺：{craft}；地域：{region}。相关背景仍以手艺人确认资料为准。",
        craft_background_en=(
            f"Craft: {craft}. Region: {region}. The background remains subject to "
            "artisan confirmation."
        ),
        cultural_meaning_zh=f"文化寓意：{meanings}。",
        cultural_meaning_en=(
            f"Cultural meaning: {meanings}. This wording remains pending artisan review."
        ),
        gifting_contexts_zh=f"建议礼赠场景：{contexts}。",
        gifting_contexts_en=f"Suggested gifting contexts: {contexts}.",
        customization_zh=customization,
        customization_en=(
            "Customization details require artisan confirmation."
            if "待确认" in customization
            else customization
        ),
    )


def _validate_ai_candidates(payload: dict[str, object]) -> dict[str, Any]:
    allowed = {
        "product_name_zh",
        "product_name_en",
        "craft_name",
        "region",
        "symbolism",
        "suggested_gifting_contexts",
        "customization",
        "logo_supported",
        "price_min_fen",
        "price_max_fen",
        "currency",
    }
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("AI 草稿包含未受控字段")
    return dict(payload)


def _validate_bilingual(payload: dict[str, object]) -> BilingualProductDraft:
    fields = tuple(BilingualProductDraft.__dataclass_fields__)
    content_fields = fields[:10]
    if not isinstance(payload, dict) or set(payload) != set(content_fields):
        raise ValueError("AI 双语草稿字段不完整")
    if any(
        not isinstance(payload[name], str) or not str(payload[name]).strip()
        for name in content_fields
    ):
        raise ValueError("AI 双语草稿必须是非空文本")
    return BilingualProductDraft(**{name: str(payload[name]).strip() for name in content_fields})


def _safe_fact_payload(draft: ArtisanProductDraft) -> dict[str, object]:
    return {"facts": _safe_facts(list(draft.facts))}


def _safe_facts(facts: list[ProvenancedFact] | tuple[ProvenancedFact, ...]) -> dict[str, object]:
    return {fact.field_name: fact.value for fact in facts if fact.value is not None}


def _aggregate_status(facts: tuple[ProvenancedFact, ...]) -> VerificationStatus:
    if not facts:
        return VerificationStatus.UNKNOWN
    if all(fact.verification_status is VerificationStatus.CONFIRMED for fact in facts):
        return VerificationStatus.CONFIRMED
    if all(
        fact.verification_status in {VerificationStatus.UNKNOWN, VerificationStatus.NOT_APPLICABLE}
        for fact in facts
    ):
        return VerificationStatus.UNKNOWN
    return VerificationStatus.PENDING_REVIEW


def _text(facts: dict[str, ProvenancedFact], name: str) -> str | None:
    fact = facts.get(name)
    return str(fact.value).strip() if fact and not _is_unknown(fact.value) else None


def _tuple_value(fact: ProvenancedFact | None) -> tuple[str, ...]:
    return _tuple_value_raw(fact.value if fact else None)


def _tuple_value_raw(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),) if str(value).strip() else ()


def _confirmed_commercial_display(
    facts: tuple[ProvenancedFact, ...], name: str, fallback: str
) -> str:
    fact = next((item for item in facts if item.field_name == name), None)
    if fact is None or fact.verification_status is not VerificationStatus.CONFIRMED:
        return fallback
    return "、".join(_tuple_value(fact)) or str(fact.value)


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(sorted(_normalize(item) for item in value))
    if isinstance(value, Decimal):
        return str(value.normalize())
    return value


def _is_unknown(value: Any) -> bool:
    if value is None or value == () or value == []:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in UNKNOWN_TEXT_VALUES
    return False
