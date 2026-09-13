# NEXUS — Autonomous Career Intelligence Agent

NEXUS is an end-to-end, production-grade autonomous career intelligence platform. It ingests live tech opportunities across public job boards using an ultra-hardened anti-detection stealth scraper engine, enforces structured schema extraction with Google Gemini, stores 768-dimensional vector embeddings in PostgreSQL/pgvector, matches opportunities against candidate resumes with hybrid retrieval (HNSW vector search + PostgreSQL GIN full-text search with Reciprocal Rank Fusion), and delivers personalized career briefings as avatar video (D-ID / HeyGen) or high-fidelity audio (Edge-TTS).

---

## 1. System Architecture

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
    DB_USERS[(users: Multi-Tenant + is_verified)]
    DB_RESUMES[(resumes: PDF Parsed + Vector Embedded)]
    DB_MATCHES[(user_listing_matches: Cosine Distance + RRF)]
  end

  subgraph CoreServices["4. Backend Services (FastAPI Async 3.11+)"]
    AUTH[Auth Service: JWT + 10-Min Password Reset]
    EMAIL[Email Service: Gmail SMTP aiosmtplib SSL]
    HYBRID[Hybrid Retrieval Engine: RRF pgvector + GIN]
    AGENT[Career Agent: Gemini Tool-Calling Loop]
    BRIEF[Briefing Pipeline: D-ID / HeyGen / Edge-TTS]
    AUTH --> EMAIL
    DB_JOBS & DB_RESUMES --> HYBRID --> DB_MATCHES
    DB_MATCHES --> BRIEF
    DB_MATCHES & DB_JOBS --> AGENT
  end

  subgraph Frontend["5. Next.js App Router (TypeScript + Tailwind CSS)"]
    UI_LOGIN[Auth: Login, Register, Verify Email, Reset Password]
    UI_DASH[Dashboard: Real-Time Matches & Opportunity Radar]
    UI_SHORT[Shortlist: Saved Roles & Status Management]
    UI_RESUME[Resume Hub: PDF Dropzone & Parser Insights]
    UI_AGENT[AI Career Agent: Natural Language Conversational Interface]
    UI_BRIEF[Briefing Hub: Expressive Avatar Video & Audio Player]
  end

  CoreServices <--> Frontend
```

---

## 2. In-Depth Deduplication Strategy

Re-running scrapers across high-frequency boards must never create duplicate records, pollute vector indexes, or burn LLM extraction quotas. NEXUS enforces a strict, two-tier idempotent deduplication architecture:

### A. The Canonical Composite Hash
Every listing is identified by a deterministic 64-character SHA-256 digest:

$$\text{canonical\_hash} = \text{SHA-256}\Big(\text{normalised\_url} \mathbin{\Vert} \text{lower}(\text{trim}(\text{title})) \mathbin{\Vert} \text{lower}(\text{trim}(\text{company}))\Big)$$

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
            O->>DB: UPDATE job_listings SET stipend/deadline/remote, is_active = True
            O->>DB: Flag saved UserListingMatches with change_alert
            O->>AI: Dispatch change alert email via Gmail SMTP
        else No Content Changes
            O->>DB: UPDATE job_listings SET scraped_at = NOW()
        end
        Note over O,AI: Skips costly LLM extraction & vector embeddings!
        O-->>S: Record refreshed (Cost: $0.00, Time: < 2ms)
    else Listing is New
        DB-->>O: None
        opt Unstructured Listing (e.g. HN / GitHub)
            O->>AI: Extract structured JSON (title, company, skills, remote_ok)
            AI-->>O: ExtractedListing DTO
            O->>O: Recompute canonical_hash with LLM extracted title & company
        end
        O->>V: Generate 768-dim vector embedding
        V-->>O: Float vector
        O->>DB: INSERT INTO job_listings (canonical_hash, source_url, embedding, ...)
        O-->>S: New listing indexed
    end
```

### D. Database-Level Guarantees
- `job_listings.source_url`: Defined with a `UNIQUE` constraint at the database schema layer.
- `job_listings.canonical_hash`: Indexed with a standard PostgreSQL B-tree index (`ix_job_listings_canonical_hash`) for $O(\log n)$ lookup speed.
- Ingestion runs inside an atomic transaction: collisions encountered during concurrent scraping passes trigger an immediate update of `scraped_at` rather than raising a duplicate key error.

