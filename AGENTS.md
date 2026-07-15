# 飞颐礼遇 repository rules

## Goal and MVP boundary

- Build an explainable Streamlit MVP for 飞颐礼遇（HeritageLink AI）using 5–10 clearly labelled demo products from 飞颐铁画.
- The MVP covers product-data standardization, gift-needs intake, deterministic rule-based ranking, up to three recommendations, bilingual culture copy, and an executable customization inquiry.
- Use Python, Streamlit, pandas, and local CSV/JSON only. Do not add external model APIs, RAG, vector databases, authentication, payments, logistics, settlement, or a complex admin system unless explicitly requested.
- Prefer the smallest runnable and explainable solution. Keep data structures ready for multiple merchants and heritage categories.

## Important paths

- `app.py`: planned Streamlit entry point.
- `src/heritagelink/`: planned domain, data, recommendation, content, and inquiry modules.
- `data/demo/`: planned MVP demo data; every dataset and UI view must state `MVP 演示数据 / MVP demo data`.
- `tests/`: planned unit, integration, schema, and evaluation fixtures.
- `docs/`: product, architecture, schema, and implementation plans.
- `.forgejo/`, `CONTRIBUTING.md`, `SUBMISSIONS.md`, and `submissions.json`: competition-owned baseline or automation files.

## Repository safety

- Never delete, overwrite, or casually rename competition baseline files. In particular, do not manually edit `SUBMISSIONS.md`, `submissions.json`, or `.forgejo/workflows/`.
- Do not commit API keys, credentials, personal data, or other secrets. Use placeholders in documentation and future `.env.example` files.
- Do not run `git push`, create releases, or publish deployments unless the user explicitly asks.
- Preserve unrelated user changes and inspect `git status` before and after work.

## Python standards

- Target Python 3.11+, use UTF-8, four-space indentation, type hints on public functions, and small single-purpose modules.
- Keep business rules out of Streamlit widgets. Recommendation and inquiry generation must be deterministic, independently testable functions.
- Use stable snake_case identifiers and explicit schemas. Validate required columns, IDs, enums, JSON-list cells, numeric ranges, and foreign keys at load time.
- Use `Decimal` or integer fen for money calculations; do not rely on binary floating point for eligibility decisions.
- New behavior requires tests, including edge cases and deterministic tie-breaking (`score desc`, then `product_id asc`).

## Required checks after implementation changes

Run these once the Phase 1 tool configuration exists:

```text
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

For UI changes, also perform a local smoke test with `python -m streamlit run app.py --server.headless true` and verify the primary flow manually. If a command cannot run because the planned tooling is not installed yet, report that clearly; do not claim it passed.
