"""
NEXUS -- Resume Upload & Semantic Matching API.

Endpoints:
- ``POST /api/resume/upload``       -- upload PDF, extract text, generate embedding.
- ``GET  /api/resume/``             -- list the current user's resumes.
- ``POST /api/matches/compute``     -- compute cosine-similarity matches + LLM justifications.
- ``GET  /api/matches/``            -- list the current user's matches.
- ``PATCH /api/matches/{id}/save``  -- toggle the ``saved`` flag on a match.

Multi-Tenant Isolation
----------------------
Every query filters by ``user_id == current_user.id``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

import aiofiles
import pdfplumber
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.api.schemas import (
    MatchComputeResponse,
    MatchListingDetail,
    MatchResponse,
    ResumeResponse,
)
from app.config import get_settings
from app.db import get_db_session
from app.models.job_listing import JobListing
from app.models.resume import Resume
from app.models.user import User
from app.models.user_listing_match import UserListingMatch
from app.services.cost_tracker import record_token_usage
from app.pipeline.embeddings import find_similar_listings, generate_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["resumes"])


def _extract_pdf_text(file_path: Path) -> str:
    """Run sync pdfplumber parsing off the FastAPI event loop."""
    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            if page_text := page.extract_text():
                pages.append(page_text)
    return "\n".join(pages).strip()


# ---------------------------------------------------------------------------
# Resume Upload
# ---------------------------------------------------------------------------
@router.post(
    "/api/resume/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    """Accept a PDF resume, extract text, generate embedding, and store."""

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    # -- Save file to disk ----------------------------------------------------
    settings = get_settings()
    upload_dir = settings.upload_dir / str(current_user.id) / "resumes"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # UploadFile.filename is client-controlled.  Retain only its basename so
    # path separators cannot escape the per-user upload directory.
    original_name = Path(file.filename).name
    safe_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = upload_dir / safe_name

    content = await file.read()
    if len(content) > settings.max_resume_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Resume exceeds the {settings.max_resume_upload_bytes // (1024 * 1024)} MB upload limit.",
        )
    async with aiofiles.open(file_path, "wb") as upload_file:
        await upload_file.write(content)

    # -- Extract text with pdfplumber -----------------------------------------
    try:
        raw_text = await asyncio.to_thread(_extract_pdf_text, file_path)
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not extract text from PDF: {exc}",
        )

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF appears to contain no extractable text.",
        )

    # -- Generate embedding ---------------------------------------------------
    embedding = await generate_embedding(raw_text)

    # -- Store in DB ----------------------------------------------------------
    resume = Resume(
        user_id=current_user.id,
        raw_text=raw_text,
        file_path=str(file_path),
        embedding=embedding,
    )
    session.add(resume)
    await session.flush()

    # Track embedding token usage (~1 token per 4 chars)
    estimated_tokens = max(1, len(raw_text) // 4)
    await record_token_usage(
        session=session,
        user_id=current_user.id,
        feature="resume_parsing",
        model="gemini-embedding-2",
        prompt_tokens=estimated_tokens,
        completion_tokens=0,
        meta={"filename": original_name},
    )

    logger.info("Resume uploaded for user %s: %s", current_user.email, safe_name)
    return ResumeResponse.model_validate(resume)


# ---------------------------------------------------------------------------
# List Resumes
# ---------------------------------------------------------------------------
@router.get("/api/resume/", response_model=list[ResumeResponse])
async def list_resumes(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[ResumeResponse]:
    """List all resumes belonging to the authenticated user."""
    result = await session.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
    )
    resumes = result.scalars().all()
    return [ResumeResponse.model_validate(r) for r in resumes]


async def refresh_user_matches(
    user_id: uuid.UUID,
    session: AsyncSession,
    top_k: int = 20,
) -> list[MatchResponse]:
    """Compute or refresh semantic matches between a user's latest resume and all listings."""
    # -- Get the user's latest resume with an embedding -----------------------
    result = await session.execute(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.embedding.isnot(None))
        .order_by(Resume.uploaded_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        return []

    # -- Fetch user preferences -----------------------------------------------
    user_res = await session.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    preferences = user.preferences if user else None

    # -- Semantic search via pgvector -----------------------------------------
    similar = await find_similar_listings(
        resume.embedding, session, top_k=top_k, preferences=preferences
    )
    if not similar:
        return []

    # -- Generate LLM justifications in batch (1 API call instead of 20) ------
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    matches_out: list[MatchResponse] = []

    # Filter listings that need new justifications (new matches or fallback text)
    listings_list = [listing for listing, _ in similar]
    justifications_map = await _generate_batch_justifications(
        client, resume.raw_text, listings_list, session=session, user_id=user_id
    )

    for listing, distance in similar:
        score = max(0.0, 1.0 - distance)
        generated_justification = (
            justifications_map.get(str(listing.id))
            or f"Strong alignment with candidate profile for {listing.title or 'this role'}."
        )

        # Upsert UserListingMatch (avoid duplicates on re-run)
        existing = await session.execute(
            select(UserListingMatch).where(
                UserListingMatch.user_id == user_id,
                UserListingMatch.listing_id == listing.id,
            )
        )
        match_row = existing.scalar_one_or_none()

        if match_row is None:
            match_row = UserListingMatch(
                user_id=user_id,
                listing_id=listing.id,
                match_score=round(score, 4),
                justification=generated_justification,
                saved=False,
                status="pending",
            )
            session.add(match_row)
        else:
            match_row.match_score = round(score, 4)
            # Update justification if previously missing or was a fallback
            if not match_row.justification or match_row.justification.startswith("Match based on"):
                match_row.justification = generated_justification

        await session.flush()

        listing_detail = MatchListingDetail.model_validate(listing)
        matches_out.append(
            MatchResponse(
                id=match_row.id,
                listing_id=listing.id,
                match_score=match_row.match_score,
                justification=match_row.justification,
                saved=match_row.saved,
                status=match_row.status,
                change_alert=match_row.change_alert,
                change_alert_at=match_row.change_alert_at,
                created_at=match_row.created_at,
                listing=listing_detail,
            )
        )

    return matches_out


# ---------------------------------------------------------------------------
# Compute Matches
# ---------------------------------------------------------------------------
@router.post("/api/matches/compute", response_model=MatchComputeResponse)
async def compute_matches(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    top_k: int = 20,
) -> MatchComputeResponse:
    """Compute cosine-similarity matches between the user's latest resume
    and all job listings, then generate LLM justifications for the top hits.
    """
    matches_out = await refresh_user_matches(current_user.id, session, top_k=top_k)
    if not matches_out:
        # Check if user had no resume
        res = await session.execute(
            select(Resume).where(Resume.user_id == current_user.id, Resume.embedding.isnot(None))
        )
        if not res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No resume with embedding found. Upload a resume first.",
            )

    return MatchComputeResponse(computed=len(matches_out), matches=matches_out)


