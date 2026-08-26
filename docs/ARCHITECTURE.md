# HAHA · 飞颐礼遇 — MVP Architecture

## 1. What this architecture is for

HAHA validates pre-transaction gift matching and artisan onboarding in a single
Streamlit application that runs locally. Buyer is the default mode; Artisan
Studio is reached from the top switch or `?mode=artisan`. The two share the
application shell but not their business repositories.

The UI only handles input, session write-back and display. A single agent
orchestrator owns call order, gating and fallback on the buyer path. Field
validation, multi-turn accumulation, recommendation, content assembly and
inquiry construction all sit behind seven independently testable thin-wrapper
Skills.

`inference_policy` / `recommendation_context` separate what the user actually
stated from what was softly inferred. `analytics`, `analytics_models` and
`repositories` separate the UI from anonymous event storage.

The principles the code holds to:

- DeepSeek is an optional field extractor, never the decision-maker.
- Accumulation, validation, question selection and recommendation-readiness are
  decided by local code, not by the model.
- Hard constraints, fixed weights and stable ordering cannot be rewritten by a
  model or by the UI.
- Product master data stays in local CSV; the session lives in Streamlit; only
  consented anonymous choice events reach SQLite or PostgreSQL.
- Artisan drafts use a separate repository, never write to buyer analytics
  tables, and never auto-write into the product CSVs.
- Museum reference facts, MVP product fields and template phrasing must stay
  distinguishable from each other.
- Every artisan fact records its own source and verification status; AI
  candidates require field-by-field human confirmation.
- Unknown customer fields stay unknown. Internal proxy values used inside the
  recommender must never masquerade as customer facts.
- The core flow runs with no API key and no network.
- A missing or failing database never blocks recommendation, selection or plan
  download.

### 1.1 Single-page data flow

```text
Streamlit UI
→ shopping_turn_router  (only recognises compare / refine / select once recommendations exist)
→ agent_orchestrator.run_agent_turn
→ AgentTurnResult

request or refinement → Skills 1–3: understanding, bounded inference, stable ranking
compare current results → ProductComparisonService (application layer; the seven-Skill contract is untouched)
selection and plan     → Skills 4–5: grounded content, final plan
consented capture      → Skill 6: recorded only after explicit consent (refusal or failure never blocks)

explicit offline entry → Skill 7: anonymous aggregates (never written back into recommendation weights)
```

`agent_trace.safe_summary` is the only trace summary boundary. Review mode needs
both the environment switch and `review_mode=1`; the public mode renders no
technical trace. Full design in [`wave3/ORCHESTRATION.md`](wave3/ORCHESTRATION.md).

Repositories never receive raw chat transcripts. Recommendation events derive a
stable UUID from the session ID and a recommendation signature; selection events
derive theirs from the recommendation event and product ID. Database constraints
and upserts together absorb duplicate writes caused by Streamlit reruns.

The capture service returns a structured safe status, and database errors are
contained at the analytics boundary. Choice-signal analysis runs from a separate
CLI or service call; it never appears in the public customer UI and never
influences live recommendations automatically.

### 1.2 AI Shopping application layer

`RequestedAction` remains the single model of user intent, extended
backward-compatibly with:

- `compare_recommendations` — compare all current formal recommendations
- `compare_selected_products` — compare a given ordinal range of them
- `refine_recommendations` — feed a relative preference back through Skills 1–3
- `explain_difference` — explain differences without re-running recommendation
- `select_product` — natural-language selection, reusing the Skills 4–6 path

`shopping_turn_router` sits ahead of Skill 1 and resolves only ordinals and
action intent within an existing recommendation context. It reads no product
facts, computes no scores and creates no new session state machine. With no
current recommendation, the message stays `continue_conversation` and enters
Skill 1 as usual.

Comparison still calls `run_agent_turn(...)`. The orchestrator hands the action
to the application-layer `ProductComparisonService` and records in the formal
seven-item `execution_trace` that no Skill ran; the structured comparison and its
safety information are stored separately as `application_trace`. Both the
`AgentTurnResult.execution_trace` contract and the agent manifest are therefore
unchanged.

The comparison service's chain of trust:

