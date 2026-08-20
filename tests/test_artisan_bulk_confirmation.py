"""Confirming in bulk must cost friction, not provenance.

The artisan review step existed to make a human vouch for each fact before it
could be published. Reviewers asked for it to be less tedious. Cheapening the
confirmation is fine for descriptive facts; doing it for the terms a buyer
transacts on would turn "the artisan vouched for this" into "the artisan
clicked once", which is the thing the step exists to prevent.
"""

from __future__ import annotations

import pytest

from heritagelink.artisan_studio import (
    INDIVIDUAL_CONFIRMATION_FIELDS,
    bulk_confirmable_fields,
    confirm_facts,
    create_draft,
    enrich_draft,
    is_ai_proposed,
    requires_individual_confirmation,
)
from heritagelink.heritage_passport_models import VerificationStatus

DESCRIPTION = (
    "一件芜湖铁画迎客松，尺寸约 45x60 厘米，价格 800-1200 元，支持题字与 Logo，企业礼赠用。"
)


def _draft():  # type: ignore[no-untyped-def]
    draft = create_draft(
        "session_bulk",
        {"product_name_zh": "迎客松铁画", "craft_name": "芜湖铁画锻制技艺"},
        description=DESCRIPTION,
    )
    enriched = enrich_draft(draft)
    return enriched[0] if isinstance(enriched, tuple) else enriched


@pytest.fixture()
def draft():  # type: ignore[no-untyped-def]
    return _draft()


def test_commercial_terms_are_never_bulk_confirmable(draft) -> None:  # type: ignore[no-untyped-def]
    """The fields a buyer acts on stay out of the one-click group."""
    bulk = set(bulk_confirmable_fields(draft))

    assert bulk.isdisjoint(INDIVIDUAL_CONFIRMATION_FIELDS)
    for name in ("price_min_fen", "price_max_fen", "currency", "logo_supported"):
        assert name not in bulk, name


def test_descriptive_facts_are_bulk_confirmable(draft) -> None:  # type: ignore[no-untyped-def]
    """Otherwise the bulk action saves nothing and the friction complaint stands."""
    bulk = set(bulk_confirmable_fields(draft))

    assert "product_name_zh" in bulk
    assert "craft_name" in bulk
    assert len(bulk) >= 3, "a bulk action that covers almost nothing is not a fix"


def test_an_ai_proposal_is_flagged_without_being_held_back(draft) -> None:  # type: ignore[no-untyped-def]
    """Origin drives what the artisan is shown, consequence drives the grouping."""
    inferred = tuple(fact for fact in draft.facts if is_ai_proposed(fact))

    assert inferred, "the fixture should exercise model-proposed values"
    descriptive = tuple(fact for fact in inferred if not requires_individual_confirmation(fact))
    assert descriptive, "AI-proposed descriptive fields still belong in the bulk group"


def test_unknown_and_already_confirmed_facts_are_excluded(draft) -> None:  # type: ignore[no-untyped-def]
    """There is nothing to vouch for in a blank, and nothing to redo in a tick."""
    for name in bulk_confirmable_fields(draft):
        fact = next(item for item in draft.facts if item.field_name == name)
        assert fact.value not in (None, "", (), [])
        assert fact.verification_status is not VerificationStatus.CONFIRMED

    once = confirm_facts(draft, bulk_confirmable_fields(draft))

    assert set(bulk_confirmable_fields(once)) == set()


def test_bulk_confirming_leaves_commercial_terms_pending(draft) -> None:  # type: ignore[no-untyped-def]
    """The guard that matters: one click must not publish a price."""
    confirmed = confirm_facts(draft, bulk_confirmable_fields(draft))

    priced = tuple(
        fact
        for fact in confirmed.facts
        if fact.field_name in INDIVIDUAL_CONFIRMATION_FIELDS
        and fact.value not in (None, "", (), [])
    )
    assert priced, "the fixture should carry commercial values to guard"
    for fact in priced:
        assert fact.verification_status is not VerificationStatus.CONFIRMED, fact.field_name


def test_individual_confirmation_still_works(draft) -> None:  # type: ignore[no-untyped-def]
    """Explicitly naming a commercial field does confirm it — the gate is the UI
    grouping plus an explicit action, not a ban on ever confirming a price."""
    confirmed = confirm_facts(draft, ("price_min_fen",))

    fact = next(item for item in confirmed.facts if item.field_name == "price_min_fen")
    assert fact.verification_status is VerificationStatus.CONFIRMED
