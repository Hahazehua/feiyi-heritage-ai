"""Optional ADK orchestration of existing campaign drafting and deterministic review.

Run in the isolated ADK environment; importing the public web app never imports ADK.
Each invocation owns its runner, callbacks and in-memory session. No publication occurs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from google.adk.agents import BaseAgent, LoopAgent, SequentialAgent
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import Field

from heritagelink.growth_agents import (
    generate_campaign_assets,
    review_campaign_grounding,
    revise_campaign_assets,
)


class _Stage(BaseAgent):
    action: Callable = Field(exclude=True)

    async def _run_async_impl(self, ctx):
        delta, stop = await asyncio.to_thread(self.action)
        yield Event(
            author=self.name,
            actions=EventActions(state_delta=delta, escalate=stop),
        )


@dataclass(frozen=True)
class CampaignLoopResult:
    assets: tuple
    review: object
    revision_count: int
    events: tuple[dict, ...]
    requires_human_review: bool = True

    @property
    def checks_passed(self) -> bool:
        return bool(self.assets) and bool(self.review and self.review.approved)


async def run_adk_campaign_loop(
    context, request, analysis, strategy, *, client=None, maximum_revisions: int = 2
) -> CampaignLoopResult:
    """Draft once, review, revise up to twice, and review the final revision.

    DeepSeek can be supplied through the existing GrowthModelClient protocol.
    Guardian and revision are deterministic capabilities, not independent LLMs.
    Exceptions propagate; there is no synthetic approval on failure/exhaustion.
    """
    if request.product_id != context.product_id or request.artisan_id != context.artisan_id:
        raise ValueError("Request does not match product/artisan context")
    if type(maximum_revisions) is not int or not 0 <= maximum_revisions <= 2:
        raise ValueError("maximum_revisions must be an integer between 0 and 2")
    work = {"assets": (), "review": None, "revisions": 0}

    def draft():
        work["assets"] = generate_campaign_assets(
            context, request, analysis, strategy, client=client
        )
        return {"stage": "draft", "asset_count": len(work["assets"])}, False

    def review():
        decision = review_campaign_grounding(context, work["assets"])
        work["review"] = decision
        # Empty output must not pass a vacuous rule-based review.
        accepted = bool(work["assets"]) and decision.approved
        exhausted = work["revisions"] >= maximum_revisions
        return {
            "stage": "review",
            "checks_passed": accepted,
            "revision_count": work["revisions"],
            "issue_count": len(decision.issues),
            "status": "human_review_required" if accepted else "needs_revision",
        }, accepted or exhausted

    def revise():
        work["assets"] = revise_campaign_assets(context, strategy, work["assets"], work["review"])
        work["revisions"] += 1
        return {"stage": "revision", "revision_count": work["revisions"]}, False

    root = SequentialAgent(
        name="heritage_campaign",
        sub_agents=[
            _Stage(name="drafter", action=draft),
            LoopAgent(
                name="review_revision_loop",
                max_iterations=maximum_revisions + 1,
                sub_agents=[
                    _Stage(name="guardian", action=review),
                    _Stage(name="reviser", action=revise),
                ],
            ),
        ],
    )
    sessions = InMemorySessionService()
    session_id = uuid4().hex
    await sessions.create_session(app_name="haha_adk", user_id="local", session_id=session_id)
    runner = Runner(agent=root, app_name="haha_adk", session_service=sessions)
    events = []
    async for event in runner.run_async(
        user_id="local",
        session_id=session_id,
        new_message=types.Content(
            role="user", parts=[types.Part(text="Run supplied campaign brief")]
        ),
    ):
        events.append({"author": event.author, **event.actions.state_delta})
    return CampaignLoopResult(work["assets"], work["review"], work["revisions"], tuple(events))
