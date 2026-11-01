from __future__ import annotations

import copy
import json
import math
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from heritagelink.catalog import HeritageReferenceItem, load_reference_catalog
from heritagelink.vector_search import (
    EMBEDDING_DIMENSION,
    CatalogSearch,
    CatalogSearchError,
    VectorSearchSettings,
    create_catalog_search,
    embed_text,
)


@pytest.fixture
def items() -> tuple[HeritageReferenceItem, ...]:
    common = dict(
        source_object_id="source-1",
        period_text="",
        region_text="",
        material_text="",
        dimensions_text="",
        image_path="assets/catalog/products/example.jpg",
        source_url="https://example.org/museum/1",
        image_source_url="https://example.org/images/1.jpg",
        source_name="Public museum",
        source_object_number="1",
        image_license="CC0",
        commercial_status="museum_reference_not_for_sale",
        verification_status="reference_only",
    )
    return (
        HeritageReferenceItem(
            catalog_product_id="ceramic-a",
            demo_product_id="prod_a",
            product_name_zh="青花瓷",
            product_name_en="porcelain",
            craft_category_zh="陶瓷",
            craft_category_en="porcelain",
            introduction_zh="青花瓷花瓶",
            introduction_en="porcelain vase",
            **common,
        ),
        HeritageReferenceItem(
            catalog_product_id="silk-b",
            demo_product_id="prod_b",
            product_name_zh="丝绸刺绣",
            product_name_en="embroidery",
            craft_category_zh="刺绣",
            craft_category_en="embroidery",
            introduction_zh="丝绸刺绣花鸟",
            introduction_en="silk embroidery birds",
            **common,
        ),
    )


def test_embedding_is_unicode_normalized_deterministic_and_unit_length() -> None:
    assert embed_text("ＰＯＲＣＥＬＡＩＮ 青花瓷") == embed_text("porcelain 青花瓷")
    vector = embed_text("青花瓷 porcelain")
    assert len(vector) == EMBEDDING_DIMENSION == 256
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1)
    assert embed_text(" ") == embed_text("！！！") == (0.0,) * 256
    assert any(embed_text("瓷"))


@pytest.mark.parametrize("query, expected", [("青花瓷", "ceramic-a"), ("silk", "silk-b")])
def test_chinese_and_english_retrieval(items, tmp_path, query, expected) -> None:
    service = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    assert service.search(query, limit=1)[0].catalog_product_id == expected


def test_classification_applies_before_limit_and_equal_scores_use_id(items, tmp_path) -> None:
    twins = (
        replace(items[0], catalog_product_id="z-id"),
        replace(items[0], catalog_product_id="a-id"),
        replace(items[0], catalog_product_id="b-id", craft_category_zh="另一分类"),
    )
    service = create_catalog_search(twins, VectorSearchSettings(), tmp_path)
    assert [hit.catalog_product_id for hit in service.search("porcelain", limit=2)] == [
        "a-id",
        "z-id",
    ]
    assert service.search("porcelain", category="另一分类", limit=1)[0].catalog_product_id == "b-id"
    assert service.search("porcelain", category="不存在") == ()


def test_idempotent_import_persists_source_and_query_is_not_saved(items, tmp_path) -> None:
    settings = VectorSearchSettings()
    first = create_catalog_search(items, settings, tmp_path)
    first.index()
    assert first.verify() == 2
    second = CatalogSearch(items, settings, tmp_path)
    unique_query = "never persist this private query 9416"
    second.search(unique_query)
    with sqlite3.connect(tmp_path / settings.sqlite_path) as connection:
        rows = connection.execute("SELECT document_json FROM catalogue_vectors").fetchall()
    assert len(rows) == 2
    records = [json.loads(row[0]) for row in rows]
    assert records[0]["metadata"]["source_url"] == items[0].source_url
    assert records[0]["metadata"]["verification_status"] == "reference_only"
    assert unique_query not in str(records)


