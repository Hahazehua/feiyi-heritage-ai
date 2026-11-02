# English web release work log

User scope: English-first web UI, FastAPI, DeepSeek RAG with source citations,
durable inquiries, GCP deployment; meaningful engineering evidence for Google FDE internship.

Working checkout: feiyi-heritage-ai-publish, branch feat/english-rag-web.
Existing Streamlit service stays available. New service: haha-studio, same GCP project.
Frontend: React/TypeScript/Vite, built static and served by FastAPI (one origin).
Backend: reuse catalogue eligibility and hard filters, Firestore vector retrieval;
DeepSeek synthesis constrained to retrieved evidence; validated citation IDs/quotes.
Persistence: Firestore in cloud, SQLite locally. Anonymous browser-owned sessions;
this release does not claim authenticated identity or a merchant account system.
Explicit consent before storing inquiry notes. No outbound messages or orders.
Cost control: bounded LLM calls, output tokens, per-session/global daily limits.
Evidence: automated tests, retrieval evaluation, structured request traces (no prompts/keys),
deployment/runbook, customer discovery assumptions labelled as hypotheses.

Implemented and pushed: aa89692 on feat/english-rag-web.
Validated: frontend production build, ruff check/format, 428 Python tests,
12-case English retrieval smoke set; local browser inquiry save.
Cloud build a54f65f5-db19-4e6e-8f46-04439426cfb1: SUCCESS, checked Nov 1, 2026.
Image: us-central1-docker.pkg.dev/project-0bc866cb-bf3a-4247-b63/haha-vectors/studio:aa89692.
Deployed after explicit user confirmation: haha-studio revision haha-studio-00001-6fh,
100% traffic. URL: https://haha-studio-201693996482.us-central1.run.app/
Runtime data-write IAM is conditioned on the default Firestore database resource name.
Old haha-vector-demo remains available independently.
Live acceptance passed Nov 1, 2026: DeepSeek generated cited observations, museum link
opened and verified, inquiry saved and survived page reload, separate browser saw an
empty workspace. First request returned transient storage-unavailable after IAM change;
subsequent request and writes succeeded without code changes.
Live request e01a66544aca4546: Firestore retrieval 216 ms, generation 6710 ms,
total 6927 ms, 4 sources, deepseek-flash, 528 input / 116 output tokens.
These are single-request observations, not a latency benchmark or correctness estimate.
Target official US 2027 FDE listing confirmed by user. English demo script and honest
CV wording provided in WEB_DEMO_SCRIPT.md; customer discovery remains future work.
