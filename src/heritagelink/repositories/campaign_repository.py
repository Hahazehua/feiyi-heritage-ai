"""Persistence contract for first-class Growth Studio campaigns."""

from __future__ import annotations

from typing import Protocol

from heritagelink.growth_models import MarketingCampaign


class CampaignRepository(Protocol):
    def save(self, campaign: MarketingCampaign) -> None: ...

    def get(self, campaign_id: str) -> MarketingCampaign | None: ...

    def list_for_artisan(self, artisan_id: str) -> tuple[MarketingCampaign, ...]: ...
