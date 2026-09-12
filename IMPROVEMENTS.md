# NEXUS Improvement Roadmap

This roadmap is ordered by production risk and leverage. Each item should be delivered with observability, a rollback plan, and regression coverage.

## P0 — Reliability and security foundations

1. Move briefing and scraping work from FastAPI `BackgroundTasks` to ARQ or Celery backed by Redis. Persist task IDs, use exponential retry with dead-letter handling, make each task idempotent, and expose worker health/queue depth. The current background implementation owns its database session correctly, but process restarts can still abandon in-memory work.
2. Add an Alembic baseline revision and enforce `alembic upgrade head` during deployment. Use a separate, least-privileged migration role and prohibit application startup from applying schema changes in production.
3. Add structured JSON logs, request IDs, Sentry/error reporting, OpenTelemetry traces, and metrics for scrape failures, Gemini retries, queue lag, per-tenant authorization denials, and briefing completion/fallback rates.
4. Expand authorization tests whenever a user-owned route is introduced. Enforce a repository rule: every query on `Resume`, `UserListingMatch`, or `BriefingJob` must include its authenticated user constraint. Consider PostgreSQL row-level security as defense in depth.

## P1 — Scale search and ingestion

1. Create an HNSW index for `job_listings.embedding` using cosine ops (`vector_cosine_ops`) after representative load testing. Tune `m` and `ef_construction`, and set query-time `hnsw.ef_search` based on latency/recall targets.
2. Implement hybrid retrieval: normalize and combine pgvector cosine similarity with PostgreSQL full-text rank (GIN-indexed `tsvector` over title, company, skills, and description). Use reciprocal-rank fusion initially; add query analytics before training weights.
3. Make ingestion durable: persist fetch/extraction states, source response metadata, canonical URL redirects, and retry schedules. Add source-specific rate-limit budgets and circuit breakers. Keep current randomized 2–5 second navigation jitter and robots checks.
4. Batch Gemini embeddings with bounded concurrency and token-aware batches. Cache by content hash, record embedding model/version, and re-embed through a queued migration when the model changes.

## P2 — Reduce LLM latency and cost

1. Use Gemini context caching for stable extraction instructions, tool declarations, and briefing-system context. Track cache-hit ratio, token savings, output-validation failure rate, and p95 model latency.
2. Use a strict JSON response mode/schema where supported; retain Pydantic validation and repair retries as the final safety boundary. Classify permanent validation failures separately from transient provider failures.
3. Add provider budgets per environment and tenant, token caps, request timeouts, and graceful user-facing fallbacks for match justifications and briefings.

## P3 — Delivery engineering and quality

1. Add GitHub Actions with independent jobs for:
   - backend: `ruff check`, `ruff format --check`, `mypy`, and `pytest` against a pgvector service;
   - frontend: `eslint .`, `tsc --noEmit`, `vitest run`, and `next build`;
   - security: dependency audit, secret scanning, and container image scanning.
2. Require branch protection, review, passing checks, immutable artifact promotion, and environment-scoped secrets. Deploy migrations as an explicit pre-deploy job.
3. Add Playwright browser E2E coverage for registration, resume upload, cross-tenant tampering, briefing polling, and the Edge-TTS fallback. Run nightly source-contract tests against supported job boards.
4. Establish retention/deletion policies for resumes, generated media, logs, embeddings, and backups. Add account deletion, export, and audit-event workflows before handling production user data.
