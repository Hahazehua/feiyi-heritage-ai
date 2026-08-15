"""Campaign persistence configuration shared by Streamlit and future services."""

from __future__ import annotations

from pathlib import Path

from heritagelink.repositories.campaign_repository import CampaignRepository
from heritagelink.repositories.memory_campaign_repository import MemoryCampaignRepository
from heritagelink.repositories.postgres_campaign_repository import PostgresCampaignRepository
from heritagelink.repositories.sqlite_campaign_repository import SQLiteCampaignRepository


def create_campaign_repository(database_url: str | None) -> CampaignRepository:
    """Create a compatible Memory, SQLite, or PostgreSQL Campaign repository."""
    normalized = (database_url or "").strip()
    if not normalized:
        return MemoryCampaignRepository()
    if normalized.startswith("sqlite:///"):
        path = Path(normalized.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)
        return SQLiteCampaignRepository(path)
    if normalized.startswith(("postgresql://", "postgres://")):
        return PostgresCampaignRepository(normalized)
    raise ValueError("CAMPAIGN_DATABASE_URL supports sqlite:///, postgresql://, or postgres://")


__all__ = ["create_campaign_repository"]
