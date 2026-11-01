# GCP CV demonstration deployment

This release uses the complete application from `feiyi-heritage-ai-publish`
(base commit `462be63`), including Buyer, Artisan Studio, Growth Studio and
Story Studio, plus the Firestore catalogue vector search integration.
It replaces the earlier buyer-only deployment at:

https://haha-vector-demo-uv6mvvajyq-uc.a.run.app/

## Deploy

In an authenticated Google Cloud Shell, from this repository:

```bash
bash deploy/gcp/deploy.sh project-0bc866cb-bf3a-4247-b63
```

The script stages only application code, public demo CSVs and published images.
It does not upload `.env`, Streamlit secrets, local databases or credentials.
Deployment uses Cloud Run and Firestore in `us-central1`, with a read-only
runtime database identity. Cloud Run has a minimum of zero and maximum of one
instance, 1 CPU and 512 MiB memory. There are no paid model API calls by default.

## What visitors can try

- Choose Buyer or Artisan at the entry screen; switch between Chinese and English.
- Browse 54 catalogue entries, including 50 source-linked museum references and
  4 separately labelled partner works. Commercial details retain demo status.
- Search the 50 museum references using Firestore's native vector index.
  Embeddings are free local 256-dimensional lexical hashes, not a learned
  semantic model; synonyms and cross-language queries are not guaranteed.
- Use deterministic gift matching, bilingual content and inquiry export.
- Try artisan intake, provenance review, growth drafts and story workflows.

Without configured model credentials, optional AI and image generation features
use their existing fallback or disabled state. Demo drafts live in session memory;
this deployment does not offer permanent artisan storage. Export work before
closing the session.

## Costs and lifetime

Free quotas are not spending caps. Open Streamlit tabs keep WebSocket connections
alive and can consume Cloud Run compute. Close demonstration tabs when finished.
Budget alerts notify but do not stop spending. The current account is a free
trial; its console shows an expiry of 2027-01-30. This does not guarantee the CV
link will remain available after the trial. No account upgrade is performed by
the deployment script.

See [Google Cloud Free Program](https://docs.cloud.google.com/free/docs/free-cloud-features)
and [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
for current quotas and trial conditions.
