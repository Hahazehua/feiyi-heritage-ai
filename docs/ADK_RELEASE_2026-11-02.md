# ADK release evidence — November 2, 2026

## Reproducible artifacts

Repository: `Hahazehua/feiyi-heritage-ai`, PR #7.
Application code: `0e84a4533781ad7858eea0b23367557cd1698ba8`.
Worker packaging fix and passing CI: `9c548b017fa3845d7c7a09d30de5e9bd665f96cf`.
The intervening commits change CI installation and legacy test paths, not web runtime code.

| Artifact | Cloud Build ID | Image digest |
| --- | --- | --- |
| Web | `11c29509-0655-4ba6-9625-a66d8a433964` | `sha256:54a0b8ec4ddb7784373678ae18258ba33db5a563663b129373e2b7f050e3dc3b` |
| ADK worker | `a88bd70e-cdbb-4c15-b5d9-850a71766d6f` | `sha256:7cfd4f5f13400afb7fb18b878cfe8b82f773c88f0505085b33fb7169ae4ce66a` |

Both builds succeeded using the explicit public-source allowlist and the existing
`haha-vector-build` identity. No working-tree credentials were uploaded.
The first worker revision failed startup because catalogue media was missing. The
corrected Dockerfile copies the media and validates the catalogue during the build.

## Automated verification

[Linux CI run 41466773777](https://github.com/Hahazehua/feiyi-heritage-ai/actions/runs/41466773777):

- Main suite: 436 passed, 2 skipped (optional ADK modules in the web environment).
- Isolated ADK/worker suite: 11 passed; actual Google ADK 2.13 scheduling is exercised.
- Synthetic campaign demo: deterministic correction of flagged claims, human review retained.
- TypeScript check and Vite production build passed.
- Changed Python files pass Ruff. Existing data-engineering lint/format findings remain.

The 17 web/proxy tests are included in the 436; they are not additional tests.
Mock provider tests do not establish live DeepSeek availability.

## Deployment controls

Private worker revision: `haha-adk-campaign-00002-gcg` in `us-central1`.
It runs with 1 CPU, 1 GiB memory, concurrency 2, min 0, max 1 and a 60-second timeout.
Only `haha-vector-runtime` has service-level `roles/run.invoker` on this worker.
The worker uses the existing `deepseek-api-key` version 1 through Secret Manager.
The browser never receives the key or a Google service token.

The web service is first released with zero traffic under the `adk-preview` tag.
Promotion requires a live draft, evidence inspection, acknowledgement-gated export,
and regression checks for the existing RAG and saved-inquiry flow.

Rollback: route `haha-studio` traffic to `haha-studio-00001-6fh`. The old public
Streamlit service is unchanged. Quotas and scale-to-zero settings limit usage but
do not guarantee a zero cloud or provider bill.

## Acceptance

Preview revision: `haha-studio-00002-xav`.

| Check | Observation |
| --- | --- |
| Real ADK request | `01a7a02f1737cb09`; `google-adk-workflow` 2.13.0; generation `deepseek`; 1,118 input / 203 output tokens; worker duration 4,469 ms |
| Workflow UI | Draft then Evidence check; 0 issues and 0 revisions for this request; human review remains required |
| Source | Met object [39646](https://www.metmuseum.org/art/collection/search/39646) opens as *Box with pommel scroll* |
| Human acknowledgement | Export disabled before acknowledgement and enabled after; click exercised, but the browser automation download event timed out, so downloaded-file contents are not independently verified |
| Existing RAG | `370a6f7213c041ca`; live `deepseek-flash`, Firestore retrieval, 4 sources; 560 input / 203 output tokens; retrieval 330 ms, generation 5,541 ms |
| Inquiry persistence | A consented demo inquiry for *Heritage-Inspired Plate with Lotus* reappeared after a full page reload and reopening Saved inquiries |
| Private worker | Anonymous `/healthz` returned HTTP 404 at the Cloud Run edge; authenticated web-to-worker generation succeeded; IAM policy grants only the runtime account the invoker role |

These are individual acceptance observations, not latency or quality benchmarks.
The test inquiry is labelled `ADK release acceptance — demo draft only, not sent.`
No message or commercial inquiry was sent. Test screenshots are kept locally under
`.local/adk-evidence/`; they are not a public credential or customer-data archive.
