# NEXUS — Autonomous Career Intelligence Agent

NEXUS is an end-to-end, production-grade autonomous career intelligence platform. It ingests live tech opportunities across public job boards using an ultra-hardened anti-detection stealth scraper engine, enforces structured schema extraction with Google Gemini, stores 768-dimensional vector embeddings in PostgreSQL/pgvector, matches opportunities against candidate resumes with hybrid retrieval (HNSW vector search + PostgreSQL GIN full-text search with Reciprocal Rank Fusion), incorporates personalized preference-boosted matching, provides a real-time **Cost & Token Intelligence Dashboard** tracking expenditure in Indian Rupees (₹), and delivers personalized career briefings as avatar video (D-ID / HeyGen) or high-fidelity audio (Edge-TTS).

---

## 1. System Architecture

The NEXUS architecture is built upon a highly concurrent, multi-tenant micro-monolith model. It seamlessly marries high-throughput asynchronous scraping with deterministically structured AI data pipelines and a responsive Next.js frontend. 

```mermaid
flowchart TD
  subgraph Ingestion["1. Multi-Source Ingestion & Anti-Detection Engine"]
    WWR[We Work Remotely - Playwright Stealth]
    HN[HN Who is Hiring - Algolia & Playwright]
    ROK[RemoteOK - Authenticated API]
    ARBN[Arbeitnow - Authenticated API]
    REMO[Remotive - Authenticated API]
    ROBOTS[Robots.txt Validator + 2-5s Jitter]
    WWR & HN & ROK & ARBN & REMO --> ROBOTS
  end

  subgraph DedupPipeline["2. Idempotent Deduplication & AI Pipeline"]
    ROBOTS --> CANON[Two-Tier Canonical Deduplication]
    CANON -->|Duplicate Found| TOUCH[Update scraped_at & Skip AI]
    CANON -->|New Unique Listing| GEM_EXT[Gemini 3.5 Flash Lite Structured Extraction]
    GEM_EXT --> GEM_EMB[Gemini Embedding 768-dim Vector]
  end

  subgraph Database["3. PostgreSQL + pgvector Storage Layer"]
    GEM_EMB --> DB_JOBS[(job_listings: HNSW Vector + GIN Full-Text Index)]
    TOUCH -.-> DB_JOBS
    DB_USERS[(users: Multi-Tenant + Preferences + Onboarded)]
    DB_RESUMES[(resumes: PDF Parsed + Vector Embedded)]
    DB_MATCHES[(user_listing_matches: Cosine Distance + Preference Boosts)]
    DB_COSTS[(token_usages: Multi-Tenant Token & INR Expenditure Ledger)]
  end

  subgraph CoreServices["4. Backend Services (FastAPI Async 3.11+)"]
    AUTH[Auth Service: JWT + 10-Min Password Reset]
    EMAIL[Email Service: Gmail SMTP aiosmtplib SSL]
    HYBRID[Hybrid Retrieval & Soft-Preference Boost Engine]
    AGENT[Career Agent: Gemini Tool-Calling Loop]
    BRIEF[Briefing Pipeline: D-ID / HeyGen / Edge-TTS]
    COST_TRACK[Cost Tracker: Real-Time Tokens & INR Spend]
    AUTH --> EMAIL
    DB_JOBS & DB_RESUMES --> HYBRID --> DB_MATCHES
    DB_MATCHES --> BRIEF
    DB_MATCHES & DB_JOBS --> AGENT
    AGENT & BRIEF & HYBRID --> COST_TRACK --> DB_COSTS
  end

  subgraph Frontend["5. Next.js App Router (TypeScript + Tailwind CSS)"]
    UI_LOGIN[Auth: Login, Register, Verify Email, Reset Password]
    UI_ONBOARD[Onboarding Wizard: 4-Step Role & Location Match Calibration]
    UI_DASH[Dashboard: Real-Time Matches & Opportunity Radar]
    UI_SHORT[Shortlist: Saved Roles & Status Pipeline]
    UI_RESUME[Resume Hub: PDF Dropzone & Parser Insights]
    UI_AGENT[AI Career Agent: Natural Language Conversational Interface]
    UI_BRIEF[Briefing Hub: Expressive Avatar Video & Audio Player]
    UI_COSTS[Cost Intelligence: Real-Time Tokens, INR/USD Spend & Ledger]
    UI_PROFILE[Account Settings: Preferences, Password Reset & Account Deletion]
  end

  CoreServices <--> Frontend
```

