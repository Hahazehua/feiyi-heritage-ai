"""Exercise real ADK scheduling with controlled drafting/review capabilities."""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("google.adk")
from heritagelink import adk_campaign as module  # noqa: E402


@pytest.mark.parametrize(
    "failures,limit,revisions,accepted",
    [
        (0, 2, 0, True),
        (1, 2, 1, True),
        (9, 2, 2, False),
        (9, 0, 0, False),
    ],
)
def test_adk_loop_stops_or_exhausts(monkeypatch, failures, limit, revisions, accepted):
    calls = []
    monkeypatch.setattr(module, "generate_campaign_assets", lambda *a, **k: ("draft",))

    def review(*args):
        calls.append("review")
        return SimpleNamespace(approved=len(calls) > failures, issues=())

    monkeypatch.setattr(module, "review_campaign_grounding", review)
    monkeypatch.setattr(module, "revise_campaign_assets", lambda *a: ("revised",))
    identity = SimpleNamespace(product_id="p", artisan_id="a")
    result = asyncio.run(
        module.run_adk_campaign_loop(identity, identity, None, None, maximum_revisions=limit)
    )
    assert result.revision_count == revisions
    assert result.events[-1]["checks_passed"] is accepted
    assert len(calls) == revisions + 1
    assert result.requires_human_review
    assert result.events[0]["author"] == "drafter"
    assert result.events[-1]["author"] == "guardian"


def test_empty_draft_cannot_pass(monkeypatch):
    monkeypatch.setattr(module, "generate_campaign_assets", lambda *a, **k: ())
    monkeypatch.setattr(
        module, "review_campaign_grounding", lambda *a: SimpleNamespace(approved=True, issues=())
    )
    identity = SimpleNamespace(product_id="p", artisan_id="a")
    result = asyncio.run(
        module.run_adk_campaign_loop(identity, identity, None, None, maximum_revisions=0)
    )
    assert not result.events[-1]["checks_passed"]


def test_request_scope_is_validated():
    with pytest.raises(ValueError):
        asyncio.run(
            module.run_adk_campaign_loop(
                SimpleNamespace(product_id="p", artisan_id="a"),
                SimpleNamespace(product_id="other", artisan_id="a"),
                None,
                None,
            )
        )


def test_concurrent_runs_do_not_share_drafts(monkeypatch):
    monkeypatch.setattr(module, "generate_campaign_assets", lambda ctx, *a, **k: (ctx.product_id,))

    def review(ctx, assets):
        assert assets == (ctx.product_id,)
        return SimpleNamespace(approved=True, issues=())

    monkeypatch.setattr(module, "review_campaign_grounding", review)

    async def run():
        identities = [SimpleNamespace(product_id=p, artisan_id="a") for p in ("first", "second")]
        return await asyncio.gather(
            *[module.run_adk_campaign_loop(i, i, None, None) for i in identities]
        )

    results = asyncio.run(run())
    assert [result.assets for result in results] == [("first",), ("second",)]