def test_corpus_fingerprint_is_order_independent_and_versions_coexist(items, tmp_path) -> None:
    settings = VectorSearchSettings()
    old = create_catalog_search(items, settings, tmp_path)
    reordered = CatalogSearch(tuple(reversed(items)), settings, tmp_path)
    assert old.corpus_id == reordered.corpus_id
    changed = (replace(items[0], introduction_zh="更新后的青花瓷资料"), items[1])
    current = CatalogSearch(changed, settings, tmp_path)
    assert current.corpus_id != old.corpus_id
    with pytest.raises(CatalogSearchError, match="incomplete"):
        current.search("porcelain")
    current.index()
    assert old.verify() == current.verify() == 2
    with sqlite3.connect(tmp_path / settings.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM catalogue_vectors").fetchone()[0] == 4


def test_missing_index_read_only_verify_never_creates_database(items, tmp_path) -> None:
    settings = VectorSearchSettings()
    service = CatalogSearch(items, settings, tmp_path)
    with pytest.raises(CatalogSearchError):
        service.verify()
    assert not (tmp_path / settings.sqlite_path).exists()


@pytest.mark.parametrize("corruption", ["source", "embedding", "dimension", "missing"])
def test_corrupt_or_incomplete_index_fails_instead_of_returning_wrong_item(
    items, tmp_path, corruption
) -> None:
    settings = VectorSearchSettings()
    service = create_catalog_search(items, settings, tmp_path)
    with sqlite3.connect(tmp_path / settings.sqlite_path) as connection:
        document = json.loads(
            connection.execute(
                "SELECT document_json FROM catalogue_vectors WHERE catalog_product_id='ceramic-a'"
            ).fetchone()[0]
        )
        if corruption == "source":
            document["metadata"]["source_url"] = "https://example.org/wrong"
        elif corruption == "embedding":
            document["embedding"][0] = 2
        elif corruption == "dimension":
            document["embedding"].pop()
        else:
            connection.execute("DELETE FROM catalogue_vectors WHERE catalog_product_id='silk-b'")
        connection.execute(
            "UPDATE catalogue_vectors SET document_json=? WHERE catalog_product_id='ceramic-a'",
            (json.dumps(document),),
        )
    with pytest.raises(CatalogSearchError):
        service.search("porcelain")


@pytest.mark.parametrize("limit", [0, 1001, -1, True, 1.5])
def test_invalid_query_limits_are_rejected(items, tmp_path, limit) -> None:
    service = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    with pytest.raises(ValueError):
        service.search("porcelain", limit=limit)


def test_blank_queries_do_not_read_store(items, tmp_path) -> None:
    service = CatalogSearch(items, VectorSearchSettings(), tmp_path)
    assert service.search("  ") == service.search("?!") == ()
    with pytest.raises(ValueError):
        service.search("a" * 2001)


def test_configuration_and_public_catalogue_guards(items, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VECTOR_BACKEND", "sqlite")
    monkeypatch.setenv("VECTOR_COLLECTION", "heritage_catalog_vectors")
    assert VectorSearchSettings.from_env().backend == "sqlite"
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        VectorSearchSettings(backend="firestore")
    with pytest.raises(ValueError, match="collection"):
        VectorSearchSettings(collection="path/to/collection")
    with pytest.raises(ValueError, match="Duplicate"):
        CatalogSearch((items[0], items[0]), VectorSearchSettings(), tmp_path)
    with pytest.raises(ValueError, match="public"):
        CatalogSearch(
            (replace(items[0], commercial_status="private_customer_record"),),
            VectorSearchSettings(),
            tmp_path,
        )
    with pytest.raises(ValueError, match="1 to 1000"):
        CatalogSearch((), VectorSearchSettings(), tmp_path)


def test_real_public_catalogue_indexes_and_verifies_all_fifty_records(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    items = load_reference_catalog(root / "data/catalog/heritage_products.csv", project_root=root)
    service = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    assert service.verify() == 50
    assert service.search("青瓷")
    assert service.search("embroidery")


@pytest.mark.parametrize("query, required", [("瓷", "瓷"), ("瓷器", "瓷"), ("丝", "丝")])
def test_real_catalogue_short_chinese_queries_retrieve_related_items(tmp_path, query, required):
    root = Path(__file__).resolve().parents[1]
    items = load_reference_catalog(root / "data/catalog/heritage_products.csv", project_root=root)
    service = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    by_id = {item.catalog_product_id: item for item in items}
    hits = service.search(query, limit=3)
    assert hits
    for hit in hits:
        item = by_id[hit.catalog_product_id]
        assert required in item.product_name_zh + item.craft_category_zh + item.introduction_zh


def test_hash_collisions_alone_cannot_produce_search_hits(items, tmp_path) -> None:
    service = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    assert service.search("unrelatednewword98357") == ()


class _Snapshot:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.document)


class _FakeQuery:
    def __init__(self, client, *, filters=(), count=1001, nearest=None):
        self.client, self.filters, self.count, self.nearest = client, filters, count, nearest

    def document(self, name):
        return name

    def where(self, *, filter):
        return _FakeQuery(self.client, filters=(*self.filters, filter), count=self.count)

    def limit(self, count):
        return _FakeQuery(self.client, filters=self.filters, count=count)

    def find_nearest(self, **kwargs):
        self.client.nearest_queries.append((self.filters, kwargs))
        return _FakeQuery(self.client, filters=self.filters, count=kwargs["limit"], nearest=kwargs)

    def stream(self, *, timeout):
        records = [
            copy.deepcopy(document)
            for document in self.client.records.values()
            if all(document.get(f.field_path) == f.value for f in self.filters)
        ]
        if self.nearest:
            for document in records:
                document["vector_distance"] = 1 - sum(
                    a * b
                    for a, b in zip(
                        document["embedding"], self.nearest["query_vector"], strict=True
                    )
                )
            records.sort(key=lambda doc: doc["vector_distance"])
        return iter(_Snapshot(document) for document in records[: self.count])


class _FakeBatch:
    def __init__(self, client):
        self.client, self.pending = client, {}

    def set(self, reference, payload):
        self.pending[reference] = copy.deepcopy(payload)

    def commit(self, *, timeout):
        self.client.commits += 1
        self.client.records.update(self.pending)


class _FakeFirestore:
    def __init__(self):
        self.records, self.nearest_queries, self.commits = {}, [], 0

    def collection(self, name):
        return _FakeQuery(self)

    def batch(self):
        return _FakeBatch(self)


@pytest.fixture
def cloud(items, tmp_path):
    # Cloud tests use real SDK Vector and FieldFilter types, with no network or credentials.
    pytest.importorskip("google.cloud.firestore_v1")
    client = _FakeFirestore()
    settings = VectorSearchSettings(backend="firestore", project_id="demo-test")
    return CatalogSearch(items, settings, tmp_path, firestore_client=client), client


def test_firestore_native_query_pre_filters_and_runtime_never_writes(cloud) -> None:
    service, client = cloud
    assert client.commits == 0
    service.index()
    service.index()
    assert len(client.records) == 2
    commits = client.commits
    assert service.verify() == 2
    assert service.search("silk", category="刺绣", limit=1)[0].catalog_product_id == "silk-b"
    assert client.commits == commits
    filters, kwargs = client.nearest_queries[-1]
    assert [(f.field_path, f.value) for f in filters] == [
        ("corpus_id", service.corpus_id),
        ("category", "刺绣"),
    ]
    assert kwargs["vector_field"] == "embedding"
    assert kwargs["limit"] == 1
    assert kwargs["distance_result_field"] == "vector_distance"


def test_firestore_real_vector_type_is_accepted_and_matches_sqlite(cloud, items, tmp_path) -> None:
    from google.cloud.firestore_v1.vector import Vector

    service, client = cloud
    service.index()
    assert all(isinstance(doc["embedding"], Vector) for doc in client.records.values())
    local = create_catalog_search(items, VectorSearchSettings(), tmp_path)
    assert service.search("porcelain") == local.search("porcelain")


def test_firestore_missing_or_stale_index_raises_instead_of_silent_empty_result(cloud) -> None:
    service, client = cloud
    with pytest.raises(CatalogSearchError, match="incomplete"):
        service.search("porcelain")
    assert client.commits == 0
    service.index()
    next(iter(client.records.values()))["item_fingerprint"] = "old"
    with pytest.raises(CatalogSearchError, match="incompatible"):
        service.search("porcelain")


def test_firestore_failures_propagate_as_safe_search_error(cloud, monkeypatch) -> None:
    service, client = cloud

    def unavailable(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(client, "collection", unavailable)
    with pytest.raises(CatalogSearchError, match="unavailable"):
        service.search("porcelain")
    assert client.commits == 0
