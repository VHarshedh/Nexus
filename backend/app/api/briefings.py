"""
NEXUS -- Briefing API Endpoints.

Endpoints:
- ``POST /api/briefings/generate``  -- queue a new briefing (non-blocking).
- ``GET  /api/briefings/{job_id}``  -- check status of a specific briefing.
- ``GET  /api/briefings/``          -- list all briefings for the current user.

All queries enforce multi-tenant isolation via ``user_id == current_user.id``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import BriefingCreateResponse, BriefingJobResponse
from app.db import get_db_session
from app.models.briefing_job import BriefingJob
from app.models.user import User
from app.services.briefing import run_briefing_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


# ---------------------------------------------------------------------------
# Helper to run async background task from FastAPI BackgroundTasks
# ---------------------------------------------------------------------------
def _run_async_pipeline(job_id: uuid.UUID) -> None:
    """Wrapper that runs the async pipeline in a new event loop.

    FastAPI's ``BackgroundTasks`` runs callables in a thread-pool, so we
    need to create a fresh event loop for the async briefing pipeline.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_briefing_pipeline(job_id))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Generate Briefing (non-blocking)
# ---------------------------------------------------------------------------
@router.post("/generate", response_model=BriefingCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_briefing(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> BriefingCreateResponse:
    """Create a new briefing job and launch background processing.

    Returns immediately with the job ID and ``status="queued"``.
    """
    job = BriefingJob(
        user_id=current_user.id,
        status="queued",
    )
    session.add(job)
    await session.flush()

    job_id = job.id
    logger.info("[briefings] Queued briefing %s for user %s", job_id, current_user.email)

    # Launch the background pipeline (runs in a thread with its own event loop
    # and its own DB session -- does NOT depend on the request session).
    background_tasks.add_task(_run_async_pipeline, job_id)

    return BriefingCreateResponse(
        job_id=job_id,
        status="queued",
        message="Briefing generation started. Poll GET /api/briefings/{job_id} for status.",
    )


# ---------------------------------------------------------------------------
# Get Briefing Status
# ---------------------------------------------------------------------------
@router.get("/{job_id}", response_model=BriefingJobResponse)
async def get_briefing(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> BriefingJobResponse:
    """Return the current status and media URL of a briefing job.

    Multi-tenant: only the owning user can access their briefing.
    """
    result = await session.execute(
        select(BriefingJob).where(
            BriefingJob.id == job_id,
            BriefingJob.user_id == current_user.id,  # <-- ISOLATION
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing job not found.",
        )

    return BriefingJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# List Briefings
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[BriefingJobResponse])
async def list_briefings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[BriefingJobResponse]:
    """List all briefing jobs for the authenticated user."""
    result = await session.execute(
        select(BriefingJob)
        .where(BriefingJob.user_id == current_user.id)  # <-- ISOLATION
        .order_by(BriefingJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [BriefingJobResponse.model_validate(j) for j in jobs]
