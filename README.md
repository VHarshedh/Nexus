# NEXUS — Autonomous Career Intelligence

NEXUS collects public job listings, validates them with Gemini, stores searchable vectors in PostgreSQL/pgvector, matches opportunities against user resumes, and delivers an agent-assisted briefing as avatar video or audio.

## Architecture

```mermaid
flowchart LR
  A[RemoteOK JSON] --> S[Scraper layer]
  B[HN Who is Hiring Markdown] --> S
  S --> C[Robots check + 2–5s jitter]
  C --> D[Canonical hash]
  D -->|new| E[Gemini extraction]
  D -->|duplicate| F[Refresh scraped_at]
  E --> G[Gemini embedding]
  G --> H[(PostgreSQL + pgvector)]
  H --> I[Resume matching]
  H --> J[Agent tools]
  I --> K[Next.js dashboard]
  J --> K
  K --> L[Briefing API]
  L --> M[Gemini script]
  M --> N{HeyGen available?}
  N -->|yes| O[HeyGen video]
  N -->|no / failure| P[Edge-TTS MP3]
  O --> K
  P --> K
```

## Repository map

```text
backend/app/
  main.py                  FastAPI app, lifespan, CORS, static uploads
  config.py                Pydantic Settings and environment configuration
  db.py                    async engine, sessions, table bootstrap
  cli.py                   scrape, db init/stats, semantic search commands
  api/auth.py              register, login, JWT current-user dependency
  api/resumes.py           PDF upload, resumes, matches, shortlist toggle
  api/briefings.py         queue/status/list briefing routes
  api/agent.py             authenticated agent-chat route
  api/schemas.py           Pydantic request/response DTOs
  models/                  User, JobListing, Resume, Match, BriefingJob ORM
  scrapers/                BaseScraper, RemoteOK, HN hiring, shared utilities
  pipeline/                orchestrator, Gemini extraction, embeddings/search
  agent/                   function-calling loop and user-scoped tools
  services/briefing.py     script generation, HeyGen polling, Edge-TTS fallback
backend/alembic/            async Alembic environment (revisions go in versions/)
backend/tests/              pytest unit, pipeline, agent, and integration tests
frontend/src/app/           Next.js App Router landing, login, dashboard pages
frontend/src/components/    protected route, match card, briefing stepper
frontend/src/lib/           Axios auth client, auth context, React Query, helpers
frontend/src/types/api.ts   TypeScript mirrors of backend DTOs
frontend/__tests__/         Vitest + React Testing Library tests
```

## Backend behavior

### Authentication and tenancy

`POST /api/auth/register` validates and bcrypt-hashes a password. `POST /api/auth/login` verifies credentials and returns a signed bearer JWT. `get_current_user` verifies signature, expiry, UUID subject, and the database user.

User-owned queries always include `Model.user_id == current_user.id`. ID routes combine resource ID and owner in the same database predicate, so guessed cross-tenant IDs return `404` and cannot be read or mutated. Agent tools receive the authenticated UUID and apply the same constraint. Global `JobListing` rows are intentionally shared; user-specific state lives in `UserListingMatch`.

### API reference

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Liveness check. |
| `POST /api/auth/register` | Create account and return token. |
| `POST /api/auth/login` | Authenticate and return token. |
| `POST /api/resume/upload` | Validate, parse, embed, and store a PDF resume. |
| `GET /api/resume/` | List only the caller’s resumes. |
| `POST /api/matches/compute` | Match latest embedded resume against listings. |
| `GET /api/matches/` | List only the caller’s matches. |
| `PATCH /api/matches/{match_id}/save` | Toggle one owned match’s shortlist flag. |
| `POST /api/briefings/generate` | Queue a briefing; returns `202` and `queued`. |
| `GET /api/briefings/{job_id}` | Poll one owned briefing. |
| `GET /api/briefings/` | List owned briefings. |
| `POST /api/agent/chat` | Run the authenticated Gemini career agent. |

Resume uploads are limited to 10 MiB, retain only a safe basename below `UPLOAD_DIR/<user-id>/resumes`, and run synchronous `pdfplumber` parsing in a worker thread. Axios injects the JWT and redirects to `/login` after a `401`.

### Data model

| Table | Ownership | Contents |
| --- | --- | --- |
| `users` | Account | Email, bcrypt hash, timestamps. |
| `job_listings` | Global | Source metadata, extracted fields, 768-dim embedding. |
| `resumes` | `user_id` | Raw text, path, resume embedding. |
| `user_listing_matches` | `user_id` | Listing link, score, justification, saved/status flags. |
| `briefing_jobs` | `user_id` | Progress, script, media URL, errors, timestamps. |

The `User` relationships cascade owned rows on account deletion. Job listings are shared ingestion data.

## Scraping and ingestion pipeline

`BaseScraper` manages Playwright lifecycle and realistic user-agent setup. `RemoteOKScraper` consumes structured JSON. `GitHubHiringScraper` is the registry name for the HN “Who is Hiring?” scraper; its free-form comments are sent through Gemini extraction. Both sources check robots.txt, use randomized polite delays, and return empty results on source failures.

`run_scrape_pipeline` catches source and per-listing failures, so a bad page, rate limit, invalid extraction, or embedding failure does not crash the orchestrator. `ListingExtractor` validates Gemini JSON with Pydantic, strips fences, retries repair prompts up to three times, caches successful extraction by text hash, and returns `None` after exhaustion.