### E. Scheduled Runs & Change Detection
- **Automated Cron Pipeline**: Configurable scheduled worker executed via CLI:
  ```powershell
  python -m app.cli run-scheduled-refresh
  ```
  Options include `--health-check / --no-health-check`, `--scrape / --no-scrape`, `--match-refresh / --no-match-refresh`, and `--source <name>`.
- **Takedown & Health Probes**: Active HTTP health checks probe the source URLs of all saved listings. If a remote posting returns `404 Not Found`, `410 Gone`, or contains closure signals ("no longer accepting applications", "job expired"):
  - Listing is flagged `is_active = False` with `taken_down_at = NOW()`.
  - Shortlisted candidates receive an in-app takedown alert and an immediate transactional email notification via Gmail SMTP.
- **Listing Modification Detection**: When recurring scraping passes encounter an existing listing whose salary, deadline, location, or remote policy has changed, the database row is updated and shortlisted users receive an amber badge alert and email breakdown.
- **Automated Match Refreshes**: Verified candidates with uploaded resumes have their match recommendations recomputed automatically against incoming listings.
- **Frontend Shortlist Experience**:
  - Distinct badge visualizer (Amber `Updated`, Red `Inactive / Taken Down`).
  - Interactive "Dismiss" action calling `PATCH /api/matches/{id}/dismiss-alert`.
  - Filter toggle (`Alerts`) with live count badge.

---

## 3. Backend Deep-Dive (FastAPI + Async Python 3.11+)

The backend is located in [`backend/`](backend/) and adheres strictly to asynchronous event-loop safety.

```text
backend/app/
├── main.py                  # FastAPI app factory, lifespan, dynamic CORS, static file mounts
├── config.py                # Pydantic Settings singleton reading .env
├── db.py                    # asyncpg engine, sessionmaker, and table initialization
├── cli.py                   # CLI for scraping, migrations, stats, and hybrid search
├── api/
│   ├── auth.py              # Register, login, verify-email, resend, forgot/reset-password
│   ├── resumes.py           # PDF resume upload, parsing, vector embedding, matching
│   ├── briefings.py         # Async briefing generation, status polling, and playback
│   ├── agent.py             # Authenticated Gemini career agent chat endpoint
│   ├── system.py            # Platform health checks and ingestion statistics
│   └── schemas.py           # Strict Pydantic v2 DTO schemas
├── models/
│   ├── user.py              # User account model with is_verified boolean
│   ├── job_listing.py       # Global listings with HNSW vector + GIN full-text indexes
│   ├── resume.py            # User-owned resume text and embedding
│   ├── user_listing_match.py# User-scoped matches, scores, justifications, shortlist flags
│   └── briefing_job.py      # User-scoped briefing progress, script, and media URLs
├── scrapers/                # BaseScraper, WeWorkRemotely, Arbeitnow, Remotive, RemoteOK, HN
├── pipeline/
│   ├── orchestrator.py      # Deduplicating pipeline coordinator
│   ├── extractor.py         # Gemini 3.5 Flash Lite structured extractor with Pydantic retry
│   └── embeddings.py        # 768-dim embeddings & RRF Hybrid Retrieval implementation
├── agent/
│   ├── loop.py              # Autonomous Gemini function-calling execution loop
│   └── tools.py             # User-isolated tools (query_saved_listings, skills, deadlines)
└── services/
    ├── email.py             # Asynchronous Gmail SMTP dispatcher (aiosmtplib SSL)
    └── briefing.py          # Script generation, D-ID / HeyGen avatar polling, Edge-TTS fallback
```

### A. Authentication, Email Confirmation & 10-Min Password Reset
- **Email Verification**: When a user registers via `POST /api/auth/register`, their account is created with `is_verified = False`. An asynchronous background task sends an HMAC-SHA256 token link via Gmail SMTP. Unverified accounts cannot sign in (`403 Forbidden`).
- **Cryptographic Anti-Tampering**: Verification and reset endpoints never accept hostile `user_id` inputs from URLs or request bodies. Ownership is proven strictly through signed JWT tokens (`purpose="email_verification"` or `purpose="password_reset"`).
- **Strict 10-Minute Reset Expiry**: Password reset tokens expire in **10 minutes max**.
- **Single-Use Invalidation**: Every reset token embeds a 16-character SHA-256 signature of the user's current hashed password (`pwd_sig = sha256(user.hashed_password)[:16]`). The moment the password changes, the signature changes, mathematically revoking all existing reset tokens.
- **Anti-Enumeration**: Reset requests for nonexistent emails return the same HTTP 200 message as valid accounts.

