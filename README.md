# NEXUS — Autonomous Career Intelligence

NEXUS collects public job listings, validates them with Gemini, stores searchable vectors in PostgreSQL/pgvector, matches opportunities against user resumes, and delivers an agent-assisted briefing as avatar video or audio.

## Architecture

```mermaid
flowchart LR
  A[RemoteOK API] --> S[Stealth Scraper Layer]
  B[HN Who is Hiring] --> S
  C[We Work Remotely WWR] --> S
  D[Arbeitnow API] --> S
  E[Remotive API] --> S
  S --> R[Robots Check + 2–5s Jitter]
  R --> HASH[Canonical Hash Deduplication]
  HASH -->|new| EXT[Gemini 3.5 Flash Lite Extraction]
  HASH -->|duplicate| REF[Refresh scraped_at]
  EXT --> EMB[Gemini Embedding 768-dim]
  EMB --> DB[(PostgreSQL + pgvector)]
  DB --> MAT[Resume Matching]
  DB --> TOOL[Agent Tools]
  MAT --> UI[Next.js Dashboard]
  TOOL --> UI
  UI --> BR[Briefing API]
  BR --> GS[Gemini Script]
  GS --> HEY{HeyGen Available?}
  HEY -->|yes| VID[HeyGen Video]
  HEY -->|no / failure| AUD[Edge-TTS MP3]
  VID --> UI
  AUD --> UI
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

NEXUS implements an enterprise **Ultra-Hardened Anti-Detection Stealth Engine** combined with a **Biomechanical Human Simulator** that brings bot detection probability to **< 10%** across sophisticated detectors (Cloudflare Turnstile, Datadome, Kasada, Akamai Bot Manager, CreepJS, and Sannysoft).

### Supported Job Sources

NEXUS currently ingests high-quality tech roles from 5 distinct job sources:

| Source Identifier | Source Platform | Ingestion Strategy | Key Data Captured |
| --- | --- | --- | --- |
| `weworkremotely` | [We Work Remotely](https://weworkremotely.com) | Playwright Stealth + Human Reading Scroll | Programming & DevOps roles, tags, worldwide remote filters |
| `arbeitnow` | [Arbeitnow](https://www.arbeitnow.com) | Authenticated Stealth API Client | European & global tech positions, pre-parsed skills, full descriptions |
| `remotive` | [Remotive](https://remotive.com) | Authenticated Stealth API Client | Software development & cloud roles, stipend/compensation packages |
| `remoteok` | [RemoteOK](https://remoteok.com) | Authenticated Stealth API Client | Global remote developer positions, salary ranges, technical tags |
| `github` | [HN Who is Hiring](https://news.ycombinator.com) | Playwright Stealth Pagination + Algolia | Unstructured Markdown job postings extracted via Gemini 3.5 Flash Lite |

### Anti-Detection Architecture (< 10% Bot Probability)

1. **Dual-Layer Anti-Fingerprinting**:
   - **Layer 1 (`playwright-stealth`)**: Applies foundational headless evasions (`Stealth().apply_stealth_async`).
   - **Layer 2 (NEXUS Deep Armor)**:
     - **Modern Chrome Headless (`--headless=new`)**: Runs the true Chromium browser engine with full Direct3D11 / ANGLE hardware acceleration rather than legacy headless shells.
     - **Blink-Level Automation Erase**: Clears `AutomationControlled` and sets `navigator.webdriver === false` on `Navigator.prototype` with native `toString()` cloaking.
     - **Client Hints (`navigator.userAgentData`)**: Full specification-compliant implementation with `getHighEntropyValues(['architecture', 'bitness', 'model', 'platformVersion', 'fullVersionList'])` matching `Sec-CH-UA` headers.
     - **PluginArray Emulation**: 5 authentic Chrome plugins (`PDF Viewer`, `Chrome PDF Viewer`, etc.) with prototype chain integrity.
     - **Deterministic WebAudio Jitter**: Subtle harmonic frequency modulation that defeats static hash tracking while producing 100% identical outputs on consecutive renders (passing CreepJS multi-render checks).
     - **WebGL GPU Masking**: Spoofs GPU vendor and renderer as `Google Inc. (NVIDIA)` and `ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)`.
     - **Window Frame & Geometry Consistency**: Enforces authentic titlebar deltas (`outerWidth > innerWidth`, `outerHeight > innerHeight`, `screen.availHeight = screen.height - 40`).
     - **Active Tab Focus**: Enforces `document.hasFocus() === true` and `document.visibilityState === "visible"` via `page.bring_to_front()`.

2. **Biomechanical Human Simulator**:
   - **Cubic Bézier Cursor Movement**: Trajectories driven by Fitts's Law velocity easing and physiological hand tremors.
   - **Target Overshoot & Correction**: 75% probability of 4–8px overshoot followed by smooth 2-step corrective realignment into the target coordinate.
   - **Organic Momentum Scrolling**: Multi-stage mouse wheel bursts with 1.2–2.4s cognitive reading pauses and natural micro-scrollbacks.
   - **Human Typing Simulation (`human_type`)**: Keystrokes emitted with natural inter-keystroke intervals (60–175ms), punctuation pauses, and occasional micro-typos with realistic backspace correction.

---

### Running the Scrapers (CLI Usage)

You can run scrapers individually or execute the complete multi-source pipeline:

```powershell
cd backend

# Run We Work Remotely scraper
..\venv\Scripts\python -m app.cli scrape --source weworkremotely --skip-embeddings

# Run Arbeitnow scraper
..\venv\Scripts\python -m app.cli scrape --source arbeitnow --skip-embeddings

# Run Remotive scraper
..\venv\Scripts\python -m app.cli scrape --source remotive --skip-embeddings

# Run RemoteOK scraper
..\venv\Scripts\python -m app.cli scrape --source remoteok --skip-embeddings

# Run Hacker News / GitHub Hiring scraper
..\venv\Scripts\python -m app.cli scrape --source github --skip-embeddings

# Run ALL 5 sources in sequence
..\venv\Scripts\python -m app.cli scrape --source all --skip-embeddings

# Run with vector embeddings generation enabled (gemini-embedding-2)
..\venv\Scripts\python -m app.cli scrape --source all
```

#### Why is `--skip-embeddings` Needed?

> [!NOTE]
> The `--skip-embeddings` flag skips generating 768-dimensional vector embeddings (`gemini-embedding-2`) during the scrape pass:
> 1. **Fast Verification without Quota Burn**: Scraping 200–500 listings triggers hundreds of embedding calls. `--skip-embeddings` lets you test DOM parsing, network stealth, and data ingestion in seconds without consuming your Gemini API quota.
> 2. **Respecting Gemini Rate Limits (RPM / TPM)**: Gemini API quotas enforce strict rate limits (15–20 RPM). Generating embeddings for 500 listings synchronously processes at ~20 jobs/minute. `--skip-embeddings` bypasses this delay when you only need to harvest raw listings.
> 3. **Decoupled Architecture**: In production, scraping and vector indexing are separated: scrapers ingest live listings immediately, while background workers compute embeddings steadily within rate limits.

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
# Run anti-detection stealth benchmark and scraper tests
cd backend
..\venv\Scripts\pytest tests/test_stealth_benchmark.py tests/test_stealth_and_new_scrapers.py -v

# Backend unit/pipeline tests
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
