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

Pending: implementation, tests, browser QA, deployment, live model + persistence checks.
Target job link requested; provisional official US 2027 FDE listing found.