### B. Multi-Tenant Security & URL Tampering Defense
- **Zero Cross-Tenant Leaks**: All user queries explicitly filter by `Model.user_id == current_user.id`.
- If an authenticated attacker tampers with resource UUIDs in URLs (e.g., attempting `GET /api/briefings/<other-user-uuid>`), the SQL query evaluates:
  ```python
  select(BriefingJob).where(BriefingJob.id == job_id, BriefingJob.user_id == current_user.id)
  ```
  This immediately yields `None` and raises a clean `404 Not Found`, confirming that user state never leaks across tenants.

### C. Hybrid Retrieval with Reciprocal Rank Fusion (RRF)
Matching combines semantic vector embeddings with keyword precision using PostgreSQL:
1. **pgvector HNSW Index**: Indexed with `vector_cosine_ops`, $m=16$, and $ef\_construction=64$ for fast approximate nearest-neighbor search.
2. **GIN Full-Text Index**: PostgreSQL tsvector index over title, company, and raw text.
3. **Reciprocal Rank Fusion**: Ranks from both systems are merged via:
   $$RRF\_Score(d) = \sum_{m \in \{\text{vector}, \text{text}\}} \frac{1}{k + \text{rank}_m(d)} \quad (k=60)$$

### D. Multi-Provider Briefing Generation (D-ID $\rightarrow$ HeyGen $\rightarrow$ Edge-TTS)
1. **Gemini 3.5 Flash Lite**: Generates a 60-second broadcast script synthesizing the user's top matches.
2. **D-ID Video (Default if `DID_API_KEY` present)**: Generates expressive talking-head video with transparent background (`result_format="webm"`).
3. **HeyGen Video (Fallback if `HEYGEN_API_KEY` present)**: High-definition avatar synthesis.
4. **Edge-TTS Audio (Zero-Cost Local Fallback)**: High-quality neural text-to-speech saved directly to disk and served via FastAPI static file mounting.

---

## 4. Frontend Deep-Dive (Next.js 16 App Router)

The frontend is located in [`frontend/`](frontend/) and built with Next.js (App Router), TypeScript, and Tailwind CSS.

```text
frontend/src/
├── app/
│   ├── page.tsx                     # Landing page with interactive feature highlights
│   ├── login/page.tsx               # Sign in, register, "Check Your Inbox", forgot password
│   ├── verify-email/page.tsx        # One-click email verification landing page
│   ├── reset-password/page.tsx      # Secure 10-minute password reset with live checklist
│   └── (dashboard)/
│       ├── layout.tsx               # Protected dashboard layout with persistent sidebar
│       ├── dashboard/page.tsx       # Live opportunities, match score radar, metrics
│       ├── shortlist/page.tsx       # Saved applications, status pipeline
│       ├── resumes/page.tsx         # Resume drag-and-drop PDF upload & parsing
│       ├── agent/page.tsx           # Interactive AI Career Intelligence Agent chat
│       └── briefings/page.tsx       # Avatar video / audio briefing hub & player
├── components/
│   ├── protected-route.tsx          # Client-side session guard & redirector
│   ├── match-card.tsx               # Opportunity card with score pill & justification
│   ├── resume-upload-zone.tsx       # Dropzone with validation & PDF preview
│   ├── video-player.tsx             # Responsive video/audio briefing media component
│   └── briefing-stepper.tsx         # Multi-step progress animation for generation
├── lib/
│   ├── api.ts                       # Axios client with JWT interceptor & 401 handling
│   ├── auth-context.tsx             # AuthProvider with user state & session management
│   └── query-client.ts              # TanStack React Query configuration
└── types/
    └── api.ts                       # TypeScript interfaces mirroring backend Pydantic DTOs
```

### Frontend Key Capabilities:
- **Server Components by Default**: Pages default to React Server Components for optimal performance, using `"use client"` exclusively for leaf components requiring state, DOM events, or browser APIs.
- **Client-Side Authentication Guard**: Protected routes wrap inside `ProtectedRoute`, validating active tokens from `auth-context.tsx`.
- **Live Password Complexity Checklist**: Registration and reset pages visually validate uppercase/lowercase letters, digits, and special symbols in real time before submission.
- **Safe Pydantic Error Extraction**: `parseErrorDetail` unwraps FastAPI 422 validation structures into readable user strings, preventing React runtime errors.
- **Responsive Media Player**: Handles video briefings (MP4/WebM) and neural audio briefings (MP3) with playback speed controls, seek bars, and transcript display.

---

## 5. API Reference

