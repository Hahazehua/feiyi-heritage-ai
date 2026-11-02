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
Current deployed service remains haha-vector-demo revision 00004-wc5.
New haha-studio service not yet published. Awaiting specific browser-action confirmation
for default Firestore write access and new public service. Live DeepSeek and persistence
acceptance remain pending. Target official US 2027 FDE listing confirmed by user.