async def _generate_batch_justifications(
    client: genai.Client,
    resume_text: str,
    listings: list[JobListing],
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, str]:
    """Generate concise 1-line match justifications for multiple listings in a single Gemini request.

    Batching avoids hitting the Gemini Free Tier 15 RPM rate limit when computing top_k matches.
    """
    if not listings:
        return {}

    resume_snippet = resume_text[:1200]
    jobs_summary = []
    for l in listings:
        jobs_summary.append({
            "id": str(l.id),
            "title": l.title or "Role",
            "company": l.company or "Company",
            "skills": l.required_skills or [],
            "location": l.location or "Unspecified",
            "remote": l.remote_ok,
        })

    prompt = (
        "You are an expert career intelligence AI. Given a candidate's resume snippet and a list "
        "of matched job openings, provide exactly ONE concise sentence (max 25 words) for each job "
        "explaining why it is a strong match based on their skills and background.\n\n"
        f"RESUME SNIPPET:\n{resume_snippet}\n\n"
        f"JOB LISTINGS (JSON):\n{json.dumps(jobs_summary, indent=2)}\n\n"
        "Return ONLY a JSON object mapping each job's 'id' to its 1-sentence justification string.\n"
        'Example format: {"<id>": "Strong match based on candidate\'s Python and cloud API skills.", ...}'
    )

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )

        if getattr(response, "usage_metadata", None) and session and user_id:
            await record_token_usage(
                session=session,
                user_id=user_id,
                feature="match_justifications",
                model="gemini-3.5-flash-lite",
                prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                meta={"matched_jobs": len(listings)},
            )

        if response.text:
            data = json.loads(response.text)
            if isinstance(data, dict):
                return {str(k): str(v).strip() for k, v in data.items()}
    except Exception as exc:
        logger.warning("[matching] Batch justification generation failed: %s", exc)

    return {}