### 1.1 The Ingestion & Anti-Detection Engine
The ingest pipeline leverages **Async Playwright** to evaluate dynamic DOMs alongside standard REST API integrations. It enforces defensive scraping patterns:
- **Stealth Browsing:** Injecting realistic user-agents, mocking navigator properties, and bypassing simple bot-protection mechanisms.
- **Polite Crawling:** Parsing `robots.txt` automatically via `robotexclusionrulesparser` and embedding randomized jitter (2 to 5 seconds) to mimic human pacing.
- **Provider Redundancy:** By pulling from overlapping sources (HN, We Work Remotely, RemoteOK), the platform guarantees a dense and high-quality job feed.

### 1.2 The AI Structure Pipeline
Raw HTML and unstructured text from job descriptions are volatile. NEXUS passes the sanitized text payload into a **Gemini 3.5 Flash Lite** model armed with strict Pydantic v2 schemas (`ExtractedListing`). The system catches `ValidationError`s automatically, feeds the error context back to the LLM, and retries. This ensures complete database integrity where titles, salaries, locations, and skills strictly adhere to the expected format, rather than failing silently on bad LLM outputs.

### 1.3 PostgreSQL + pgvector Storage Layer
NEXUS uses a highly specialized database schema utilizing the `pgvector` extension. 
- **Vectors:** All AI-extracted job descriptions and uploaded user resumes are converted into 768-dimensional dense vectors using Google's `text-embedding-004` model.
- **HNSW Indexing:** Hierarchical Navigable Small World (HNSW) indices (`vector_cosine_ops`) are applied to the `embedding` columns, allowing sub-millisecond retrieval of vector candidates even as the table scales to hundreds of thousands of listings.
- **GIN Indexing:** Full-text indexing is applied concurrently via GIN indices to support lexical matching.

### 1.4 Backend Core Services (FastAPI Async)
The backend is fundamentally non-blocking and fully asynchronous, utilizing Python 3.11+.
- **Database I/O:** Powered by `asyncpg` and SQLAlchemy 2.0 `async_sessionmaker`.
- **Background Tasks:** Long-running processes (like audio generation, email dispatching, and asynchronous scraping) are delegated to FastAPI's `BackgroundTasks`, ensuring zero-latency HTTP responses.
- **Tool-Calling Architecture:** The backend features a stateful Career Agent that dynamically binds Python functions to the Gemini API using native JSON schema tool declarations, allowing the AI to query the live Postgres database on behalf of the user.

### 1.5 The Frontend Presentation Layer (Next.js)
Built entirely on the Next.js 16 App Router, the frontend maximizes performance by aggressively shifting rendering to the server (RSC).
- **Client vs Server:** State-heavy interactive elements (dropzones, conversational chat, video players) are demarcated with `"use client"`, while data-heavy layouts are statically or dynamically rendered on the server.
- **State Management:** Uses React Query (TanStack) for aggressive client-side caching, background refetching, and optimistic UI updates (e.g., when a user saves a job to their shortlist).
- **Aesthetic:** Clean, glass-morphic Tailwind CSS implementations emphasizing focus and data density.

---

## 2. In-Depth Deduplication Strategy

Re-running scrapers across high-frequency boards must never create duplicate records, pollute vector indexes, or burn LLM extraction quotas. NEXUS enforces a strict, two-tier idempotent deduplication architecture:

### A. The Canonical Composite Hash
Every listing is identified by a deterministic 64-character SHA-256 digest:

$$\mathrm{canonical\_hash} = \mathrm{SHA\text{-}256}\Big(\mathrm{normalised\_url} \mathbin{\Vert} \mathrm{lower}(\mathrm{trim}(\mathrm{title})) \mathbin{\Vert} \mathrm{lower}(\mathrm{trim}(\mathrm{company}))\Big)$$

