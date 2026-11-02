# ADK campaign drafting / review adapter

This optional local adapter uses real Google ADK `SequentialAgent`, `LoopAgent`,
custom `BaseAgent` stages, `Runner`, events and an in-memory session. It reuses the
existing Growth Studio capabilities instead of changing the public web RAG path.

Flow: draft → Guardian → (revise → Guardian), with at most two revisions. Passing
checks exits the loop; exhaustion also stops and leaves the content for human review.
The last revision is always reviewed. Empty drafts do not pass the orchestration gate.
No stage publishes, sends messages or updates catalogue eligibility.

Drafting uses `generate_campaign_assets`, which supports the existing DeepSeek client
and deterministic fallback. Guardian and revision remain deterministic rule-based
capabilities. This implementation must not be described as two LLMs independently
reviewing each other. Existing rule checks do not establish general factual accuracy.

## Run the framework tests

Use a separate environment: ADK 2.13 requires Starlette >=1.3.1, whereas the current
web project pins Starlette below 1. Installing both together is not supported here.

```powershell
python -m venv .local/adk-venv
.local/adk-venv/Scripts/python -m pip install -r requirements-adk.txt
$env:PYTHONPATH = 'src'
.local/adk-venv/Scripts/python -m pytest tests/test_adk_campaign.py
.local/adk-venv/Scripts/python scripts/demo_adk_campaign.py
```

## Call from an asynchronous integration

```python
from heritagelink.adk_campaign import run_adk_campaign_loop

# Use validated Growth Studio objects; do not accept a caller's verification flags.
result = await run_adk_campaign_loop(
    context, request, analysis, strategy, client=existing_deepseek_client,
    maximum_revisions=2,
)
# Inspect result.events and result.review; preserve human approval before publication.
# Use result.checks_passed, which also rejects empty output.
```

Inputs are the same typed context, request, market analysis and strategy consumed by
the existing creative capability. Each call owns its callback state, runner and session.
Events include stage, revision count, issue count and check status, not raw product facts
or generated text. Session state records control metadata; assets stay in invocation-local
memory. There is no durable resume across process restarts in this adapter.

Tests exercise real ADK orchestration with controlled capability outputs, without API
spend. They do not demonstrate a live model or deployed integration. The public website
still uses its existing single-call RAG workflow. A separate deployment or dependency
migration, API integration, authentication/quotas and live acceptance are required before
exposing this adapter publicly.

References: [ADK loop workflow](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/loop-agents.md),
[custom agents](https://github.com/google/adk-docs/blob/main/docs/agents/custom-agents.md).

## Local validation, November 2, 2026

Six framework tests passed against ADK 2.13.0. The executable synthetic demonstration
also ran actual Growth Studio drafting/review/revision functions: four assets, eight
initial Guardian issues, one revision, then zero issues and human review required.
No provider API was called. In this pinned ADK version, SequentialAgent and LoopAgent
still run but are deprecated in favor of Workflow; migrate to the graph API before a
long-lived deployment. The compatibility adapter intentionally keeps this visible.

Changed-file Ruff lint/format checks passed. A full legacy pytest run was started
but interrupted before completion; no full-suite pass is claimed for this change.
Whole-repository Ruff currently reports 175 existing errors and 20 formatting issues
in the separate haha-data-engineering tree; those files were not changed here.
