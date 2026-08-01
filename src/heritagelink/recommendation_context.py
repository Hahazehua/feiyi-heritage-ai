"""Recommendation context separating stated facts from inferred soft preferences."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from heritagelink.request_parser import ParsedCustomerRequest


@dataclass(frozen=True, slots=True)
class InferredPreference:
    """One auditable soft preference inferred for recommendation presentation."""

    field_name: str
    value: tuple[str, ...] | str
    reason: str
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("inference confidence 必须在 0 到 1 之间")
        if not self.reason.strip() or not self.source.strip():
            raise ValueError("推断原因和来源不能为空")


@dataclass(frozen=True, slots=True)
class RecommendationContext:
    """Effective request plus provenance used by recommendation and analytics."""

    stated_request: ParsedCustomerRequest
    effective_request: ParsedCustomerRequest
    user_provided_fields: frozenset[str]
    inferred_fields: Mapping[str, InferredPreference]
    direction_summary: str


def readonly_inferences(
    values: dict[str, InferredPreference],
) -> Mapping[str, InferredPreference]:
    return MappingProxyType(dict(values))


def is_provided(value: Any) -> bool:
    """Return whether a validated request field contains a user value."""
    return value is not None and value != "" and value != () and value != []
