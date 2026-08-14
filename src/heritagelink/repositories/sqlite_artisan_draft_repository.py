"""Local SQLite repository for Artisan Studio drafts."""

from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from heritagelink.heritage_passport_models import (
    ArtisanProductDraft,
    BilingualProductDraft,
    FactConflict,
    FactGroup,
    FactSource,
    ProvenancedFact,
    PublicationStatus,
    VerificationStatus,
)


class SQLiteArtisanDraftRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS artisan_drafts (
                    draft_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    publication_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_artisan_draft_session "
                "ON artisan_drafts(session_id, created_at)"
            )

    def save(self, draft: ArtisanProductDraft) -> None:
        payload = json.dumps(_serialize(draft), ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artisan_drafts VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET
                  session_id=excluded.session_id,
                  publication_status=excluded.publication_status,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    draft.draft_id,
                    draft.session_id,
                    draft.publication_status.value,
                    payload,
                    draft.created_at.isoformat(),
                    draft.updated_at.isoformat(),
                ),
            )

    def get(self, draft_id: str) -> ArtisanProductDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM artisan_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        return _deserialize(json.loads(row[0])) if row else None

    def list_for_session(self, session_id: str) -> tuple[ArtisanProductDraft, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM artisan_drafts WHERE session_id = ? "
                "ORDER BY created_at, draft_id",
                (session_id,),
            ).fetchall()
        return tuple(_deserialize(json.loads(row[0])) for row in rows)


def _serialize(draft: ArtisanProductDraft) -> dict[str, object]:
    payload = asdict(draft)
    for key in ("created_at", "updated_at", "submitted_at", "reviewed_at"):
        value = getattr(draft, key)
        payload[key] = value.isoformat() if value else None
    payload["publication_status"] = draft.publication_status.value
    payload["image_bytes"] = (
        base64.b64encode(draft.image_bytes).decode() if draft.image_bytes else None
    )
    payload["facts"] = [
        {
            **asdict(fact),
            "group": fact.group.value,
            "source": fact.source.value,
            "verification_status": fact.verification_status.value,
            "confirmed_at": fact.confirmed_at.isoformat() if fact.confirmed_at else None,
        }
        for fact in draft.facts
    ]
    if draft.bilingual_draft:
        payload["bilingual_draft"] = {
            **asdict(draft.bilingual_draft),
            "source": draft.bilingual_draft.source.value,
            "verification_status": draft.bilingual_draft.verification_status.value,
        }
    payload["conflicts"] = [asdict(conflict) for conflict in draft.conflicts]
    return payload


def _deserialize(payload: dict[str, object]) -> ArtisanProductDraft:
    raw_facts = cast(list[dict[str, Any]], payload["facts"])
    facts = tuple(
        ProvenancedFact(
            field_name=str(item["field_name"]),
            value=(
                tuple(item["value"])
                if item["field_name"]
                in {"customization", "symbolism", "suggested_gifting_contexts"}
                and isinstance(item["value"], list)
                else item["value"]
            ),
            group=FactGroup(str(item["group"])),
            source=FactSource(str(item["source"])),
            verification_status=VerificationStatus(str(item["verification_status"])),
            source_note=(str(item["source_note"]) if item.get("source_note") else None),
            confirmed_at=(
                datetime.fromisoformat(str(item["confirmed_at"]))
                if item.get("confirmed_at")
                else None
            ),
        )
        for item in raw_facts
    )
    bilingual_payload = payload.get("bilingual_draft")
    bilingual = None
    if isinstance(bilingual_payload, dict):
        bilingual = BilingualProductDraft(
            **{
                key: value
                for key, value in bilingual_payload.items()
                if key not in {"source", "verification_status"}
            },
            source=FactSource(str(bilingual_payload["source"])),
            verification_status=VerificationStatus(str(bilingual_payload["verification_status"])),
        )
    return ArtisanProductDraft(
        draft_id=str(payload["draft_id"]),
        session_id=str(payload["session_id"]),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        facts=facts,
        publication_status=PublicationStatus(str(payload["publication_status"])),
        image_name=(str(payload["image_name"]) if payload.get("image_name") else None),
        image_bytes=(
            base64.b64decode(str(payload["image_bytes"])) if payload.get("image_bytes") else None
        ),
        bilingual_draft=bilingual,
        conflicts=tuple(
            FactConflict(**item)
            for item in cast(list[dict[str, Any]], payload.get("conflicts", []))
        ),
        submitted_at=(
            datetime.fromisoformat(str(payload["submitted_at"]))
            if payload.get("submitted_at")
            else None
        ),
        reviewed_at=(
            datetime.fromisoformat(str(payload["reviewed_at"]))
            if payload.get("reviewed_at")
            else None
        ),
    )
