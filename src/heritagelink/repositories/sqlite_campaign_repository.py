"""SQLite Campaign repository using the same JSON-payload pattern as Artisan drafts."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from heritagelink.growth_models import MarketingCampaign
from heritagelink.repositories.campaign_serialization import (
    campaign_from_dict,
    campaign_to_dict,
)


class SQLiteCampaignRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS growth_campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    artisan_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_growth_campaign_artisan "
                "ON growth_campaigns(artisan_id, created_at)"
            )

    def save(self, campaign: MarketingCampaign) -> None:
        payload = json.dumps(
            campaign_to_dict(campaign),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO growth_campaigns VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(campaign_id) DO UPDATE SET
                  artisan_id=excluded.artisan_id,
                  product_id=excluded.product_id,
                  status=excluded.status,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    campaign.campaign_id,
                    campaign.artisan_id,
                    campaign.product_id,
                    campaign.status.value,
                    payload,
                    campaign.created_at.isoformat(),
                    campaign.updated_at.isoformat(),
                ),
            )

    def get(self, campaign_id: str) -> MarketingCampaign | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM growth_campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        return campaign_from_dict(json.loads(row[0])) if row else None

    def list_for_artisan(self, artisan_id: str) -> tuple[MarketingCampaign, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM growth_campaigns WHERE artisan_id = ? "
                "ORDER BY created_at DESC, campaign_id DESC",
                (artisan_id,),
            ).fetchall()
        return tuple(campaign_from_dict(json.loads(row[0])) for row in rows)
