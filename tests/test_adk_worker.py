"""Exercise the real domain rules and ADK graph behind the private API."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("google.adk")
from fastapi.testclient import TestClient  # noqa: E402

from heritagelink.adk_worker import create_worker  # noqa: E402


def provider(content):
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=40, completion_tokens=20),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))],
    )
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response))
    )


def body(app):
    return {"product_id": next(iter(app.state.contexts)), "goal": "Introduce a demo gift concept"}


def test_actual_graph_revises_risky_model_output():
    model = provider(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "test",
                        "channel": "LinkedIn",
                        "asset_type": "post",
                        "content": "Ships worldwide. Explore this demo concept.",
                        "claims": [],
                    }
                ]
            }
        )
    )
    app = create_worker(provider=model)
    with TestClient(app) as client:
        result = client.post("/campaign", json=body(app)).json()
    assert result["trace"]["generation"] == "deepseek"
    assert result["trace"]["revision_count"] == 1
    assert [e["stage"] for e in result["events"]] == ["draft", "review", "revision", "review"]
    assert "Ships worldwide" not in result["assets"][0]["content"]
    assert result["requires_human_review"] and not result["published"]


def test_bad_model_output_is_labelled_fallback():
    app = create_worker(provider=provider("not JSON"))
    with TestClient(app) as client:
        result = client.post("/campaign", json=body(app)).json()
    assert result["trace"]["generation"] == "deterministic_fallback"
    assert result["trace"]["output_tokens"] == 20
    assert result["requires_human_review"]


def test_worker_rejects_browser_facts_and_unknown_identity():
    app = create_worker(provider=provider("not used"))
    with TestClient(app) as client:
        assert client.post("/campaign", json={**body(app), "verified_facts": []}).status_code == 422
        assert (
            client.post("/campaign", json={**body(app), "product_id": "missing"}).status_code == 422
        )


def test_catalogue_demo_commercial_facts_stay_unverified():
    app = create_worker(provider=provider("not used"))
    with TestClient(app):
        for context in app.state.contexts.values():
            assert "price_min_fen" not in context.verified_by_name
            assert "international_shipping" not in context.verified_by_name