* **Why these three fields?**
  1. `normalised_url`: Uniquely identifies a listing on a specific board.
  2. `title + company`: Catches identical positions re-posted under differing tracking campaigns, vanity URLs, or across multiple aggregated boards.

### B. URL Normalization Pipeline
Before hashing, URLs pass through a deterministic normalization algorithm in [`app/scrapers/utils.py`](backend/app/scrapers/utils.py):
1. **Scheme & Host Normalization**: Lowercased (`HTTPS://Jobs.Example.COM` $\rightarrow$ `https://jobs.example.com`).
2. **Path Normalization**: Strips trailing slashes, lowercases paths, and eliminates URL fragments (`#details`, `#apply`).
3. **Query Parameter Sanitization & Sorting**:
   - Strips ephemeral marketing and attribution parameters (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `ref`, `source`, `fbclid`, `gclid`).
   - Retains board-critical identifiers (e.g. `?id=12849` or `?job_id=99281`) and alphabetizes keys so parameter ordering does not affect the resulting hash.

### C. The Two-Tier Deduplication Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant S as Scraper Worker
    participant O as Orchestrator
    participant DB as PostgreSQL Database
    participant AI as Gemini 3.5 Flash Lite
    participant V as Vector Store

    S->>O: Yields RawListing(source_url, title?, company?, raw_text)
    O->>O: Compute initial canonical_hash
    O->>DB: Query: source_url == raw.source_url OR canonical_hash == hash
    alt Listing Already Exists (Dedup Hit & Change Detection)
        DB-->>O: Existing JobListing row returned
        O->>O: Compare stipend, deadline, location, remote policy against raw
        alt Content Changed (Salary / Deadline / Remote Policy / Reactivation)
            O->>DB: Update row, flag change_alert on user saved shortlists
            Note over O,DB: Preserves existing vector embeddings — skips redundant AI calls!
        else No Content Changes
            O->>DB: UPDATE job_listings SET scraped_at = now()
            Note over O,DB: Refreshes freshness timestamp with 0 LLM cost
        end
    else New Unique Listing
        O->>AI: Extract structured JSON (ExtractedListing schema)
        AI-->>O: Validated fields (title, company, skills, compensation, location)
        O->>O: Recompute canonical_hash with refined title & company
        O->>AI: Generate 768-dim text-embedding
        AI-->>O: Vector array
        O->>DB: INSERT INTO job_listings (...)
        O->>V: Index embedding via PostgreSQL HNSW
    end
