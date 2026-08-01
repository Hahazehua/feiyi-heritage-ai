---
name: capture-consented-choice
description: Save a HeritageLink gift recommendation and final choice as privacy-minimized anonymous events only after explicit user consent. Use when a user selects a recommended product or generates a customization brief and the system must validate consent, preserve idempotency across Streamlit reruns, or safely handle unavailable SQLite/PostgreSQL storage.
---

# Capture Consented Anonymous Choice

## Name

Use `capture-consented-choice` / 匿名授权选择记录.

## Purpose

Persist an anonymous session summary, final structured requirement, recommendation event, selection event, and optional feedback. Do not generate recommendations or change ranking.

## Trigger

Run only when all conditions hold:

1. A recommendation event exists.
2. The user selects a product or generates a customization brief.
3. The user explicitly grants the displayed anonymous analytics consent.

Return `skipped_no_consent` without writing when consent is absent. Return `skipped_no_selection` when no final action exists.

## Inputs

Accept consent version/time, anonymous session metadata, `RecommendationContext`, `RecommendationEvent`, and `SelectionEvent`. Treat optional requirement and feedback fields as nullable. Read the exact field contract in [references/event-schema.md](references/event-schema.md).

## Outputs

Return `CaptureChoiceResult` with `status`, `event_id`, `saved`, `duplicate`, `storage_backend`, and `error_category`. Supported statuses are `saved`, `skipped_no_consent`, `skipped_no_selection`, `duplicate_ignored`, `storage_unavailable`, and `validation_failed`.

Never show backend names, UUIDs, SQL messages, or `error_category` in the customer UI.

## Processing Steps

1. Check explicit consent before touching a repository.
2. Require a selection/final action.
3. Validate the anonymous session → recommendation → selection chain.
4. Build privacy-minimized records from the effective structured request.
5. Save session, requirement, recommendation, then selection through `ChoiceRepository`.
6. Interpret stable-ID conflicts as duplicates.
7. Catch repository failures and return `storage_unavailable`.

## Business Rules

- Generate session IDs with random UUID4; never derive them from identity or device data.
- Generate recommendation and selection IDs with stable UUID5 inputs.
- Keep one recommendation per `(anonymous_session_id, recommendation_signature)`.
- Ignore an identical selection rerun; create a new event when the selected product changes.
- Represent customization-brief generation as the selection's final action.
- Never modify product eligibility, recommendation scores, or ranking.

## Privacy Boundary

Do not store names, phone numbers, email, detailed addresses, company names, identity documents, IP addresses, account IDs, credentials, API keys, or full chat text. Keep `ANALYTICS_STORE_RAW_CHAT=false`; this implementation has no raw-chat field.

## Failure and Fallback

Allow recommendation, selection, final-plan generation, and download to continue when analytics is disabled, unconfigured, invalid, or unavailable. Log technical failures internally and keep the customer message nontechnical.

## Code Entry Points

- Service: `src/heritagelink/analytics_service.py::capture_consented_choice`
- Event builders/configuration: `src/heritagelink/analytics.py`
- Records: `src/heritagelink/analytics_models.py`
- Repositories: `src/heritagelink/repositories/`
- Streamlit integration: `app.py::_persist_choice`

## How to Run

Set `ANALYTICS_ENABLED=true` and a local `sqlite:///...` URL, start `python -m streamlit run app.py`, grant anonymous consent, and select a product. Do not use production data for a demo.

## Evaluation

Run:

```powershell
python -m pytest tests/test_analytics.py tests/test_analytics_service.py tests/test_choice_repositories.py
```

Verify no-consent zero writes, stable IDs, identical rerun deduplication, changed-product insertion, customization final action, private schemas, and failure tolerance.

## Demo Case

Complete one unconsented selection and show zero rows. Grant consent, select recommendation 1, rerun, and show one row. Change to recommendation 2 and show a second selection event. Simulate repository failure and finish the customer plan normally.

## Known Limitations

PostgreSQL is covered with a fake connection rather than a live service. Analytics capture is intentionally best-effort and does not provide transactional guarantees across multiple remote writes.
