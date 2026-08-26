# HAHA Story Studio — Phase 1 delivery

## Outcome

Phase 1 turns confirmed artisan/product facts into a reviewable, exportable video
production package without requiring an external LLM, image, or video API.

The current Xiaohongshu package contains:

- one evidence-led Story Core and claim ledger;
- one of three narrative templates: Object Record, Artisan Life, or Time Dialogue;
- six 9:16 scenes with durations `5 + 12 + 12 + 12 + 12 + 7 = 60` seconds;
- voiceover, on-screen text, visual direction, and camera direction per scene;
- provider-neutral image and video prompts per scene;
- stable fact references and available HTTPS source links;
- a structured Story Guardian result;
- an explicit human approve, request-revision, or reject decision;
- a downloadable UTF-8 JSON production package.

## Demo path

1. Start the application with `python -m streamlit run app.py` and open the
   artisan side (`?mode=artisan`).
2. Choose **Story Studio**.
3. Select a product, narrative template, and script language.
4. Choose **Generate script and run Guardian**.
5. Open the six scenes and inspect voiceover, visual direction, fact IDs, sources,
   and future provider prompts.
6. Review the Story Guardian result. A clean script waits for human approval; a
   failed script cannot be approved.
7. Approve, request revision, or reject. Approved packages can be exported as
   JSON.

## Fact and approval boundary

Public script facts may come only from `GrowthProductContext.verified_facts`.
Pending oral accounts, unknown fields, and user-supplied claims are excluded from
generation. The Guardian independently checks that references still correspond
to the selected product and flags pending values and unsupported credential,
certification, heritage-age, or shipping language.

The automated review never performs the final approval. The project must be in
`awaiting_human_approval`, with a clean Guardian result, before a human `approve`
decision can move it to `approved`.

## Provider independence

The production package deliberately stops at text, prompts, and evidence. A later
image or video adapter receives an approved `StoryScript`; it does not own story
generation, fact selection, Guardian policy, or human approval. This means
OpenAI, Gemini, DashScope, Seedream, Runway, Kling, or another provider can be
replaced without changing the core data and safety contracts.

Phase 1 makes no external media API calls and stores no provider keys.

## Verification

Focused coverage is in `tests/test_story_studio.py` and `tests/test_story_app.py`.
It verifies deterministic 60-second generation, verified-only facts, Guardian
fail-closed behavior, approval transitions, bilingual output, the complete UI
flow, and JSON availability.