```

---

## 3. Core Capabilities & Specialized Engines

### 3.1 First-Login Onboarding Wizard & Soft-Preference Boost Matching Engine
Upon account creation and email verification, users are greeted with an interactive 4-step wizard:
1. **Target Roles & Seniority**: Desired job titles (e.g., *Frontend Developer*, *AI Engineer*) and level (*Junior*, *Mid*, *Senior*, *Lead*).
2. **Location Preferences**: Country, state, and city for hybrid/onsite preferences, or remote selection.
3. **Minimum Stipend Requirement**: Expected base compensation or monthly stipend.
4. **Multi-Select Role Categories**: Broad industry clusters (*SDE*, *AI/ML*, *Data Science*, *DevOps*, etc.).

#### Non-Strict Soft-Boosting Algorithm
Rather than rigidly filtering out non-matching listings, NEXUS retrieves expanded candidate listings via pgvector cosine distance, and applies additive heuristic bonuses:
- **Location Bonus (+0.12)**: Boosts listings matching the user's country, state, city, or remote preference.
- **Stipend Boost (+0.08)**: Elevates listings meeting or exceeding the user's target stipend.
- **Category Overlap (+0.05)**: Grants bonuses to listings whose extracted skills intersect the selected role categories.

$$\text{Final Score} = \min\Big(0.99, \text{Cosine Similarity} + \text{Bonus}_{\text{Location}} + \text{Bonus}_{\text{Stipend}} + \text{Bonus}_{\text{Category}}\Big)$$

### 3.2 Hybrid Retrieval (HNSW Vector + GIN Full-Text Search with Reciprocal Rank Fusion)
To maximize match relevance, the system executes two concurrent queries and mathematically merges the results:
1. **HNSW Vector Search**: Semantic search understanding context. Captures cases where a "Python Engineer" is equivalent to a "Backend Developer."
2. **GIN Full-Text Index**: Lexical search utilizing `to_tsvector`. Captures exact keyword hits, which is critical for highly specific tooling (e.g., "Kubernetes", "Next.js", "Docker").
3. **Reciprocal Rank Fusion**: Ranks from both systems are merged. This eliminates the weaknesses of standalone vector search (hallucinations on exact matches) and standalone keyword search (failing on synonyms).

$$RRF\_Score(d) = \sum_{m \in \{\text{vector}, \text{text}\}} \frac{1}{k + \text{rank}_m(d)} \quad (k=60)$$

### 3.3 Cost & Token Intelligence Dashboard (`/costs`)
NEXUS provides transparency into LLM usage and API expenditures:
- **Real-Time Token Tracking**: Automatically captures prompt and candidate tokens from `response.usage_metadata` across Career Agent chats, resume embedding generation, match justifications, and video briefings.
- **INR & USD Costing**:
  - **Gemini 3.5 Flash Lite**: Input at **$0.15 / 1M tokens** (~₹12.98 / 1M), Output at **$1.25 / 1M tokens** (~₹108.13 / 1M).
  - **Gemini Embeddings**: **$0.025 / 1M tokens** (~₹2.16 / 1M).
  - **Exchange Rate**: 1 USD = **₹86.50**.
- **Interactive Controls & Visualization**:
  - Currency toggle (**₹ INR** default / **$ USD**).
  - 4 Key Metric Cards (Total Spend, Tokens Consumed, Today's Spend, This Week's Spend).
  - Visual per-feature progress bars & percentage distributions.
  - 14-day spending trend bar chart.
  - Live activity ledger recording every AI invocation with model, prompt/output tokens, and cost.

### 3.4 Multi-Provider Briefing Generation (D-ID $\rightarrow$ HeyGen $\rightarrow$ Edge-TTS)
1. **Gemini 3.5 Flash Lite**: Generates a 60-second broadcast script synthesizing the user's top matches.
2. **D-ID Video (Default if `DID_API_KEY` present)**: Generates expressive talking-head video with transparent background.
3. **HeyGen Video (Fallback if `HEYGEN_API_KEY` present)**: High-definition avatar synthesis.
4. **Edge-TTS Audio (Zero-Cost Local Fallback)**: Neural text-to-speech saved directly to disk and served via FastAPI static file mounting.

### 3.5 Single-File Resume Upload & Security Overrides
- **Dropzone Constraints:** Resume dropzones on both `/resume` and `/dashboard` enforce `multiple: false` and `maxFiles: 1`.
- **System Locks:** Locks the native operating system file explorer to single PDF selection.
- **Feedback Alerts:** Features `onDropRejected` toast guidance alerting users if multiple files are dragged at once.
- **Data Deletion Cascades:** A complete Account Deletion feature (`/profile`) securely wipes user records, preferences, tokens, resumes, briefings, and vector matches via strict Postgres ON DELETE CASCADE foreign key constraints.

---

## 4. Frontend Directory Architecture (Next.js 16 App Router)

The frontend is located in [`frontend/`](frontend/) and built with Next.js (App Router), TypeScript, and Tailwind CSS:

```text
frontend/src/
├── app/
│   ├── page.tsx                     # Landing page with interactive feature highlights
│   ├── login/page.tsx               # Sign in, register, password complexity checklist
│   ├── verify-email/page.tsx        # One-click email verification landing page
│   ├── reset-password/page.tsx      # Secure 10-minute password reset with live checklist
│   └── (dashboard)/
│       ├── layout.tsx               # Protected dashboard layout with persistent sidebar
│       ├── dashboard/page.tsx       # Live opportunities, match score radar, metrics
│       ├── shortlist/page.tsx       # Saved applications, status pipeline
│       ├── resume/page.tsx          # Single-file PDF dropzone & parser insights
│       ├── agent/page.tsx           # Interactive AI Career Intelligence Agent chat
│       ├── briefings/page.tsx       # Avatar video / audio briefing hub & player
│       ├── costs/page.tsx           # Cost & Token Intelligence Dashboard (INR/USD)
│       └── profile/page.tsx         # Account Settings: Preferences, Security, Deletion
├── components/
│   ├── onboarding-wizard.tsx        # 4-step first-login preference collection wizard
│   ├── protected-route.tsx          # Client-side session guard & redirector
│   ├── match-card.tsx               # Opportunity card with score pill & justification
│   └── video-player.tsx             # Responsive video/audio briefing media component
├── lib/
│   ├── api.ts                       # Axios client with JWT interceptor & 401 handling
│   ├── auth-context.tsx             # AuthProvider with user state & session management
│   ├── resume-file.ts               # File size and PDF MIME validation utilities
│   └── query-client.ts              # TanStack React Query configuration
└── types/
    └── api.ts                       # TypeScript interfaces mirroring backend Pydantic DTOs
