from __future__ import annotations

import importlib
from pathlib import Path

import yaml

from heritagelink.agent_registry import SKILL_REGISTRY

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "docs" / "wave3" / "agent_manifest.yaml"


def _load() -> dict[str, object]:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def _import_entrypoint(value: str):
    module_name, attribute = value.split(":", maxsplit=1)
    return getattr(importlib.import_module(module_name), attribute)


def test_manifest_is_valid_and_entrypoints_are_importable() -> None:
    manifest = _load()

    assert manifest["agent_id"] == "heritagelink_gift_advisor"
    assert callable(_import_entrypoint(str(manifest["entrypoint"])))
    assert callable(_import_entrypoint(str(manifest["analysis_entrypoint"])))


def test_manifest_has_seven_unique_ordered_skills_and_real_fallbacks() -> None:
    manifest = _load()
    skills = manifest["skills"]
    ids = [item["id"] for item in skills]
    registry = list(SKILL_REGISTRY)

    assert len(ids) == len(set(ids)) == 7
    assert [item["order"] for item in skills] == list(range(1, 8))
    assert ids == [item.skill_id for item in registry]
    assert [item["fallback"] for item in skills] == [item.fallback for item in registry]
    assert skills[-1]["execution"] == "offline_on_demand"


def test_manifest_contains_no_credentials_or_false_runtime_claims() -> None:
    text = MANIFEST.read_text(encoding="utf-8").lower()
    runtime = _load()["runtime"]

    assert not {"api_key", "password", "database_url"} & set(text.split())
    assert runtime["trace_contains_raw_chat"] is False
    assert runtime["trace_contains_pii"] is False
    assert runtime["automatic_weight_updates"] is False
