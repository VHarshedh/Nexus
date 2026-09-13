"""
NEXUS -- FastAPI Application Entry Point.

Creates the FastAPI app with:
- Lifespan management (init_db on startup, dispose on shutdown).
- CORS middleware configured for localhost:3000.
- All API routers registered.
- Static file serving for uploaded media (resumes, briefing audio).

Run with::

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import dispose_engine, init_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    # -- Startup --------------------------------------------------------------
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("NEXUS API starting up...")

    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Initialise database (pgvector extension + tables)
    await init_db()
    logger.info("Database initialised.")

    yield  # <-- app is running

    # -- Shutdown -------------------------------------------------------------
    await dispose_engine()
    logger.info("NEXUS API shut down.")


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NEXUS -- Autonomous Career Intelligence Agent",
    description=(
        "REST API for the NEXUS career intelligence platform. "
        "Provides authentication, resume management, semantic job matching, "
        "an AI-powered career agent, and async video briefings."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Static Files (uploaded resumes, briefing audio/video)
# ---------------------------------------------------------------------------
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


# ---------------------------------------------------------------------------
# Register Routers
# ---------------------------------------------------------------------------
from app.api.auth import router as auth_router  # noqa: E402
from app.api.resumes import router as resumes_router  # noqa: E402
from app.api.agent import router as agent_router  # noqa: E402
from app.api.briefings import router as briefings_router  # noqa: E402
from app.api.system import router as system_router  # noqa: E402

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(resumes_router)
app.include_router(agent_router)
app.include_router(briefings_router)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["system"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "nexus-api"}
