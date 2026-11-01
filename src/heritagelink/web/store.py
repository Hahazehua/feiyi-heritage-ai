"""Session-owned inquiry persistence and atomic daily request budgets."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class QuotaExceeded(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class SQLiteStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS inquiries (
                  id TEXT PRIMARY KEY, owner TEXT, fingerprint TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS quotas (id TEXT PRIMARY KEY, used INTEGER);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def consume(self, owner: str, action: str, session_limit: int, global_limit: int) -> None:
        day = datetime.now(UTC).date().isoformat()
        keys = [
            (f"{day}:{action}:{owner}", session_limit),
            (f"{day}:{action}:global", global_limit),
        ]
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for key, limit in keys:
                row = db.execute("SELECT used FROM quotas WHERE id=?", (key,)).fetchone()
                if row and row[0] >= limit:
                    raise QuotaExceeded()
            for key, _ in keys:
                db.execute(
                    "INSERT INTO quotas VALUES (?,1) ON CONFLICT(id) DO UPDATE SET used=used+1",
                    (key,),
                )

    def save(self, owner: str, key: str, payload: dict) -> dict:
        record_id = digest(owner + ":" + key)
        fingerprint = digest(_canonical(payload))
        record = {**payload, "id": record_id, "created_at": datetime.now(UTC).isoformat()}
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT fingerprint,payload FROM inquiries WHERE id=?", (record_id,)
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise IdempotencyConflict()
                return json.loads(existing[1])
            db.execute(
                "INSERT INTO inquiries VALUES (?,?,?,?)",
                (record_id, owner, fingerprint, _canonical(record)),
            )
        return record

    def list(self, owner: str) -> list[dict]:
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT payload FROM inquiries WHERE owner=? ORDER BY rowid DESC LIMIT 50", (owner,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]


class FirestoreStore:
    def __init__(self, project: str, database: str = "(default)"):
        from google.cloud import firestore

        self.client = firestore.Client(project=project, database=database)
        self.firestore = firestore

    def consume(self, owner: str, action: str, session_limit: int, global_limit: int) -> None:
        now = datetime.now(UTC)
        day = now.date().isoformat()
        keys = [
            (f"{day}:{action}:{owner}", session_limit),
            (f"{day}:{action}:global", global_limit),
        ]
        refs = [(self.client.collection("web_quotas").document(digest(k)), n) for k, n in keys]

        @self.firestore.transactional
        def update(transaction):
            current = [(ref, limit, ref.get(transaction=transaction)) for ref, limit in refs]
            for _, limit, snapshot in current:
                if snapshot.exists and snapshot.to_dict().get("used", 0) >= limit:
                    raise QuotaExceeded()
            for ref, _, snapshot in current:
                used = snapshot.to_dict().get("used", 0) if snapshot.exists else 0
                transaction.set(ref, {"used": used + 1, "expires_at": now + timedelta(days=2)})

        update(self.client.transaction())

    def save(self, owner: str, key: str, payload: dict) -> dict:
        record_id = digest(owner + ":" + key)
        fingerprint = digest(_canonical(payload))
        ref = (
            self.client.collection("web_sessions")
            .document(owner)
            .collection("inquiries")
            .document(record_id)
        )
        record = {**payload, "id": record_id, "created_at": datetime.now(UTC).isoformat()}

        @self.firestore.transactional
        def create(transaction):
            snapshot = ref.get(transaction=transaction)
            if snapshot.exists:
                existing = snapshot.to_dict()
                if existing["fingerprint"] != fingerprint:
                    raise IdempotencyConflict()
                return existing["payload"]
            transaction.set(ref, {"fingerprint": fingerprint, "payload": record})
            return record

        return create(self.client.transaction())

    def list(self, owner: str) -> list[dict[str, Any]]:
        collection = self.client.collection("web_sessions").document(owner).collection("inquiries")
        docs = collection.order_by("payload.created_at", direction="DESCENDING").limit(50).stream()
        return [doc.to_dict()["payload"] for doc in docs]
