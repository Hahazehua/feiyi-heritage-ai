"""Central privacy boundary for review-only Agent execution traces."""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter

from heritagelink.agent_models import SafetyCheckResult, SkillExecutionTrace, SkillStatus
from heritagelink.agent_registry import ALL_SKILLS_BY_ID

_SAFE_KEYS = frozenset(
    {
        "message_count",
        "known_field_count",
        "known_fields",
        "unknown_fields",
        "uncertain_field_count",
        "parser_source",
        "inferred_fields",
        "preserved_unknown_commercial_fields",
        "catalog_total",
        "formally_recommendable",
        "reference_only",
        "hard_filter_remaining",
        "final_recommendation_count",
        "hard_constraints",
        "alternative_count",
        "selected_product_present",
        "source_categories",
        "template_organized",
        "fact_boundary_protected",
        "omitted_fields",
        "plan_type",
        "uses_existing_product",
        "contains_controlled_inference",
        "unknown_commercial_fields_omitted",
        "download_ready",
        "consent_granted",
        "capture_status",
        "idempotency_protected",
        "reason",
        "verified_fact_count",
        "unverified_fact_count",
        "unknown_field_count",
        "opportunity_count",
        "recommended_segment",
        "strategy_channel_count",
        "campaign_asset_count",
        "guardian_issue_count",
        "guardian_approved",
        "risk_level",
        "revision_count",
        "requires_human_review",
        "external_evidence_used",
        "publication_eligibility_changed",
        "generation_source",
    }
)
_PII = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?86[- ]?)?1[3-9]\d{9}|"
    r"(?:postgres(?:ql)?|sqlite)://|api[_ -]?key|system prompt|select\s+.+\s+from)",
    re.IGNORECASE,
)


def safe_summary(values: Mapping[str, object]) -> dict[str, object]:
    """Allow only controlled, aggregate values into a trace."""
    output: dict[str, object] = {}
    for key, value in values.items():
        if key not in _SAFE_KEYS:
            continue
        if (
            isinstance(value, (bool, int, float))
            or value is None
            or isinstance(value, str)
            and len(value) <= 120
            and not _PII.search(value)
        ):
            output[key] = value
        elif isinstance(value, (tuple, list)) and all(
            isinstance(item, str) and len(item) <= 60 and not _PII.search(item) for item in value
        ):
            output[key] = list(value)
    return output


def safety(check_id: str, passed: bool, summary: str) -> SafetyCheckResult:
    return SafetyCheckResult(check_id, passed, summary)


class TraceTimer:
    """Build one trace while keeping timestamps and summaries centralized."""

    def __init__(self, skill_id: str, trigger_reason: str) -> None:
        self.definition = ALL_SKILLS_BY_ID[skill_id]
        self.trigger_reason = trigger_reason
        self.started_at = datetime.now(UTC)
        self.started_counter = perf_counter()

    def finish(
        self,
        status: SkillStatus,
        *,
        input_summary: Mapping[str, object] | None = None,
        output_summary: Mapping[str, object] | None = None,
        fallback_reason: str | None = None,
        safety_checks: tuple[SafetyCheckResult, ...] = (),
    ) -> SkillExecutionTrace:
        completed = datetime.now(UTC)
        return SkillExecutionTrace(
            trace_id=f"trace-{self.definition.order:02d}-{self.definition.skill_id}",
            skill_id=self.definition.skill_id,
            skill_name=self.definition.skill_name,
            sequence_number=self.definition.order,
            status=status,
            trigger_reason=self.trigger_reason[:120],
            input_summary=safe_summary(input_summary or {}),
            output_summary=safe_summary(output_summary or {}),
            fallback_used=status is SkillStatus.FALLBACK or fallback_reason is not None,
            fallback_reason=fallback_reason[:120] if fallback_reason else None,
            safety_checks=safety_checks,
            duration_ms=max(0.0, round((perf_counter() - self.started_counter) * 1000, 3)),
            started_at=self.started_at,
            completed_at=completed,
        )


def skipped_trace(skill_id: str, reason: str) -> SkillExecutionTrace:
    return TraceTimer(skill_id, reason).finish(
        SkillStatus.SKIPPED, output_summary={"reason": reason}
    )


def is_review_mode_enabled(
    query_params: Mapping[str, object],
    environ: Mapping[str, str] | None = None,
) -> bool:
    environment = environ or os.environ
    env_enabled = environment.get("AGENT_REVIEW_MODE_ENABLED", "").lower() == "true"
    query_enabled = str(query_params.get("review_mode", "")) == "1"
    configured_token = environment.get("AGENT_REVIEW_TOKEN", "")
    supplied_token = str(query_params.get("review_token", ""))
    token_enabled = not configured_token or secrets.compare_digest(supplied_token, configured_token)
    return env_enabled and query_enabled and token_enabled
