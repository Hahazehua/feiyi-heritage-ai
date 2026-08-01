---
name: analyze-gift-choice-signals
description: Produce privacy-safe aggregate HeritageLink gift recommendation and selection metrics from consented or clearly marked synthetic SQLite events. Use when reviewers or product analysts need funnel, product, rank, recipient, scene, budget, customization, destination, or conversation-turn signals with minimum-sample protection and no person-level output.
---

# Analyze Gift Choice Signals

## Name

Use `analyze-gift-choice-signals` / 匿名礼品选择信号分析.

## Purpose

Read authorized anonymous events and report aggregate choice signals. Do not change online weights, reorder products, profile individuals, or claim causal effects.

## Trigger

Run when a reviewer or authorized analyst requests an aggregate report from a local analytics database, optionally filtered by date, recipient, scene, budget bucket, or product.

## Inputs

Accept a SQLite path plus optional `date_from`, `date_to`, `recipient`, `scene`, `budget_bucket`, `product_id`, `minimum_sample_size`, requested metrics, and output format. Default `minimum_sample_size` to 5. See [references/analytics-schema.md](references/analytics-schema.md).

## Outputs

Return overall funnel, product metrics, rank metrics, optional segment metrics, conversation metrics, data-quality counts, cautious observations, sample warning, limitations, generated time, data window, data sources, and a synthetic-data notice. See [references/metric-definitions.md](references/metric-definitions.md).

## Processing Steps

1. Verify that the local database exists and contains the expected aggregate tables.
2. Load only structured anonymous fields.
3. Apply session-level filters.
4. Aggregate recommendation, selection, rank, segment, budget, and turn counts.
5. Suppress rates whose denominator is below the minimum sample size.
6. Mark any `synthetic_demo` input prominently.
7. Output table or JSON without event-level rows or database credentials.

## Business Rules

- Describe correlation only; never imply causation.
- Do not use “best”, “favorite”, or stable preference language for small samples.
- Return empty aggregates rather than fabricated examples for zero rows.
- Do not automatically update recommendation weights or ordering.
- Keep real consented and synthetic sources distinguishable.

## Privacy Boundary

Expose aggregate counts, rates, averages, product IDs, and coarse segments only. Never print anonymous session IDs, event IDs, raw requirements, individual selections, full chat, PII, database URLs, or credentials.

## Failure and Fallback

Return exit code 2 and a concise local message for a missing/invalid database. Return a valid empty report for an initialized empty database. Never affect the customer Streamlit application.

## Code Entry Points

- Analysis service: `src/heritagelink/choice_analysis.py`
- CLI: `skills/analyze-gift-choice-signals/scripts/analyze_choices.py`
- Synthetic generator: `scripts/generate_synthetic_choice_data.py`
- SQLite reader/schema: `src/heritagelink/repositories/sqlite_choice_repository.py`

## How to Run

```powershell
python scripts/generate_synthetic_choice_data.py --sessions 50
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --format table
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --scene anniversary --format json
```

## Evaluation

Run:

```powershell
python -m pytest tests/test_choice_analysis.py tests/test_choice_analysis_cli.py
```

Verify empty data, exact recommendation/selection/rank counts, segments, budget buckets, turn averages, nonselection rate, brief rate, deduplication, synthetic labeling, sample protection, CLI formats, missing database handling, and absence of person-level output.

## Demo Case

Generate 50 deterministic synthetic sessions, run table output, then filter the JSON output to `anniversary`. Point out the synthetic disclaimer, rank rates, scene distribution, average turns, and suppressed small-sample percentages.

## Known Limitations

The executable reader currently targets local SQLite. PostgreSQL stores compatible records, but remote aggregate queries are not implemented. Turn metrics use the persisted total conversation-turn count as the available approximation for turns before recommendation and selection.
