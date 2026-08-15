"""PostgreSQL Campaign repository compatible with the existing storage adapters."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import closing
from typing import Any, Protocol

from heritagelink.growth_models import MarketingCampaign
from heritagelink.repositories.campaign_serialization import (
    campaign_from_dict,
    campaign_to_dict,
)


class ConnectionLike(Protocol):
    def cursor(self) -> Any: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...


class PostgresCampaignRepository:
    def __init__(
        self,
        database_url: str,
        *,
        connect: Callable[[str], ConnectionLike] | None = None,
        initialize: bool = True,
    ) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("unsupported PostgreSQL URL")
        self.database_url = database_url
        self._connect_fn = connect or _load_psycopg_connect()
        if initialize:
            self._initialize()

    def _connection(self) -> ConnectionLike:
        return self._connect_fn(self.database_url)

    def _initialize(self) -> None:
        with closing(self._connection()) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS growth_campaigns (
                      campaign_id TEXT PRIMARY KEY,
                      artisan_id TEXT NOT NULL,
                      product_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      payload_json JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_growth_campaign_artisan "
                    "ON growth_campaigns(artisan_id, created_at)"
                )
            connection.commit()

    def save(self, campaign: MarketingCampaign) -> None:
        payload = json.dumps(campaign_to_dict(campaign), ensure_ascii=False)
        with closing(self._connection()) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    INSERT INTO growth_campaigns VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)
                    ON CONFLICT (campaign_id) DO UPDATE SET
                      artisan_id=EXCLUDED.artisan_id,
                      product_id=EXCLUDED.product_id,
                      status=EXCLUDED.status,
                      payload_json=EXCLUDED.payload_json,
                      updated_at=EXCLUDED.updated_at
                    """,
                    (
                        campaign.campaign_id,
                        campaign.artisan_id,
                        campaign.product_id,
                        campaign.status.value,
                        payload,
                        campaign.created_at,
                        campaign.updated_at,
                    ),
                )
            connection.commit()

    def get(self, campaign_id: str) -> MarketingCampaign | None:
        with (
            closing(self._connection()) as connection,
            closing(connection.cursor()) as cursor,
        ):
            cursor.execute(
                "SELECT payload_json FROM growth_campaigns WHERE campaign_id = %s",
                (campaign_id,),
            )
            row = cursor.fetchone()
        return campaign_from_dict(_payload(row[0])) if row else None

    def list_for_artisan(self, artisan_id: str) -> tuple[MarketingCampaign, ...]:
        with (
            closing(self._connection()) as connection,
            closing(connection.cursor()) as cursor,
        ):
            cursor.execute(
                "SELECT payload_json FROM growth_campaigns WHERE artisan_id = %s "
                "ORDER BY created_at DESC, campaign_id DESC",
                (artisan_id,),
            )
            rows = cursor.fetchall()
        return tuple(campaign_from_dict(_payload(row[0])) for row in rows)


def _payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise ValueError("campaign payload must be a JSON object")
    return parsed


def _load_psycopg_connect() -> Callable[[str], ConnectionLike]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required for PostgreSQL campaign storage") from exc
    return psycopg.connect


__all__ = ["PostgresCampaignRepository"]
