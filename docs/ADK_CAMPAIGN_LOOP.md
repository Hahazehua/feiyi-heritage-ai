# Google ADK campaign drafting and review

The optional English Draft Studio uses Google ADK 2.13.0 `Workflow` graph nodes,
`Runner`, events and invocation-local in-memory sessions. The graph drafts once,
checks with the existing deterministic Guardian, and revises at most twice.
Every revision is checked; empty output and exhausted failed checks never permit export.
The public cultural RAG route remains separate.

## Architecture

React → same-origin FastAPI `/api/campaign` → private Cloud Run worker `/campaign`
→ ADK Workflow → one bounded DeepSeek call → rule review / deterministic revisions.

The public API validates browser session and origin, validates the selected product,
and consumes persistent Firestore quotas (3 per browser / 20 globally per UTC day).
It obtains a Google-signed ID token with the worker URL as audience. The worker must
remain IAM-protected; only the existing web runtime account receives service-level
`roles/run.invoker`. It reconstructs facts from the canonical catalogue and rejects
caller-provided verification flags. Do not disable the worker's Cloud Run IAM check.

Runtime constraints are deliberately separate: ADK requires Starlette >=1.3.1 while
the legacy web package pins Starlette <1. The worker image installs only
`requirements-adk-runtime.txt`; do not install the project extras into this image.

The worker shares the existing runtime account and its Secret Manager permission.
This minimizes IAM changes but retains that account's existing database access;
a dedicated least-privilege worker identity is a future hardening option.

## Behavior and limits

- One DeepSeek request, 25-second provider timeout, no retries, 1,400 output-token cap.
- Market assessment and strategy use deterministic rules; only drafting calls the model.
- Rule review and revision are not independent LLM reviewers and do not prove semantic truth.
- A failed or malformed model response produces an explicitly labelled template fallback.
- The frontend shows stage history, issue counts, revisions, facts, sources and token usage.
- A user acknowledgement enables local text export only. Nothing is posted or sent.
- Campaign drafts are not persisted. Existing inquiry persistence is unaffected.
- In-memory ADK sessions do not survive restarts or implement resumable human approval.
- Anonymous browser quotas are not verified-user identities; the global quota bounds abuse.
- Sources are catalogue references, not evidence that demo products are available for purchase.

## Local checks

```powershell
python -m venv .local/adk-venv
.local/adk-venv/Scripts/python -m pip install -r requirements-adk.txt
$env:PYTHONPATH = 'src'
.local/adk-venv/Scripts/python -m pytest tests/test_adk_campaign.py tests/test_adk_worker.py
.local/adk-venv/Scripts/python scripts/demo_adk_campaign.py
```

No API key is required for tests. Tests execute real ADK scheduling, including revision
exhaustion, empty drafts, request scope, concurrent isolation, actual Guardian removal,
fallback labelling and rejection of forged facts. The synthetic demo starts with eight
flagged issues, revises once, and ends with human review required.

Web checks run in the original environment: `python -m pytest tests/test_web.py
 tests/test_campaign_proxy.py`; the UI is built with `npm ci` / `npm run build` in `web`.
`.github/workflows/web-adk.yml` runs separate web and ADK jobs without deployment secrets.

## Deployment

Use the existing explicit source allowlist (`deploy/gcp/stage_source.py`). Build with
`cloudbuild.adk.yaml` and `cloudbuild.web.yaml`. Deploy `haha-adk-campaign` privately,
then grant its service-level invoker role to `haha-vector-runtime`. Set `ADK_WORKER_URL`
on `haha-studio` to the canonical worker URL and update the web image.

Worker: us-central1, min instances 0, max instances 1, concurrency 2, 1 CPU, 1 GiB memory,
60-second request timeout; `LLM_ENABLED=true`, `DEEPSEEK_MODEL=deepseek-flash`, and
`DEEPSEEK_API_KEY` from `deepseek-api-key:1`. Reuse request-based CPU allocation.
Cloud Run, build minutes, image storage and DeepSeek can incur charges beyond allowances;
min=0 and request quotas are not a billing cap.

Accept only after the private worker rejects unauthenticated calls, live UI reports
DeepSeek generation with token usage and stage history, and human acknowledgement gates
export. Recheck the existing RAG/citation and inquiry refresh flows. For rollback,
route web traffic to `haha-studio-00001-6fh`; the unused worker scales to zero.

## Validation status

Linux CI at `9c548b0` passed: 436 main-suite tests, 2 optional skips, 11 isolated
ADK/worker tests, the synthetic workflow demo and the frontend production build.
The web/proxy tests account for 17 of the main-suite passes. Streamlit AppTest paths
are now resolved from the repository location, independently of the test runner.
An earlier Windows full-suite attempt had Streamlit timeouts; the complete Linux
run supplies the release verification.
Whole-repository Ruff has 175 pre-existing errors and 20 formatting issues in
`haha-data-engineering`; those unrelated files are unchanged. See release evidence
for final worker tests, CI and deployment acceptance results:
[November 2 release record](ADK_RELEASE_2026-11-02.md).

Official references: [Google ADK](https://github.com/google/adk-python),
[Workflow graphs](https://adk.dev/graphs/), [graph routing](https://adk.dev/graphs/routes/).