```text
current ProgressiveRecommendationResult allowlist
→ full Product lookup
→ catalog_role == recommendation_demo
→ product / merchant / heritage status == active
→ original recommendation order
→ structured ProductComparisonResult
→ optional injected grounded narration, or deterministic fallback
```

The double check keeps forged recommendation snapshots, stale products and the
30 `inactive/catalog_reference` records out of formal comparison. The service
invents no comparison score and no new ranking: reorder `product_ids` on the way
in and the output still follows the original recommendation order.

Each displayable fact is carried by `ComparisonEvidence` in one of four
`EvidenceState`s — `verified_yes`, `verified_no`, `unknown`,
`not_applicable`. Price, customisation, quantity, lead time, portability and
international shipping each consult their own fact status first. Without a
reliable source the value stays `unknown`: a non-empty demo field is never
promoted to confirmed, and a missing value is never displayed as a negative fact.

Optional narration is dependency-injected into `ProductComparisonService` and
receives only the sanitised structured comparison. If narration raises or fails a
safety check, the service returns the pre-generated deterministic summary. With
no narration client injected — the orchestrator's default — the core comparison
depends on neither API nor network.

`AgentSessionState` holds the current `comparison_result` and at most three
entries of `comparison_history`, both only for the life of the Streamlit session.
Restarting clears them, and existing anonymous choice consent never causes
comparison history to be persisted.

### 1.3 Artisan Studio and Heritage Passport

Artisan Studio does not pass through `run_agent_turn(...)` and registers no new
Skill. It records a sanitised trace under the application action
`artisan_product_onboarding` and does its work through local services: draft
creation, candidate field extraction, bilingual drafting, conflict detection,
field-by-field human confirmation, passport construction and submission.

```text
Artisan Streamlit mode
→ ArtisanProductDraft (its own session draft)
→ optional extraction / writing client, or deterministic fallback
→ ProvenancedFact + BilingualProductDraft
→ explicit field-level human confirmation
→ HeritagePassport
→ ArtisanDraftRepository
→ pending_review
```

`FactSource` and `VerificationStatus` are orthogonal. `artisan_provided`
describes where a value came from and never becomes `confirmed` on its own;
`ai_inferred` can never be confirmed directly. Inconsistencies across price,
materials, customisation, MOQ, shipping and lead time raise a `FactConflict`,
and submission is blocked until the user explicitly resolves the value.

Publication status runs `draft → pending_review →
reference_only / recommendable / archived`. Submission only reaches
`pending_review`. The review-mode simulation neither converts a draft into a
canonical `Product` nor edits any CSV; production would additionally need an
explicit publication transaction covering identity, merchant, provenance and
commercial capability.

The unified eligibility gate ahead of Skill 3 accepts only canonical products
whose logical publication status is `recommendable`. To leave the existing CSV
contract untouched, an adapter treats `recommendation_demo` records whose
product, merchant and craft statuses are all `active` as legacy `recommendable`,
and `catalog_reference/inactive` as `reference_only`. So `draft`,
`pending_review`, `reference_only`, `archived` and every artisan record not
explicitly wired into the catalogue are excluded. The boundary of **23 formal
demo recommendations, 30 references, 1 partner record pending verification and
54 canonical records** is unchanged.

Confirmation is grouped by consequence rather than by origin. Descriptive facts
are confirmed in one action; price, currency, MOQ, lead time, shipping,
customisation, logo support, source URLs and named ICH projects each keep their
own confirmation, because a buyer transacts on those and a model could invent a
plausible source URL. A guard test blocks a single bulk confirmation from ever
marking a commercial term confirmed.

## 2. Repository layout

The files the current implementation actually uses, excluding `.git`, caches,
virtualenvs and competition automation:

```text
feiyi-heritage-ai-publish/
├── app.py
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── data/
│   ├── demo/
│   │   ├── merchants.csv
│   │   ├── heritage_items.csv
│   │   ├── products.csv
│   │   ├── product_texts.csv
│   │   └── customization_options.csv
│   └── catalog/
│       ├── heritage_products.csv
│       ├── source_registry.csv
│       ├── coverage_matrix.csv
│       └── research_log.csv
├── assets/catalog/products/          # 54 local catalogue images
├── static/pitch-deck.pdf             # served beside the app for the roadshow
├── src/heritagelink/                 # 39 modules
│   ├── config.py                     # DeepSeek environment configuration
│   ├── llm_client.py                 # OpenAI-compatible calls, safe error mapping
│   ├── dialogue_prompt.py            # bounded JSON extraction constraints
│   ├── conversation_state.py         # immutable in-session conversation state
│   ├── dialogue_manager.py           # process_turn, merging, questions, signature
│   ├── request_parser.py             # parsing, local validation, deterministic fallback
│   ├── models.py                     # domain types and enums
│   ├── data_loader.py                # loads and validates the five demo CSVs
│   ├── catalog.py                    # museum reference catalogue and image checks
│   ├── recommender.py                # hard filters, eight-dimension scoring, stable order
│   ├── progressive_recommender.py    # modes, coverage, normalisation over known dimensions
│   ├── catalog_eligibility.py        # the gate shared by Skill 3 and comparison
│   ├── comparison_models.py          # comparison schema, EvidenceState, application trace
│   ├── product_comparison.py         # structured comparison with narration fallback
│   ├── shopping_turn_router.py       # post-recommendation compare / refine / select routing
│   ├── heritage_passport_models.py   # fact source, verification, publication status
│   ├── heritage_passport.py          # conservative canonical Product → passport adapter
│   ├── artisan_studio.py             # drafts, fallback, conflicts, confirmation, submission
│   ├── agent_registry.py             # the canonical Skill registries
│   ├── growth_agents.py              # the artisan growth chain
│   ├── content.py                    # local bilingual content assembly
│   ├── customization_concept.py      # standalone concept when nothing qualifies
│   ├── inquiry.py                    # InquiryRequestContext and inquiry JSON
│   ├── repositories/
│   ├── i18n/{zh_CN,en_US}.py         # interface copy, key-for-key identical
│   └── ui/                           # theme, components, cards, gallery, passport
├── tests/                            # 42 test modules, 368 tests
│   ├── conftest.py                   # blocks real DeepSeek network calls
│   └── evaluation_cases.json         # 14 deterministic regression cases
├── deploy/                           # Dockerfile, compose, nginx, deploy.sh
└── docs/
```

`CONTRIBUTING.md`, `SUBMISSIONS.md`, `submissions.json` and `.forgejo/` are
competition baseline or automation files, not business modules.

## 3. End-to-end data flow

### 3.1 Buyer

```text
first natural-language turn, follow-up, or the detailed form
  → dialogue_manager.process_turn / request_parser
  → locally validated ParsedCustomerRequest
  → user revises and confirms on the confirmation page
  → progressive_recommender.recommend_progressively
  → recommender.recommend
  → 0–3 qualifying demo products, or an explicit no-result with conflicts
  → content.generate_bilingual_content
  → InquiryRequestContext + build_customization_inquiry
  → on-page preview, copy, and UTF-8 JSON download
```

Component responsibilities:

1. `config` reads DeepSeek environment variables and judges key validity. It
   never prints a key to the page or the log.
2. `llm_client` requests bounded JSON, disables thinking mode, retries a
   transient error at most once, and maps authentication, balance, timeout,
   network, empty-response and malformed-JSON failures to safe errors.
3. `dialogue_manager.process_turn` handles first and follow-up turns, calls the
   optional model or the deterministic parser, then merges fields locally,
   picks at most one question, and computes coverage and the request signature.
4. `request_parser` applies a field allowlist plus type, enum, amount and
   cross-field validation to untrusted extraction. Total-budget conversion uses
   local decimal arithmetic.
5. `app.py` shows the session's history in an expander on the confirmation page
   and advances only through an explicit "merge this addition" button. The
   detailed form remains a complete fallback entry point.
6. `data_loader` reads the five `data/demo` CSVs and validates columns, types,
   primary and foreign keys, enums, amounts, quantities, bilingual rows, images
   and demo declarations.
7. `catalog` reads the museum reference catalogue and validates source URL,
   licence, local image and the one-to-one `demo_product_id` link.
8. `progressive_recommender` passes only known constraints to the base
   recommender and computes mode, information coverage, confidence,
   participating dimensions and independent alternatives.
9. `recommender` applies unbypassable hard filters, eight-dimension scoring and
   stable ordering. It never calls DeepSeek.
