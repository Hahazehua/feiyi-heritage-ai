"""In-memory Campaign repository for local demos and Streamlit sessions."""

from __future__ import annotations

from heritagelink.growth_models import MarketingCampaign


class MemoryCampaignRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.campaigns: dict[str, MarketingCampaign] = {}

    def save(self, campaign: MarketingCampaign) -> None:
        if self.fail:
            raise RuntimeError("campaign storage unavailable")
        self.campaigns[campaign.campaign_id] = campaign

    def get(self, campaign_id: str) -> MarketingCampaign | None:
        if self.fail:
            raise RuntimeError("campaign storage unavailable")
        return self.campaigns.get(campaign_id)

    def list_for_artisan(self, artisan_id: str) -> tuple[MarketingCampaign, ...]:
        if self.fail:
            raise RuntimeError("campaign storage unavailable")
        return tuple(
            sorted(
                (
                    campaign
                    for campaign in self.campaigns.values()
                    if campaign.artisan_id == artisan_id
                ),
                key=lambda campaign: (campaign.created_at, campaign.campaign_id),
                reverse=True,
            )
        )
