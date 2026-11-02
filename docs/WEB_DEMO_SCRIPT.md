# Three-minute English engineering demonstration

## 0:00 — Problem and boundaries

“HAHA helps an overseas gift buyer understand unfamiliar Chinese craft and turn that
interest into a concrete inquiry brief. This is a functional prototype with labelled demo
commercial data. Museum reference objects are not inventory, and saving a draft does not
contact a merchant.”

## 0:30 — Evidence-based discovery

Enter `Explain blue and white porcelain`, a CNY 1,200 budget, quantity 10 and 30 days.
Submit once. Check the result status before describing it: only `grounded_generation`
demonstrates a successful live model call. Source-only fallback is not AI success.
Open a museum source and compare the displayed quotation with the supplied reference.

“The backend retrieves catalogue evidence, asks DeepSeek for structured observations,
and validates source IDs and exact quotations. Citation checks do not prove every inference.
The interface keeps that limitation and the supporting evidence visible.”

## 1:20 — Separate language generation from business rules

Show the demo concept prices and timing. Explain that server-side rules check eligibility,
budget, quantity, shipping and lead time. Lower the budget to CNY 1 to show a no-match case.
Restore the original brief before saving an inquiry.

## 1:50 — Complete a workflow

Save a clearly labelled demonstration inquiry with explicit consent. Open Saved inquiries,
refresh the page, reopen the saved list and export its JSON. Explain anonymous browser
ownership, the lack of cross-device account recovery and that the draft has not been sent.

## 2:20 — Explain delivery and tradeoffs

“React and FastAPI share one Cloud Run origin. Firestore holds a versioned lexical vector
index, inquiry drafts and atomic request budgets. Secret Manager provides the provider key.
The API records request IDs, timings and token usage without logging questions or notes.
Daily quotas constrain model spend; they do not guarantee a zero infrastructure bill.”

Show the request evidence panel. Distinguish measured latency and tokens from estimated cost.
Describe the next experiment: compare learned embeddings against the lexical baseline using
a held-out query set and human factuality review, then observe target buyers completing briefs.

## Verified engineering evidence

- Full Python regression suite: 428 passed on November 1, 2026.
- New backend contract tests: 9 passed, including source validation, storage failure,
  session isolation, idempotency and request budgets.
- Hand-authored English retrieval smoke set: 12/12 passed; not a general accuracy estimate.
- TypeScript and frontend production build passed.
- GCP build `a54f65f5-db19-4e6e-8f46-04439426cfb1`: SUCCESS.
- Published on Cloud Run: https://haha-studio-201693996482.us-central1.run.app/
- Revision: `haha-studio-00001-6fh`, 100% traffic.
- Live DeepSeek call returned citation-checked observations: 528 input / 116 output tokens,
  216 ms retrieval and 6,710 ms generation (one request, not a benchmark).
- Museum citation opened successfully; saved inquiry survived reload; a separate browser
  saw an empty workspace. See WEB_IMPLEMENTATION_STATUS.md for the acceptance record.

## CV wording supported by current evidence

Built and deployed an English-first heritage discovery prototype on GCP Cloud Run with
React, FastAPI, Firestore vector
retrieval and DeepSeek integration, adding source/quote validation, deterministic commercial
constraints and session-owned inquiry persistence; validated the repository with 428 Python
tests and a 12-case domain retrieval regression set.

Do not claim customer impact, semantic embedding quality, multi-agent orchestration or
production-scale reliability without corresponding evidence.
