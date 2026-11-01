"""Verify safe upload scope and Firestore index provisioning without cloud access."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_helper(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy" / "gcp" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage = load_helper("stage_source")
indexes = load_helper("ensure_indexes")


def test_upload_allowlist_excludes_credentials_databases_and_logs(tmp_path: Path) -> None:
    source = tmp_path / "project"
    for filename in stage.FILES:
        path = source / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public demo file", encoding="utf-8")
    allowed = ["src/heritagelink/module.py", "assets/catalog/products/public.jpg"]
    excluded = [
        ".env",
        ".streamlit/secrets.toml",
        ".git/config",
        ".local/analytics.db",
        "deploy/gcp/service-account.json",
        "deploy/gcp/private.py",
        "src/heritagelink/.env",
        "src/heritagelink/__pycache__/cached.py",
        "src/another-package/module.py",
        "assets/catalog/products/credentials.json",
        "assets/private.jpg",
        "data/demo/analytics.csv",
        "app.log",
    ]
    for filename in allowed + excluded:
        path = source / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    destination = tmp_path / "staged"
    stage.stage_source(destination, root=source)
    for filename in (*stage.FILES, *allowed):
        assert (destination / filename).is_file()
    for filename in excluded:
        assert not (destination / filename).exists()
    with pytest.raises(ValueError, match="must be empty"):
        stage.stage_source(destination, root=source)


def index_fixture(category: bool, state: str = "READY") -> dict:
    fields = [{"fieldPath": "corpus_id", "order": "ASCENDING"}]
    if category:
        fields.append({"fieldPath": "category", "order": "ASCENDING"})
    fields.extend(
        [
            {"fieldPath": "embedding", "vectorConfig": {"dimension": 256, "flat": {}}},
            {"fieldPath": "__name__", "order": "ASCENDING"},
        ]
    )
    return {
        "name": (
            "projects/demo/databases/(default)/collectionGroups/heritage_catalog_vectors/indexes/abc"
        ),
        "queryScope": "COLLECTION",
        "fields": fields,
        "state": state,
    }


def test_index_matching_rejects_wrong_dimension_collection_and_filter() -> None:
    index = index_fixture(False)
    assert indexes.matches(index, False, "heritage_catalog_vectors")
    assert not indexes.matches(index, True, "heritage_catalog_vectors")
    assert not indexes.matches(index, False, "unrelated_collection")
    index["fields"][1]["vectorConfig"]["dimension"] = 384
    assert not indexes.matches(index, False, "heritage_catalog_vectors")


def test_ready_indexes_are_reused_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert "list" in command
        return subprocess.CompletedProcess(
            command, 0, json.dumps([index_fixture(False), index_fixture(True)])
        )

    monkeypatch.setattr(indexes.subprocess, "run", run)
    indexes.ensure_indexes("demo-project", "heritage_catalog_vectors", timeout=1)
    assert len(calls) == 2


def test_missing_indexes_created_then_wait_for_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    listings = iter(
        [
            [],
            [index_fixture(False, "CREATING"), index_fixture(True, "CREATING")],
            [index_fixture(False), index_fixture(True)],
        ]
    )

    def run(command, **kwargs):
        calls.append(command)
        payload = next(listings) if "list" in command else {}
        return subprocess.CompletedProcess(command, 0, json.dumps(payload))

    monkeypatch.setattr(indexes.subprocess, "run", run)
    monkeypatch.setattr(indexes.time, "sleep", lambda _: None)
    indexes.ensure_indexes("demo-project", "heritage_catalog_vectors", timeout=1)
    creates = [command for command in calls if "create" in command]
    assert len(creates) == 2
    for command in creates:
        config = json.loads(
            next(arg.split("=", 1)[1] for arg in command if arg.startswith("--field-config="))
        )
        assert config[-1]["vector-config"] == {"dimension": 256, "flat": {}}
    assert len([command for command in calls if "list" in command]) == 3


def test_index_listing_failure_does_not_create_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(command, **kwargs):
        assert "list" in command
        return subprocess.CompletedProcess(command, 1, "", "Permission denied")

    monkeypatch.setattr(indexes.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        indexes.ensure_indexes("demo-project", "heritage_catalog_vectors", timeout=1)
