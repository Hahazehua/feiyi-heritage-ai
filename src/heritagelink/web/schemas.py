"""Strict API input and grounded-output contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Brief(StrictModel):
    query: str = Field(min_length=3, max_length=1500)
    budget_cny: int = Field(default=1200, ge=1, le=100000)
    quantity: int = Field(default=1, ge=1, le=1000)
    lead_days: int | None = Field(default=None, ge=1, le=730)
    international_shipping: bool = False


class InquiryInput(StrictModel):
    brief: Brief
    product_id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    notes: str = Field(default="", max_length=1500)
    consent: Literal[True]
    idempotency_key: str = Field(min_length=16, max_length=80, pattern=r"^[\w-]+$")


class EvidenceClaim(StrictModel):
    text: str = Field(min_length=1, max_length=700)
    source_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=12, max_length=500)


class GroundedAnswer(StrictModel):
    claims: list[EvidenceClaim] = Field(min_length=1, max_length=5)
