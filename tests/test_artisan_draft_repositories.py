from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from heritagelink.artisan_studio import (
    confirm_facts,
    create_draft,
    enrich_draft,
    merge_artisan_values,
)
from heritagelink.heritage_passport_models import (
    FactSource,
    VerificationStatus,
)
from heritagelink.repositories.memory_artisan_draft_repository import (
    MemoryArtisanDraftRepository,
)
from heritagelink.repositories.sqlite_artisan_draft_repository import (
    SQLiteArtisanDraftRepository,
)

NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


def _representative_draft():  # type: ignore[no-untyped-def]
    draft = create_draft(
        "artisan-session-a",
        {
            "product_name_zh": "芜湖铁画迎客松",
            "craft_name": "芜湖铁画",
            "price_min_fen": 120_000,
            "international_shipping": False,
            "quantity_capacity": "暂不确定",
            "merchant_source_url": "https://example.org/merchant-source",
        },
        description="适合作为企业礼赠，也支持题字。",
        image_name="iron-painting.jpg",
        image_bytes=b"test-image-bytes",
        now=NOW,
    )
    enriched, _ = enrich_draft(draft, now=LATER)
    resolved = merge_artisan_values(
        enriched,
        {"price_min_fen": 80_000},
        resolutions={"price_min_fen": 120_000},
        now=LATER,
    )
    return confirm_facts(resolved, ("product_name_zh",), now=LATER)


def _assert_round_trip(original, restored) -> None:  # type: ignore[no-untyped-def]
    assert restored == original
    assert restored.image_name == original.image_name
    assert restored.image_bytes == original.image_bytes
    assert restored.bilingual_draft == original.bilingual_draft
    assert restored.conflicts == original.conflicts
    assert restored.facts_by_name["product_name_zh"].source is FactSource.ARTISAN_CONFIRMED
    assert (
        restored.facts_by_name["product_name_zh"].verification_status
        is VerificationStatus.CONFIRMED
    )
    unknown = restored.facts_by_name["quantity_capacity"]
    assert unknown.value is None
    assert unknown.source is FactSource.UNKNOWN
    assert unknown.verification_status is VerificationStatus.UNKNOWN


def test_memory_repository_round_trips_complete_draft_and_isolates_sessions() -> None:
    repository = MemoryArtisanDraftRepository()
    first = _representative_draft()
    second = create_draft(
        "artisan-session-b",
        {"product_name_zh": "另一件作品", "craft_name": "另一项工艺"},
        now=LATER,
    )

    repository.save(first)
    repository.save(second)

    restored = repository.get(first.draft_id)
    assert restored is not None
    _assert_round_trip(first, restored)
    assert repository.list_for_session("artisan-session-a") == (first,)
    assert repository.list_for_session("artisan-session-b") == (second,)
    assert repository.list_for_session("missing-session") == ()


def test_memory_repository_upserts_same_draft_without_duplicates() -> None:
    repository = MemoryArtisanDraftRepository()
    draft = _representative_draft()
    updated = merge_artisan_values(draft, {"materials": "铁质材料，具体构成待审核"}, now=LATER)

    repository.save(draft)
    repository.save(updated)

    assert repository.get(draft.draft_id) == updated
    assert repository.list_for_session(draft.session_id) == (updated,)


def test_sqlite_repository_round_trips_provenance_unknowns_image_and_conflicts(
    tmp_path: Path,
) -> None:
    repository = SQLiteArtisanDraftRepository(tmp_path / "artisan.sqlite3")
    draft = _representative_draft()

    repository.save(draft)

    restored = repository.get(draft.draft_id)
    assert restored is not None
    _assert_round_trip(draft, restored)
    assert repository.list_for_session(draft.session_id) == (restored,)


def test_sqlite_repository_is_idempotent_and_updates_existing_draft(tmp_path: Path) -> None:
    database = tmp_path / "artisan.sqlite3"
    repository = SQLiteArtisanDraftRepository(database)
    draft = _representative_draft()
    updated = merge_artisan_values(draft, {"materials": "铁质材料，具体构成待审核"}, now=LATER)

    repository.save(draft)
    repository.save(updated)

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM artisan_drafts").fetchone()[0]
    assert count == 1
    assert repository.get(draft.draft_id) == updated


def test_sqlite_artisan_storage_does_not_create_choice_analytics_tables(tmp_path: Path) -> None:
    database = tmp_path / "artisan.sqlite3"
    repository = SQLiteArtisanDraftRepository(database)
    repository.save(_representative_draft())

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert tables == {"artisan_drafts"}
    assert "recommendation_events" not in tables
    assert "selection_events" not in tables
    assert "final_requirements" not in tables