10. `content` assembles only local zh/en material, sources and review status. It
    performs no runtime machine translation and writes no missing facts.
11. `InquiryRequestContext` carries what the customer actually confirmed. Unknown
    budget, quantity, customisation, logo, shipping and lead time stay `None`.
12. `inquiry` builds JSON from customer context, exactly one selected product
    snapshot, bilingual content and open questions, validating before download.
13. `shopping_turn_router` maps comparison, difference, relative refinement and
    ordinal selection onto existing `RequestedAction`s — only when a current
    recommendation exists.
14. `product_comparison` reads the current `ProgressiveRecommendationResult`,
    `RecommendationContext` and the full catalogue snapshot, re-checks the
    allowlist and formal eligibility, then builds the structured comparison. It
    calls no recommender and reorders nothing.
15. `ui.comparison` renders that same structure as a desktop matrix and mobile
    cards. The customer layer shows no technical score, internal ID or narration
    source.
16. `ApplicationExecutionTrace` appears only in review mode, as a separate
    application action, kept apart from the fixed seven `SkillExecutionTrace`s.

### 3.2 Artisan

1. `app.py` renders Artisan Studio inside the same application via the top switch
   or `mode=artisan`; buyer remains the default.
2. `ArtisanProductDraft` holds incomplete work details, an optional image, the
   bilingual draft, conflicts and publication timestamps.
3. `artisan_studio` treats model output strictly as candidates, writing them as
   `ai_inferred/pending_review` after a field allowlist and local validation, and
   falls back deterministically when the model fails.
4. `confirm_facts` upgrades only the fields the user explicitly selected this
   time to `artisan_confirmed/confirmed`; the bilingual draft is confirmed
   separately.
5. `build_passport` aggregates cultural and commercial verification separately.
   Unknown commercial conditions stay unknown and are never displayed as
   unsupported.
6. `submit_for_review` refuses unresolved conflicts, writes the draft to the
   separate `ArtisanDraftRepository` and sets `pending_review`.
7. The simulated review demonstrates a status change only. It writes nothing to
   buyer product master data or to the anonymous analytics repository.

## 4. Dialogue understanding and local authority

### 4.1 The model's boundary

DeepSeek supplies candidate structured fields, nothing more. A model-returned
`ready_to_recommend`, `recommended_action`, question or confidence value cannot
drive business state directly. Local code decides:

- merging new fields with old
- rejecting unknown fields, illegal types and illegal enums
- total-budget conversion
- which fields count as known, missing or uncertain
- question priority, and at most one question per turn
- the recommendation signature and whether recomputation is needed
- all product eligibility, scores and ordering

With no key, or when a model call fails, `demo_parse_request` provides clearly
labelled limited keyword and regex parsing. That degradation changes only how
fields are extracted — recommendation, content and inquiry logic are untouched.

### 4.2 ConversationState

Within the current Streamlit session, `ConversationState` holds the
`conversation_id`, displayable messages and per-turn raw text; the locally
validated `accumulated_request`; missing required, missing optional and uncertain
fields; the current single follow-up question; stage, coverage and clarification
count; and the user's explicit fields plus the last recommendation signature.

Each follow-up produces a new immutable state through `process_turn`. Sessions
are not written to a database and offer no accounts, cross-device sync or
long-term history.

## 5. Recommendation engine

### 5.1 Progressive input

When budget, quantity or preferences are absent, the progressive adapter may
construct internal proxy values used solely to run the base recommender per
product. **Those values must never reach the user summary or the inquiry.** Real
customer facts come from `ParsedCustomerRequest` and `InquiryRequestContext`.

Modes:

- `exploring` — too few personalising fields; show catalogue direction
- `guided` — some of recipient, occasion, style or symbolism known
- `constrained` — hard conditions known: budget, quantity, customisation, logo,
  lead time or international shipping

### 5.2 Explicit hard constraints

The base recommender checks, in order:

1. product, demo-merchant and craft-category status
2. minimum demo unit price within the user's explicit per-item ceiling
3. quantity at or above MOQ, and not above a non-empty demo maximum
4. every explicitly required customisation type is supported
5. an enabled logo option exists when logo is explicitly required
6. available lead time covers the base period plus the largest required
   customisation surcharge
7. the product may enter international shipping assessment when that is required