| Method & Path | Auth Required | Description |
| --- | :---: | --- |
| `GET /health` | No | System health and database connectivity check. |
| `POST /api/auth/register` | No | Creates unverified account, dispatches confirmation email via Gmail SMTP. |
| `POST /api/auth/login` | No | Authenticates verified user and issues JWT bearer token. |
| `POST /api/auth/verify-email` | No | Validates email token and marks account verified. |
| `POST /api/auth/resend-verification` | No | Resends verification link for unverified account. |
| `POST /api/auth/forgot-password` | No | Dispatches single-use 10-minute password reset link. |
| `POST /api/auth/reset-password` | No | Validates reset token & password signature; updates password. |
| `POST /api/resume/upload` | Yes | Uploads, validates, parses PDF, and computes 768-dim vector. |
| `GET /api/resume/` | Yes | Lists all resumes owned by the authenticated caller. |
| `POST /api/matches/compute` | Yes | Runs hybrid search against the user's latest resume vector. |
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

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Email Confirmation & Password Reset (Gmail SMTP)
GMAIL_USER=nexus.verify.app@gmail.com
GMAIL_APP_PASSWORD=your-16-char-google-app-password
FRONTEND_URL=http://localhost:3000

# Avatar Video Synthesis (Optional)
# D-ID API (Free trial available at https://studio.d-id.com)
DID_API_KEY=
DID_AVATAR_ID=public_mia_elegant@avt_TJ0Tq5
# HeyGen API
HEYGEN_API_KEY=
# (If both are unset, NEXUS automatically falls back to Edge-TTS neural audio)

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
In a new terminal:
```powershell
cd frontend
npm install
npm run dev
```

Visit **`http://localhost:3000`** in your browser. The backend interactive Swagger documentation is available at **`http://localhost:8000/docs`**.

---

### Extraction Evaluation Benchmark Suite (Evals)
Evaluates LLM structured extraction against a curated, hand-labelled ground truth benchmark dataset ([`backend/evals/dataset.json`](backend/evals/dataset.json)):

```powershell
cd backend

# Run against live Gemini 3.5 Flash Lite
..\venv\Scripts\python -m evals.eval_extraction

# Or via Click CLI
..\venv\Scripts\python -m app.cli eval-extraction

# Run in deterministic offline mock mode (for fast CI validation)
..\venv\Scripts\python -m evals.eval_extraction --mock
```

**Benchmark Accuracy Results (10 Ground-Truth Samples including Adversarial Edge Cases):**
* **Job Title Accuracy**: `88.0%` [PASS]
* **Company Name Accuracy**: `90.0%` [PASS]
* **Remote Classification Accuracy**: `90.0%` [PASS]
* **Experience Level Mapping Accuracy**: `80.0%` [PASS]
* **Skills Token Overlap (Mean F1-Score)**: `87.0%` [PASS]
* **Overall Composite Benchmark Score**: **`87.76%`** [PASS] (Threshold: 80%)

---

### Backend Test Suite (`pytest`)
```powershell
cd backend
..\venv\Scripts\python -m pytest tests/test_evals.py -v
..\venv\Scripts\python -m pytest tests/test_email_and_password_reset.py -v
..\venv\Scripts\python -m pytest tests/test_agent_tools.py tests/test_extractor.py -v
```

### Frontend Test Suite & Static Checks (`vitest` + `tsc` + `eslint`)
```powershell
cd frontend
npm test
npx tsc --noEmit
npm run lint
npm run build
```

---

## 9. Production Cloud Deployment (Vercel + Render + Supabase)

Zero codebase modifications are needed to deploy NEXUS to the cloud:

1. **Database (Supabase or Neon Postgres)**:
   - Create a project on [Supabase](https://supabase.com). Enable the `vector` extension.
   - Copy the PostgreSQL URI and set it as `DATABASE_URL` in your backend environment.

2. **Backend (Render Web Service)**:
   - Deploy `backend/` to [Render](https://render.com).
   - Set Build Command: `pip install -r requirements.txt`
   - Set Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Add environment variables (`DATABASE_URL`, `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `FRONTEND_URL`).

3. **Frontend (Vercel)**:
   - Deploy `frontend/` to [Vercel](https://vercel.com).
   - In Project Settings $\rightarrow$ Environment Variables:
     ```env
     NEXT_PUBLIC_API_URL=https://your-nexus-backend.onrender.com
     ```
   - *Note:* CORS is pre-configured in `app/main.py` to automatically permit requests originating from `https://*.vercel.app`.