```

---

## 5. System API Reference Blueprint

| Method & Path | Auth Required | Description |
| --- | :---: | --- |
| `GET /health` | No | System health and database connectivity check. |
| `POST /api/auth/register` | No | Creates unverified account, dispatches confirmation email via Gmail SMTP. |
| `POST /api/auth/login` | No | Authenticates verified user and issues JWT bearer token. |
| `POST /api/auth/verify-email` | No | Validates email token and marks account verified. |
| `POST /api/auth/resend-verification` | No | Resends verification link for unverified account. |
| `POST /api/auth/forgot-password` | No | Dispatches single-use 10-minute password reset link. |
| `POST /api/auth/reset-password` | No | Validates reset token & password signature; updates password. |
| `GET /api/auth/me` | Yes | Retrieves current user profile and onboarding preferences. |
| `PATCH /api/auth/preferences` | Yes | Updates target roles, locations, and stipend preferences. |
| `PUT /api/auth/password` | Yes | Changes account password after verifying current password. |
| `DELETE /api/auth/me` | Yes | Permanently deletes account and cascades across all data. |
| `GET /api/costs/summary` | Yes | Retrieves token consumption, feature breakdown, and INR/USD spend. |
| `POST /api/resume/upload` | Yes | Uploads single PDF resume, extracts text, computes vector embedding. |
| `GET /api/resume/` | Yes | Lists all resumes owned by the authenticated caller. |
| `POST /api/matches/compute` | Yes | Runs preference-boosted hybrid search against resume vector. |
| `GET /api/matches/` | Yes | Lists caller's matched opportunities with match scores. |
| `PATCH /api/matches/{match_id}/save` | Yes | Toggles shortlist status (`is_saved = true/false`). |
| `PATCH /api/matches/{match_id}/dismiss-alert` | Yes | Clears change or takedown alert on a saved match. |
| `POST /api/briefings/generate` | Yes | Queues an asynchronous video/audio briefing job (`202 Accepted`). |
| `GET /api/briefings/{job_id}` | Yes | Polls status of a specific briefing owned by the user. |
| `GET /api/briefings/` | Yes | Lists all briefings generated for the caller. |
| `POST /api/agent/chat` | Yes | Conversational query to the Gemini Autonomous Career Agent. |
| `GET /api/stats` | No | Platform metrics: total listings, active users, matches computed. |

---

## 6. Environment Configuration

### Backend (`backend/.env`)

```env
# PostgreSQL with asyncpg driver
DATABASE_URL=postgresql+asyncpg://nexus:nexus@localhost:5432/nexus

# Google Gemini API Key (https://aistudio.google.com/apikey)
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-3.5-flash-lite

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Email Confirmation & Password Reset (Gmail SMTP)
GMAIL_USER=nexus.verify.app@gmail.com
GMAIL_APP_PASSWORD=your-16-char-google-app-password
FRONTEND_URL=http://localhost:3000

# Avatar Video Synthesis (Optional)
DID_API_KEY=
DID_AVATAR_ID=public_mia_elegant@avt_TJ0Tq5
HEYGEN_API_KEY=
# (If unset, NEXUS automatically falls back to Edge-TTS neural audio)