async def _generate_justification(
    client: genai.Client,
    resume_text: str,
    listing: JobListing,
) -> str:
    """Call Gemini to generate a concise 1-line match justification."""
    resume_snippet = resume_text[:1500]
    prompt = (
        "You are a career matching assistant. Given the candidate's resume snippet "
        "and a job listing, write exactly ONE concise sentence (max 30 words) explaining "
        "why this is a good match. Focus on specific skill overlaps.\n\n"
        f"RESUME SNIPPET:\n{resume_snippet}\n\n"
        f"JOB: {listing.title} at {listing.company}\n"
        f"Skills: {listing.required_skills}\n"
        f"Location: {listing.location} | Remote: {listing.remote_ok}\n"
    )

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=100,
            ),
        )
        return (response.text or "").strip()
    except Exception as exc:
        logger.warning("Justification generation failed: %s", exc)
        return "Match based on semantic similarity."


# ---------------------------------------------------------------------------
# List Matches
# ---------------------------------------------------------------------------
@router.get("/api/matches/", response_model=list[MatchResponse])
async def list_matches(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[MatchResponse]:
    """List all matches for the authenticated user, sorted by score."""
    result = await session.execute(
        select(UserListingMatch)
        .options(selectinload(UserListingMatch.listing))
        .where(UserListingMatch.user_id == current_user.id)
        .order_by(UserListingMatch.match_score.desc())
    )
    match_rows = result.scalars().all()

    matches_out: list[MatchResponse] = []
    for m in match_rows:
        listing_detail = MatchListingDetail.model_validate(m.listing) if m.listing else None
        matches_out.append(
            MatchResponse(
                id=m.id,
                listing_id=m.listing_id,
                match_score=m.match_score,
                justification=m.justification,
                saved=m.saved,
                status=m.status,
                change_alert=m.change_alert,
                change_alert_at=m.change_alert_at,
                created_at=m.created_at,
                listing=listing_detail,
            )
        )

    return matches_out


# ---------------------------------------------------------------------------
# Toggle Save
# ---------------------------------------------------------------------------
@router.patch("/api/matches/{match_id}/save", response_model=MatchResponse)
async def toggle_save(
    match_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    """Toggle the 'saved' flag on a match (multi-tenant enforced)."""
    result = await session.execute(
        select(UserListingMatch)
        .options(selectinload(UserListingMatch.listing))
        .where(
            UserListingMatch.id == match_id,
            UserListingMatch.user_id == current_user.id,  # <-- ISOLATION
        )
    )
    match_row = result.scalar_one_or_none()

    if match_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    match_row.saved = not match_row.saved
    await session.flush()

    listing_detail = (
        MatchListingDetail.model_validate(match_row.listing)
        if match_row.listing
        else None
    )

    return MatchResponse(
        id=match_row.id,
        listing_id=match_row.listing_id,
        match_score=match_row.match_score,
        justification=match_row.justification,
        saved=match_row.saved,
        status=match_row.status,
        change_alert=match_row.change_alert,
        change_alert_at=match_row.change_alert_at,
        created_at=match_row.created_at,
        listing=listing_detail,
    )


# ---------------------------------------------------------------------------
# Dismiss Change Alert
# ---------------------------------------------------------------------------
@router.patch("/api/matches/{match_id}/dismiss-alert", response_model=MatchResponse)
async def dismiss_match_alert(
    match_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    """Clear the change_alert flag on a saved match (multi-tenant enforced)."""
    result = await session.execute(
        select(UserListingMatch)
        .options(selectinload(UserListingMatch.listing))
        .where(
            UserListingMatch.id == match_id,
            UserListingMatch.user_id == current_user.id,  # <-- ISOLATION
        )
    )
    match_row = result.scalar_one_or_none()

    if match_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    match_row.change_alert = None
    match_row.change_alert_at = None
    await session.flush()

    listing_detail = (
        MatchListingDetail.model_validate(match_row.listing)
        if match_row.listing
        else None
    )

    return MatchResponse(
        id=match_row.id,
        listing_id=match_row.listing_id,
        match_score=match_row.match_score,
        justification=match_row.justification,
        saved=match_row.saved,
        status=match_row.status,
        change_alert=match_row.change_alert,
        change_alert_at=match_row.change_alert_at,
        created_at=match_row.created_at,
        listing=listing_detail,
    )
