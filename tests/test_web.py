"""Public API contract, grounding, ownership and budget regression tests."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from heritagelink.web.app import create_app
from heritagelink.web.schemas import Brief
from heritagelink.web.service import HeritageService, validate_answer
from heritagelink.web.store import IdempotencyConflict, QuotaExceeded, SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-Requested-With": "HAHA-Studio"}


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_BACKEND", "sqlite")
    monkeypatch.setenv("VECTOR_SQLITE_PATH", str(tmp_path / "vectors.sqlite3"))
    monkeypatch.setenv("LLM_ENABLED", "false")
    return HeritageService(ROOT)


@pytest.fixture
def client(service, tmp_path):
    with TestClient(create_app(service, SQLiteStore(tmp_path / "inquiries.db"))) as c:
        c.get("/api/session")
        yield c


def test_citation_validation_rejects_fabricated_sources_and_quotes():
    sources = [{"id": "one", "passage": "This is a documented porcelain vessel."}]
    claim = {"text": "A porcelain vessel.", "source_id": "one", "quote": sources[0]["passage"]}
    assert len(validate_answer(json.dumps({"claims": [claim]}), sources)) == 1
    for change in [
        {"source_id": "invented"},
        {"quote": "A completely invented quote"},
        {"text": "Visit https://evil.example"},
    ]:
        with pytest.raises(ValueError):
            validate_answer(json.dumps({"claims": [{**claim, **change}]}), sources)


def test_no_sources_never_calls_model(service):
    service.client = object()  # Would fail if a provider was called.
    result = service.advise(Brief(query="zxqvnonexistent"))
    assert result["status"] == "no_sources"
    assert result["trace"]["input_tokens"] == 0


def test_provider_failure_preserves_sources(service):
    service.client = object()
    result = service.advise(Brief(query="carved lacquer"))
    assert result["status"] == "generation_unavailable"
    assert result["sources"]
    assert not result["claims"]


def test_valid_model_response(service):
    source = service.advise(Brief(query="carved lacquer"))["sources"][0]
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=60),
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "claims": [
                                {
                                    "text": "This reference documents carved lacquer.",
                                    "source_id": source["id"],
                                    "quote": source["passage"],
                                }
                            ],
                        }
                    )
                ),
            )
        ],
    )
    service.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response))
    )
    result = service.advise(Brief(query="carved lacquer"))
    assert result["status"] == "grounded_generation"
    assert result["trace"]["output_tokens"] == 60


def test_hard_constraints(service):
    assert service.shortlist(Brief(query="porcelain", budget_cny=1)) == []
    assert service.shortlist(Brief(query="porcelain", lead_days=1)) == []
    products = service.shortlist(Brief(query="porcelain", budget_cny=1200, quantity=10))
    assert products
    assert all(p["min_fen"] <= 120000 for p in products)
    eligible = {p.product_id for p in service.products}
    assert all(p["id"] in eligible for p in products)


def test_session_ownership_consent_and_idempotency(client, service):
    brief = Brief(query="porcelain tea", quantity=10).model_dump()
    product = service.shortlist(Brief(**brief))[0]
    body = {
        "brief": brief,
        "product_id": product["id"],
        "notes": "Blue packaging",
        "consent": True,
        "idempotency_key": "same-request-key-001",
    }
    assert (
        client.post("/api/inquiries", json={**body, "consent": False}, headers=HEADERS).status_code
        == 422
    )
    first = client.post("/api/inquiries", json=body, headers=HEADERS)
    assert first.status_code == 200
    assert client.post("/api/inquiries", json=body, headers=HEADERS).json() == first.json()
    assert (
        client.post(
            "/api/inquiries", json={**body, "notes": "Changed"}, headers=HEADERS
        ).status_code
        == 409
    )
    assert len(client.get("/api/inquiries").json()["items"]) == 1
    client.cookies.clear()
    assert client.get("/api/inquiries").status_code == 401
    client.get("/api/session")
    assert client.get("/api/inquiries").json()["items"] == []


def test_origin_and_schema_guards(client):
    brief = Brief(query="porcelain").model_dump()
    assert client.post("/api/advice", json=brief).status_code == 403
    assert (
        client.post(
            "/api/advice", json=brief, headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/advice", json={**brief, "budget_cny": -1}, headers=HEADERS).status_code
        == 422
    )
    assert client.post("/api/advice", content="x" * 16001, headers=HEADERS).status_code == 413
    assert client.get("/api/inquiries").headers["cache-control"] == "no-store"


def test_persistent_atomic_quotas_and_idempotency(tmp_path):
    path = tmp_path / "store.db"
    store = SQLiteStore(path)
    store.consume("a", "advice", 1, 2)
    with pytest.raises(QuotaExceeded):
        SQLiteStore(path).consume("a", "advice", 1, 2)
    store.consume("b", "advice", 1, 2)
    with pytest.raises(QuotaExceeded):
        store.consume("c", "advice", 1, 2)
    store.save("a", "key", {"notes": "hello"})
    with pytest.raises(IdempotencyConflict):
        store.save("a", "key", {"notes": "different"})
    assert len(SQLiteStore(path).list("a")) == 1
    assert SQLiteStore(path).list("b") == []


def test_storage_failure_is_not_reported_as_saved(client, service):
    class BrokenStore:
        def list(self, owner):
            raise RuntimeError("private database details")

    client.app.state.store = BrokenStore()
    result = client.get("/api/inquiries")
    assert result.status_code == 503
    assert "private" not in result.text