### Deduplication

```text
SHA-256(canonical_url || lowercase(trim(title)) || lowercase(trim(company)))
```

Canonical URL processing lowercases scheme/host/path, removes fragments and trailing slashes, sorts query parameters, and drops `utm_*`, `ref`, and `source` tracking parameters. Meaningful query parameters remain because boards may use them as listing IDs. The indexed hash and unique source URL are both checked; a duplicate only refreshes `scraped_at` and skips Gemini/embedding costs.

## Agent tools

The Gemini function-calling loop can invoke `query_saved_listings(filter_remote?, max_deadline?)`, `get_top_skills_breakdown()`, and `get_deadline_alerts(days_ahead?)`. Tools execute async SQLAlchemy queries scoped to the supplied authenticated user, return JSON-safe structures, and have a ten-round loop cap. Tool errors are returned to Gemini as structured errors rather than escaping the request.

## Frontend

The Next.js App Router uses TypeScript, Tailwind, React Query, Axios, and `react-dropzone`. Landing and login pages are public. Dashboard pages provide discovery/matching, shortlist, resume/profile, agent chat, and briefing history. `AuthProvider` restores browser-only localStorage state; interactive pages and browser APIs use `'use client'`. Resume drop zones accept one PDF up to 10 MiB. Match cards update shortlist state through the protected PATCH route. The Briefing Hub polls active jobs every three seconds and renders video or audio media.

## Briefing lifecycle and delivery

`POST /api/briefings/generate` creates a job and returns immediately. Background processing uses an independent `get_session()` database session and reports `queued → generating_script → synthesizing_media → done` (or `failed`). The top three user matches seed the script. HeyGen is attempted when `HEYGEN_API_KEY` is set; missing credentials, exhausted credits, provider errors, or timeout trigger Edge-TTS MP3 generation under the user’s upload directory and `/uploads` static mount.

## Environment variables

Copy `backend/.env.example` to `backend/.env`; create `frontend/.env.local` for the public API URL.

| Variable | Default / requirement | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Required | `postgresql+asyncpg://nexus:nexus@localhost:5432/nexus`. |
| `GEMINI_API_KEY` | Empty | Extraction, embeddings, agent, and scripts. |
| `JWT_SECRET_KEY` | Replace sample | Long random JWT signing secret. |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm. |
| `JWT_EXPIRE_MINUTES` | `1440` | Token lifetime. |
| `HEYGEN_API_KEY` | Empty | Optional avatar video credential. |
| `UPLOAD_DIR` | `backend/uploads` | Resume/media storage root. |
| `MAX_RESUME_UPLOAD_BYTES` | `10485760` | PDF upload limit. |
| `CORS_ORIGINS` | Localhost origins | Allowed browser origins. |
| `SCRAPE_DELAY_MIN/MAX` | `2.0` / `5.0` | Polite scrape delay bounds. |
| `LOG_LEVEL` | `INFO` | Backend logging level. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API base URL. |
| `NEXUS_TEST_DATABASE_URL` | Unset | Disposable PostgreSQL+pgvector integration DB. |

## Local setup

Prerequisites: Python 3.11+, Node.js 20+, Docker, and a Gemini key for AI-backed flows.

```powershell
cd backend
docker compose up -d
Copy-Item .env.example .env
# Edit .env: set GEMINI_API_KEY and a strong JWT_SECRET_KEY
python -m venv ..\venv
..\venv\Scripts\python -m pip install -r requirements.txt
..\venv\Scripts\python -m app.cli db init
# Apply revisions when backend/alembic/versions contains migrations:
..\venv\Scripts\alembic upgrade head
..\venv\Scripts\python -m app.cli scrape --source remoteok
..\venv\Scripts\uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
# Optional .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000`; API health is `http://localhost:8000/health`. Stop local PostgreSQL with `docker compose down`.

## Testing and static checks

```powershell
# Backend unit/pipeline tests
cd backend
..\venv\Scripts\python -m pytest tests -q --basetemp .pytest-tmp

# Enable auth/tenant integration tests against a disposable database
$env:NEXUS_TEST_DATABASE_URL = 'postgresql+asyncpg://nexus:nexus@localhost:5432/nexus_test'
..\venv\Scripts\python -m pytest tests -q --basetemp .pytest-tmp

# Frontend tests, types, and lint
cd ..\frontend
npm test
npx tsc --noEmit
npm run lint
```

Without `NEXUS_TEST_DATABASE_URL`, integration tests skip while unit and pipeline tests still run. Never point it at production.

## Current limitations and next steps

- FastAPI `BackgroundTasks` is process-local; production should use ARQ/Celery + Redis, retries, dead-letter queues, and idempotency.
- Alembic’s async environment exists, but no revision is checked in yet; `db init` is the current bootstrap path.
- Add HNSW vector indexing and hybrid vector/full-text retrieval for large corpora.
- Local media storage needs object storage, retention, malware scanning, and backups in production.
- Add CI jobs for Ruff, mypy, ESLint, TypeScript, Vitest, pytest, dependency audit, and container scanning.

See [`IMPROVEMENTS.md`](IMPROVEMENTS.md) for the prioritized roadmap.