Apart from status, a filter engages only for fields the user supplied explicitly
and did not mark uncertain. "Meets every explicit hard constraint" means no known
necessary condition is violated — not that information is complete, that the item
is genuinely for sale, or that a merchant has committed to fulfil it.

### 5.3 Fixed scoring and ordering

| Dimension | Base weight |
|---|---:|
| Budget fit | 25 |
| Recipient | 15 |
| Occasion | 15 |
| Style preference | 15 |
| Cultural symbolism | 10 |
| Customisation fit | 10 |
| Quantity and capacity headroom | 5 |
| Delivery headroom | 5 |
| Total | 100 |

The progressive layer normalises the base score to 0–100 over the participating
dimensions only. Unknown dimensions display as "to be supplied" — never scored
zero, never shown as a match. `Recommendation.total_score` carries the normalised
current match score shown on the page; with no participating dimension at all,
pure exploration uses a neutral display score of 50 and sorts stably by
`product_id`. **That number is not a purchase probability, a success rate, or a
business metric.**

Results sort by `total_score desc, product_id asc`, at most three. The page shows
information coverage, low/medium/high confidence and the eight-dimension status
together. Confidence describes information coverage only — not purchase
probability, and not merchant satisfaction.

### 5.4 No result

If nothing satisfies every explicit hard constraint, the qualifying set is empty.
The page shows conflict statistics, adjustable directions and separate
conflicting reference products. It does not quietly relax the user's constraints.

`customization_concept.py` can build a standalone concept with
`is_existing_product=false`. It must contain no invented product ID or name, and
is not the same thing as a selected product's `customization_inquiry`.

## 6. Data and content boundaries

### 6.1 Current dataset

`data/demo/` currently holds:

- 1 platform demo curation entity, plus 1 named partner merchant
- 11 craft categories — 10 at `official_level=unverified`, 1 `national`
  (芜湖铁画, Wuhu iron painting)
- 54 catalogue records with images: 23 `recommendation_demo/active`,
  30 `catalog_reference/inactive`, 1 `partner_pending_verification/inactive`
- 108 bilingual cultural records, all `review_status=draft`
- 51 MVP customisation options

Price, quantity, lead time, shipping and customisation capability are MVP demo
fields pending merchant review. They are neither a quotation nor a capacity
commitment.

### 6.2 Museum reference

`data/catalog/heritage_products.csv` stores the museum source page, historical
metadata, image licence, local path and `museum_reference_not_for_sale` status.
Museum objects serve only as image, craft and cultural reference. They are not
sold on the platform, and are never used to infer a product's price, capacity,
lead time, shipping or customisation capability.

### 6.3 Bilingual content

`product_texts.csv` holds one `zh-CN` and one `en` record per catalogue entry.
`content.py` only assembles those fields and their source notes:

- only `approved` may indicate that review is complete
- `draft` must display "demo copy, pending merchant review"
- missing fields display "待商家确认 / Pending merchant confirmation"
- all 108 current records are `draft` and must never be called merchant-reviewed
- no runtime machine translation, RAG or model-generated cultural facts

## 7. Merchant inquiry

The proxy `GiftRequest` the recommender builds for missing input serves per-product
computation only. `app.py::_inquiry_context` builds `InquiryRequestContext` from
the user's confirmed `ParsedCustomerRequest`, keeping these `None` when unknown:
per-item and total budget, quantity, whether customisation is required, whether a
logo is required, whether international shipping is required, and available lead
time.

`build_customization_inquiry` takes one qualifying recommendation, bilingual
content, presentation detail and customer context, and emits a bilingual MVP
declaration, the request snapshot with `pending_fields`, exactly one selected
product snapshot, customisation and delivery fields, and merchant action items
with open questions.

The page shows the declaration, pending values, a copyable summary and a JSON
download. **The inquiry is not a contract, order, quotation, stock, capacity or
delivery commitment.**

## 8. Trust boundaries, errors and degradation

- **Browser input** — bounded length, enums and numeric ranges; user text never
  builds a path or filename.
- **Model output** — untrusted JSON, always through the local allowlist and
  business validation.
- **Local CSV** — validated at startup; an error names the file, row or ID, field
  and the direction of the fix.