# Limits & Scraping Politeness
MAX_RESUME_UPLOAD_BYTES=10485760
SCRAPE_DELAY_MIN=2.0
SCRAPE_DELAY_MAX=5.0
LOG_LEVEL=INFO
```

### Frontend (`frontend/.env.local`)

```env
# URL pointing to the FastAPI backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 7. Local Development & Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker Desktop (for local PostgreSQL with `pgvector`)

### Step 1: Database Setup
```powershell
cd backend
docker compose up -d
```

### Step 2: Backend Setup
```powershell
# Create and activate Python virtual environment
python -m venv ..\venv
..\venv\Scripts\Activate.ps1

# Install dependencies and Playwright headless browsers
pip install -r requirements.txt
playwright install chromium

# Apply database migrations
alembic upgrade head

# Ingest initial job listings from scrapers
python -m app.cli scrape --source remoteok --skip-embeddings

# Start FastAPI backend server
uvicorn app.main:app --reload --port 8000
```

### Step 3: Frontend Setup
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```

Visit **`http://localhost:3000`** in your browser. Interactive Swagger API documentation is available at **`http://localhost:8000/docs`**.

---

## 8. Verification & Quality Assurance

### Pre-Deployment Compilation & Syntax Check
Verify that the Python backend compiles cleanly without errors:
```powershell
cd backend
python -m compileall app
python -c "import app.main; print('Ready for deployment!')"
```

### Frontend Typechecking & Production Build
```powershell
cd frontend
npx tsc --noEmit
npm run build
```

### Automated Benchmark Suite (`evals`)
Evaluates LLM structured extraction against a hand-labelled benchmark dataset ([`backend/evals/dataset.json`](backend/evals/dataset.json)):
```powershell
cd backend
..\venv\Scripts\python -m evals.eval_extraction
```

**Benchmark Results:**
* **Job Title Accuracy**: `88.0%` [PASS]
* **Company Name Accuracy**: `90.0%` [PASS]
* **Remote Classification Accuracy**: `90.0%` [PASS]
* **Experience Level Mapping Accuracy**: `80.0%` [PASS]
* **Skills Token Overlap (Mean F1-Score)**: `87.0%` [PASS]
* **Overall Composite Benchmark Score**: **`87.76%`** [PASS] (Threshold: 80%)

---

## 9. Production Cloud Deployment (Vercel + Render + Supabase)

1. **Database (Supabase / Neon Postgres)**:
   - Create a project on [Supabase](https://supabase.com) and enable the `vector` extension.
   - Set the connection string as `DATABASE_URL` in your backend environment.

2. **Backend (Render Web Service)**:
   - Deploy `backend/` to [Render](https://render.com).
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Configure environment variables (`DATABASE_URL`, `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `FRONTEND_URL`).

3. **Frontend (Vercel)**:
   - Deploy `frontend/` to [Vercel](https://vercel.com).
   - Configure `NEXT_PUBLIC_API_URL=https://your-nexus-backend.onrender.com`.
   - *Note:* CORS is pre-configured in `app/main.py` to automatically permit requests originating from `https://*.vercel.app`.

---

## 10. Troubleshooting & FAQ

**Q: I'm getting `asyncpg.exceptions.InvalidPasswordError` when running tests.**
**A:** Ensure your `DATABASE_URL` inside your `.env` perfectly matches the credentials established in your `docker-compose.yml`. Wait for PostgreSQL to fully initialize before running Alembic migrations.

**Q: Vector embeddings aren't returning matches?**
**A:** If you skipped embeddings during scraping (`--skip-embeddings`), your job rows have `null` vector embeddings. Re-run the scraper without the skip flag, or ensure you have a valid Resume uploaded in the system to create a candidate vector.

**Q: The AI video briefing hangs indefinitely.**
**A:** Background polling requires `httpx`. Verify that your machine has internet access and your `DID_API_KEY` or `HEYGEN_API_KEY` are well-funded and active. If they are disabled or empty, the system automatically defaults to `Edge-TTS` audio, which creates an `.mp3` artifact in seconds locally.

**Q: Character encoding errors on Windows terminal.**
**A:** The `cost_tracker.py` might try to print the Indian Rupee symbol `₹`. If you face `charmap codec can't encode character` in CMD, either use PowerShell or Windows Terminal, which have full UTF-8 support by default.
