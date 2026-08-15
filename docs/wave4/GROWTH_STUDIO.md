# HAHA Growth Studio — implementation note

HAHA Growth Studio extends the existing Artisan Studio. It does not replace the
Buyer Agent, its seven-Skill manifest, deterministic ranking, or publication gate.

## Architecture mapping

Existing modules reused:

- `heritage_passport.py` and `heritage_passport_models.py` provide product facts,
  provenance, verification status, and publication status.
- `agent_registry.py` now holds a separate `GROWTH_SKILL_REGISTRY` beside the
  unchanged seven-Skill Buyer registry.
- `agent_trace.py` produces the same safe-summary trace contract for Buyer and
  Growth Skills. It records actions and decisions, never chain-of-thought.
- `llm_client.py` remains the only OpenAI-compatible model client. Growth calls use
  bounded JSON prompts and deterministic fallbacks.
- `repositories/` supplies Memory, SQLite, and PostgreSQL Campaign adapters.
- `catalog_eligibility.py` remains the only Buyer-side recommendation gate.

New modules:

- `growth_models.py`: typed workflow, strategy, asset, Guardian, and Campaign models.
- `growth_grounding.py`: separates verified, pending, and unknown product facts.
- `growth_agents.py`: Market, Strategy, Creative, Guardian, and revision domain logic.
- `growth_orchestrator.py`: bounded state machine with at most two revision cycles.
- `ui/growth_studio.py`: Growth Studio presentation and human editing UI.

## Workflow

```text
Product + Heritage Passport
        -> Market Intelligence
        -> Marketing Strategist
        -> Creative Agent
        -> Cultural Guardian
             -> approved: Campaign Ready
             -> rejected: Creative Revision -> Guardian
```

The loop stops after two automatic revisions. Remaining issues are retained as
structured warnings and the campaign becomes `needs_review`.

## Evidence and permissions

Campaign generation uses this order:

1. confirmed structured product facts;
2. confirmed artisan facts;
3. confirmed cultural content and sources;
4. user campaign instructions as instructions, not factual evidence.

Pending and unknown values are shown in the UI but are not promoted into public
claims. Market output is explicitly labelled as a product-grounded AI opportunity
assessment, not externally validated market research.

Campaign approval and product publication are separate permissions. Generating or
saving a campaign never changes `draft`, `pending_review`, `reference_only`,
`recommendable`, or `archived` product status and never inserts an Artisan draft into
the Buyer catalogue.

## Runtime modes

- `Live AI`: use the configured DeepSeek/OpenAI-compatible client; malformed or
  unavailable model output falls back safely.
- `Demo / deterministic`: reproducible competition flow using actual catalogue and
  Heritage Passport data.
- `Safe fallback`: deterministic output without a model call.

The optional Guardian revision fixture is visibly labelled. Its unsupported wording
exists only in the preserved raw demo draft and is removed before final approval.

## Persistence

`MarketingCampaign` retains raw AI text, revised AI text, final human-edited text,
Guardian review, trace events, source mode, revision count, and warning
acknowledgements. Memory storage supports the hosted demo; SQLite and PostgreSQL
adapters provide compatible durable storage paths.

