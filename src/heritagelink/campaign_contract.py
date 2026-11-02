"""Small shared contract; importing it does not import ADK."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    goal: str = Field(min_length=8, max_length=500)
    channel: Literal["LinkedIn", "Instagram", "Landing Page"] = "LinkedIn"
