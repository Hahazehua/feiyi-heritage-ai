# English web service runbook

## Local

Install Python 3.11+ dependencies with `python -m pip install -e '.[gcp,web,dev]'`.
Build `web` using `npm ci && npm run build` (Node 22+).
Run `python -m uvicorn heritagelink.web.app:app --host 127.0.0.1 --port 8080`.
Open http://127.0.0.1:8080. Default storage and retrieval are SQLite under `.local`.
Keep keys outside Git. Set `LLM_ENABLED=true` and `DEEPSEEK_API_KEY` in the process environment
to enable the provider. Model defaults to `deepseek-flash`, configurable via `DEEPSEEK_MODEL`.

## Cloud release

Project: `project-0bc866cb-bf3a-4247-b63`, region: `us-central1`.
New service: `haha-studio`; original `haha-vector-demo` remains available.
The web Dockerfile reuses the previously verified application runtime image and adds the new
source and compiled UI. This deliberately reuses registry layers; retain that base image.
For deployment to a different project, first build the standard GCP Dockerfile and substitute
its image as the web runtime base. It is not a universal public base image.

Stage only allowed public files with `python deploy/gcp/stage_source.py <new-empty-directory>`.
Submit the staged directory using `deploy/gcp/cloudbuild.web.yaml` and `_IMAGE_URI`.
Use existing `haha-vector-build` build account and private build-source bucket. Do not upload
the complete working directory, inquiry database, `.env`, credentials, or browser artifacts.

Required runtime environment:

| Name | Value |
| --- | --- |
| VECTOR_BACKEND | firestore |
| WEB_STORE | firestore |
| GOOGLE_CLOUD_PROJECT | project-0bc866cb-bf3a-4247-b63 |
| FIRESTORE_DATABASE | (default) |
| VECTOR_COLLECTION | heritage_catalog_vectors |
| LLM_ENABLED | true |
| DEEPSEEK_MODEL | deepseek-flash |
| DEEPSEEK_API_KEY | Secret Manager reference `deepseek-api-key:1` |

Run as a dedicated service identity; it needs Firestore data read/write and access to this one
secret. Do not use Owner/Editor for runtime. Firestore server SDKs use IAM, not browser security
rules; application session checks enforce per-inquiry isolation. Database IAM does not provide
collection-level isolation within this service identity.

Deploy with port 8080, 512 MiB RAM, 1 vCPU, concurrency 4, minimum 0, maximum 1 instance,
request-based CPU and 60-second request timeout. The public web service is intentional; saved
inquiries require the unguessable browser cookie. Set billing alerts separately; max instances
and daily model quotas are useful bounds, not a guaranteed zero-cost bill.

## Verify / rollback

Check `/healthz`, load the catalogue, ask `Explain blue and white porcelain`, inspect the
`grounded_generation` state, source links and token counts. Save a clearly labelled QA draft;
reload and confirm it persists. A new cookie must not see the first cookie's inquiries.
Do not print the secret value or paste it in shell history. Provider failures are source-only,
so page availability alone is not sufficient proof of model integration.

View Cloud Run logs for request IDs and `advice` events. A 503 indicates unavailable storage
or an incompatible index; 429 indicates the daily demo budget. If an index is stale, run the
existing indexing script as an operator, never grant runtime index administration privileges.
If model output fails citation checks, source-only fallback is expected; inspect with synthetic
queries without logging user content. To stop model spend, set `LLM_ENABLED=false` and deploy
a new revision. To roll back, move traffic to a previously verified `haha-studio` revision.

## Costs and known limits

Free-tier allowances and trial credit are not a permanent hosting guarantee. Cloud Run,
Firestore, build time, registry storage, logs and external DeepSeek usage have separate billing.
The original trial showed an expiration of January 30, 2027; check current billing status before
depending on this URL in applications. No paid account upgrade is part of this release.
Registry storage was already close to the free allowance before this web release; reused base
layers reduce duplication, but verify actual storage after each build. Do not automatically
delete images needed by a running revision or rollback.

This is a CV-ready functional prototype, not a claim of audited production readiness. Future
work includes verified accounts, retention/deletion UX, stronger abuse prevention, held-out
human evaluation, incident alerting and measured customer discovery.