- **Demo marking** — `MVP 演示数据 / MVP demo data` shown globally; the inquiry
  carries both `is_demo` and a bilingual declaration.
- **No key or API failure** — safe fallback to deterministic parsing; the
  detailed form and the rest of the core flow stay available.
- **Nothing qualifies** — return zero qualifying recommendations rather than
  pushing a conflicting one.
- **Missing content** — never auto-translated or written in; displayed as pending.
- **Inquiry validation failure** — no partial JSON is emitted.

## 9. Test architecture

**368 tests across 42 modules**, grouped as parsing and dialogue; recommendation
(including `evaluation_cases.json`); shopping routing and comparison; artisan
domain, repository, confirmation and publication gating; data and provenance;
content and inquiry; end-to-end UI; and import boundaries.

`tests/conftest.py` sets a placeholder key and replaces real OpenAI-compatible
completion calls with an immediately failing guard, so an accidental external API
call fails the test rather than incurring cost.

Several tests guard the product's central claim rather than its behaviour: a
record declaring itself unverified may not appear in the museum table, claim an
open museum licence, or present commercial terms as confirmed without a real
merchant behind them; and this documentation's own catalogue figures are
recomputed from the CSVs. **Each of those guards was mutation-tested** — the rule
was deliberately broken to confirm the test fails — because a guard that passes
vacuously is worse than none.

`tests/evaluation_cases.json` is a deterministic regression set of 14 cases, not
a leaderboard dataset labelled by merchants or domain experts. Actual commands
and manual smoke results live in `docs/wave2/EVALUATION.md`.

## 10. Boundaries and where this could go

This iteration includes the Artisan Studio prototype inside the same Streamlit
application, a separate draft repository, per-field provenance and confirmation,
the Heritage Passport and a publication-status demonstration.

It does **not** include RAG, a vector database, a production database, real
identity or merchant verification, a multi-merchant back office, user accounts,
payment, logistics, tax, formal orders, or a production-grade permission and
audit system.

Formal storage, a merchant workbench, sourced retrieval and model-assisted
drafting could follow once real merchants and users have validated the flow — but
only while preserving the explicit hard-constraint layer, the deterministic rule
baseline, source/review/demo status, the rule that unknown customer facts are
never overwritten by proxy values, and reproducible tests and audit records.

## Wave 4 extension: HAHA Growth Studio

The artisan application includes a separate Growth Studio state machine:

```text
Heritage Passport → Market Intelligence → Strategy → Creative → Guardian
                                                        ^           |
                                                        |-- revision |
```

The revision loop is bounded to two cycles. It reuses the existing agent registry
and safe trace contracts while leaving the original seven-Skill buyer chain
unchanged. Campaign storage uses repository adapters, isolated from anonymous
buyer analytics and from catalogue publication. See
[`wave4/GROWTH_STUDIO.md`](wave4/GROWTH_STUDIO.md) for the detailed mapping and
safety boundaries.

## Story Studio Phase 1 extension

Story Studio consumes the same verified/unverified/unknown partition as Growth
Studio, but produces a provider-neutral production package:

```text
Heritage Passport facts → Story Core + claim ledger → 60s / 6-scene storyboard
                                                → Story Guardian → human decision
                                                                    → JSON export
```

`story_service.py` owns deterministic generation, fact-reference construction,
Guardian checks, and approval transitions. `ui/story_studio.py` only renders
those domain objects. Image and video prompts are data fields rather than API
calls, so a future provider adapter cannot bypass provenance or approval rules.
See [`STORY_STUDIO_PHASE1.md`](STORY_STUDIO_PHASE1.md) for the runnable demo path
and current boundary.

Phase 2 adds provider-neutral visual production after the human script gate:

```text
approved StoryProject + VisualBible
        → ImageProvider (demo | OpenAI | future adapter)
        → scene variants → human selection → per-scene approval → ZIP export
```

`image_providers.py` contains the provider contract and adapters;
`story_visual_models.py` owns visual continuity, artifact, selection, and approval
state; `story_visual_service.py` owns constrained media storage and transitions.
External providers cannot run against an unapproved story. Provider failures are
stored as recoverable scene errors and do not erase other generated versions. See
[`STORY_STUDIO_PHASE2.md`](STORY_STUDIO_PHASE2.md).
