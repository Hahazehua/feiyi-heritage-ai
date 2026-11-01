"""Versioned lexical vector retrieval over the public reference catalogue.

The free embedding hashes Chinese bigrams, lower-weight characters and English words.
It is lexical similarity, not a learned semantic model or cross-language translation.
SQLite persists the vectors locally; Firestore performs native nearest-neighbor queries.
Only the explicit indexing command writes to Firestore. Search text is never stored.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from heritagelink.catalog import HeritageReferenceItem

EMBEDDING_DIMENSION = 256
EMBEDDING_VERSION = "lexical-zh-bigram-char-en-word-sha256-v2-256"
SCHEMA_VERSION = 1
MAX_CATALOG_SIZE = 1000
_TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ebef]+|[a-z0-9]+(?:'[a-z]+)?")


class CatalogSearchError(RuntimeError):
    """The configured vector index is unavailable, incomplete or incompatible."""


@dataclass(frozen=True, slots=True)
class VectorSearchSettings:
    backend: str = "sqlite"
    sqlite_path: str = ".local/catalog-vectors.sqlite3"
    project_id: str = ""
    database: str = "(default)"
    collection: str = "heritage_catalog_vectors"

    def __post_init__(self) -> None:
        if self.backend not in {"sqlite", "firestore"}:
            raise ValueError("VECTOR_BACKEND must be sqlite or firestore")
        if not self.sqlite_path.strip() or not self.database.strip():
            raise ValueError("Vector database path and database ID cannot be empty")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,99}", self.collection):
            raise ValueError("VECTOR_COLLECTION must be a simple collection name")
        if self.backend == "firestore" and not self.project_id.strip():
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Firestore vector search")

    @classmethod
    def from_env(cls) -> VectorSearchSettings:
        """Read non-secret settings; Firestore authentication uses ADC only."""
        return cls(
            backend=os.getenv("VECTOR_BACKEND", "sqlite").strip().lower(),
            sqlite_path=os.getenv("VECTOR_SQLITE_PATH", ".local/catalog-vectors.sqlite3"),
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "").strip(),
            database=os.getenv("FIRESTORE_DATABASE", "(default)").strip(),
            collection=os.getenv("VECTOR_COLLECTION", "heritage_catalog_vectors").strip(),
        )


@dataclass(frozen=True, slots=True)
class SearchHit:
    catalog_product_id: str
    score: float


def _features(text: str) -> dict[str, float]:
    if not isinstance(text, str):
        raise TypeError("Search text must be a string")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    features: list[str] = []
    for token in _TOKEN_RE.findall(normalized):
        if token[0].isascii():
            features.append("word:" + token)
        else:
            # Single-character searches such as 瓷 must share features with 青花瓷.
            features.extend("char:" + character for character in token)
            features.extend("zh:" + token[index : index + 2] for index in range(len(token) - 1))
    return {
        feature: (0.25 if feature.startswith("char:") else 1.0) * (1 + math.log(count))
        for feature, count in sorted(Counter(features).items())
    }


def embed_text(text: str) -> tuple[float, ...]:
    """Return a normalized, reproducible 256-dimensional lexical feature vector."""
    vector = [0.0] * EMBEDDING_DIMENSION
    for feature, weight in _features(text).items():
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1 if digest[4] & 1 else -1
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm else tuple(vector)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _item_text(item: HeritageReferenceItem) -> str:
    return "\n".join(
        (
            item.product_name_zh,
            item.product_name_en,
            item.craft_category_zh,
            item.craft_category_en,
            item.period_text,
            item.region_text,
            item.material_text,
            item.introduction_zh,
            item.introduction_en,
        )
    )


def _documents(items: tuple[HeritageReferenceItem, ...]) -> tuple[str, dict[str, dict[str, Any]]]:
    if not items or len(items) > MAX_CATALOG_SIZE:
        raise ValueError("Vector catalogue must contain 1 to 1000 public reference items")
    ordered = sorted(items, key=lambda item: item.catalog_product_id)
    if len({item.catalog_product_id for item in ordered}) != len(ordered):
        raise ValueError("Duplicate catalogue product IDs")
    corpus_id = _fingerprint(
        {
            "schema_version": SCHEMA_VERSION,
            "embedding_version": EMBEDDING_VERSION,
            "items": [asdict(item) for item in ordered],
        }
    )
    documents = {}
    for item in ordered:
        if item.commercial_status not in {
            "museum_reference_not_for_sale",
            "catalog_reference_not_for_sale",
        }:
            raise ValueError("Only public reference catalogue items may enter this index")
        metadata = asdict(item)
        embedding = embed_text(_item_text(item))
        if not any(embedding):
            raise ValueError("Catalogue item has no searchable text")
        documents[item.catalog_product_id] = {
            "corpus_id": corpus_id,
            "schema_version": SCHEMA_VERSION,
            "embedding_version": EMBEDDING_VERSION,
            "catalog_product_id": item.catalog_product_id,
            "item_fingerprint": _fingerprint(metadata),
            "category": item.craft_category_zh,
            "embedding": list(embedding),
            "metadata": metadata,
        }
    return corpus_id, documents


def _document_id(corpus_id: str, catalog_product_id: str) -> str:
    return f"{corpus_id}_{hashlib.sha256(catalog_product_id.encode('utf-8')).hexdigest()}"


class CatalogSearch:
    """Search a specific immutable catalogue version, rejecting stale cloud records."""

    def __init__(
        self,
        items: tuple[HeritageReferenceItem, ...],
        settings: VectorSearchSettings,
        project_root: Path,
        *,
        firestore_client: Any = None,
    ) -> None:
        self.settings = settings
        self.corpus_id, self._documents = _documents(items)
        self._features_by_id = {
            item.catalog_product_id: frozenset(_features(_item_text(item))) for item in items
        }
        self._path = project_root / settings.sqlite_path
        self._client = firestore_client
        if settings.backend == "firestore" and self._client is None:
            try:
                from google.cloud import firestore

                self._client = firestore.Client(
                    project=settings.project_id, database=settings.database
                )
            except Exception as exc:
                raise CatalogSearchError("Firestore client or ADC credentials unavailable") from exc

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            return sqlite3.connect(self._path.resolve().as_uri() + "?mode=ro", uri=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._path, timeout=15)

    def _validate_document(self, document: dict[str, Any]) -> str:
        item_id = document.get("catalog_product_id", "")
        expected = self._documents.get(item_id)
        if expected is None or any(
            document.get(key) != expected[key]
            for key in (
                "corpus_id",
                "schema_version",
                "embedding_version",
                "item_fingerprint",
                "category",
                "metadata",
            )
        ):
            raise CatalogSearchError("Vector index contains stale or incompatible records")
        vector = document.get("embedding")
        # Firestore Vector implements Sequence; SQLite deserializes to a list.
        if (
            not isinstance(vector, Sequence)
            or isinstance(vector, (str, bytes))
            or len(vector) != EMBEDDING_DIMENSION
        ):
            raise CatalogSearchError("Vector index has an incompatible embedding dimension")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
            raise CatalogSearchError("Vector index has non-finite embedding values")
        if any(
            abs(left - right) > 1e-12
            for left, right in zip(vector, expected["embedding"], strict=True)
        ):
            raise CatalogSearchError("Vector index embeddings do not match this catalogue version")
        return item_id

    def index(self) -> int:
        """Explicitly upsert this version without deleting other versions or collections."""
        try:
            if self.settings.backend == "sqlite":
                with self._connect() as connection:
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS catalogue_vectors ("
                        "corpus_id TEXT NOT NULL, catalog_product_id TEXT NOT NULL, "
                        "category TEXT NOT NULL, document_json TEXT NOT NULL, "
                        "PRIMARY KEY (corpus_id, catalog_product_id))"
                    )
                    connection.executemany(
                        "INSERT INTO catalogue_vectors VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(corpus_id, catalog_product_id) DO UPDATE SET "
                        "category=excluded.category, document_json=excluded.document_json",
                        [
                            (self.corpus_id, item_id, doc["category"], _json(doc))
                            for item_id, doc in self._documents.items()
                        ],
                    )
            else:
                from google.cloud.firestore_v1.vector import Vector

                collection = self._client.collection(self.settings.collection)
                records = tuple(self._documents.items())
                for start in range(0, len(records), 400):
                    batch = self._client.batch()
                    for item_id, document in records[start : start + 400]:
                        payload = dict(document, embedding=Vector(document["embedding"]))
                        reference = collection.document(_document_id(self.corpus_id, item_id))
                        batch.set(reference, payload)
                    batch.commit(timeout=30)
            return len(self._documents)
        except CatalogSearchError:
            raise
        except Exception as exc:
            raise CatalogSearchError("Catalogue vector indexing failed") from exc

    def _cloud_query(self, category: str | None = None) -> Any:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._client.collection(self.settings.collection).where(
            filter=FieldFilter("corpus_id", "==", self.corpus_id)
        )
        if category is not None:
            query = query.where(filter=FieldFilter("category", "==", category))
        return query

    def _local_documents(self, category: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT document_json FROM catalogue_vectors WHERE corpus_id = ?"
        params = [self.corpus_id]
        if category is not None:
            sql += " AND category = ?"
            params.append(category)
        with self._connect(read_only=True) as connection:
            return [json.loads(row[0]) for row in connection.execute(sql, params)]

    def verify(self) -> int:
        """Read-only integrity check, including both required Firestore vector indexes."""
        try:
            if self.settings.backend == "sqlite":
                documents = self._local_documents()
            else:
                snapshots = self._cloud_query().limit(MAX_CATALOG_SIZE + 1).stream(timeout=15)
                documents = [snapshot.to_dict() for snapshot in snapshots]
            found = [self._validate_document(document) for document in documents]
            if len(found) != len(set(found)) or set(found) != set(self._documents):
                raise CatalogSearchError("Vector index is incomplete; run the indexing command")
            first = next(iter(self._documents.values()))
            self.search(first["metadata"]["product_name_zh"], limit=1)
            self.search(first["metadata"]["product_name_zh"], category=first["category"], limit=1)
            return len(found)
        except CatalogSearchError:
            raise
        except Exception as exc:
            raise CatalogSearchError("Catalogue vector verification failed") from exc

    def search(
        self, query: str, *, category: str | None = None, limit: int = 12
    ) -> tuple[SearchHit, ...]:
        """Filter before ranking, then sort equal scores by stable catalogue ID.

        This small catalogue is capped at 1000 items, Firestore's nearest-query limit.
        All eligible candidates are requested so a top-k cutoff cannot split ties
        nondeterministically. The current 50-item catalogue reads at most 50 documents
        per search, plus Firestore vector-index read charges. Queries are never saved.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000")
        if len(query) > 2000:
            raise ValueError("Search query must be at most 2000 characters")
        vector = embed_text(query)
        query_features = _features(query)
        expected_ids = {
            item_id
            for item_id, document in self._documents.items()
            if category is None or document["category"] == category
        }
        if not any(vector) or not expected_ids:
            return ()
        try:
            if self.settings.backend == "sqlite":
                documents = self._local_documents(category)
            else:
                from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
                from google.cloud.firestore_v1.vector import Vector

                nearest = self._cloud_query(category).find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(vector),
                    distance_measure=DistanceMeasure.COSINE,
                    distance_result_field="vector_distance",
                    limit=len(expected_ids),
                )
                documents = [snapshot.to_dict() for snapshot in nearest.stream(timeout=15)]
            hits = []
            found = set()
            for document in documents:
                item_id = self._validate_document(document)
                if item_id not in expected_ids or item_id in found:
                    raise CatalogSearchError("Vector index has duplicate or unexpected records")
                found.add(item_id)
                # Hash collisions must not outweigh real lexical evidence. Require 20%
                # query-feature coverage; 瓷器 needs both characters when no exact bigram
                # exists, rather than matching any unrelated artefact mentioning 器.
                overlap = sum(
                    weight
                    for feature, weight in query_features.items()
                    if feature in self._features_by_id[item_id]
                )
                if overlap / sum(query_features.values()) < 0.2:
                    continue
                if self.settings.backend == "sqlite":
                    score = sum(a * b for a, b in zip(vector, document["embedding"], strict=True))
                else:
                    distance = document.get("vector_distance")
                    if not isinstance(distance, (int, float)) or not math.isfinite(distance):
                        raise CatalogSearchError("Firestore did not return a valid vector distance")
                    score = 1 - distance
                score = round(max(-1.0, min(1.0, score)), 10)
                if score > 0:
                    hits.append(SearchHit(item_id, score))
            if found != expected_ids:
                raise CatalogSearchError("Vector index is incomplete; run the indexing command")
            return tuple(sorted(hits, key=lambda hit: (-hit.score, hit.catalog_product_id))[:limit])
        except CatalogSearchError:
            raise
        except Exception as exc:
            raise CatalogSearchError("Catalogue vector search unavailable") from exc


def create_catalog_search(
    items: tuple[HeritageReferenceItem, ...],
    settings: VectorSearchSettings,
    project_root: Path,
) -> CatalogSearch:
    """Prepare local persistence; cloud runtime construction is strictly read-only."""
    service = CatalogSearch(items, settings, project_root)
    if settings.backend == "sqlite":
        service.index()
    return service
