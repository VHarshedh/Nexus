"""
NEXUS -- Async Video Briefing Engine.

Generates a career briefing for the authenticated user:

1. Synthesise a 60-90 second narrated **script** from the user's top 3
   matched job listings using Gemini.
2. Convert the script to audio/video:
   - **Primary path**: HeyGen API (if ``HEYGEN_API_KEY`` is configured).
   - **Fallback path**: Microsoft Edge-TTS (free, no API key).
3. Store the resulting media URL and update the ``BriefingJob`` record.

Background-Task Session Safety
------------------------------
``run_briefing_pipeline`` creates its **own** database session via
``get_session()`` (the context-manager variant) rather than relying on
the request-scoped FastAPI session, which closes when the HTTP response
completes.  This is critical for correctness.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import edge_tts
import httpx
from google import genai
from google.genai import types
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session  # <-- NOT get_db_session (request-scoped)
from app.models.briefing_job import BriefingJob
from app.models.job_listing import JobListing
from app.models.user_listing_match import UserListingMatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Script Generation
# ---------------------------------------------------------------------------
async def generate_briefing_script(
    user_id: uuid.UUID,
) -> str:
    """Generate a 60-90 second career briefing script from the user's
    top 3 matched jobs.

    Uses its own DB session to be safe for background tasks.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    # Fetch top 3 matches
    async with get_session() as session:
        stmt = (
            select(UserListingMatch, JobListing)
            .join(JobListing, UserListingMatch.listing_id == JobListing.id)
            .where(UserListingMatch.user_id == user_id)
            .order_by(UserListingMatch.match_score.desc())
            .limit(3)
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        return (
            "Welcome to your NEXUS career briefing. "
            "Unfortunately, no job matches were found yet. "
            "Upload your resume and compute matches to receive "
            "a personalised briefing. Stay tuned!"
        )

    # Build context for the LLM
    jobs_context = []
    for i, (match, listing) in enumerate(rows, 1):
        jobs_context.append(
            f"Job {i}: {listing.title} at {listing.company} "
            f"(Location: {listing.location or 'N/A'}, "
            f"Remote: {'Yes' if listing.remote_ok else 'No'}, "
            f"Match Score: {match.match_score:.0%}). "
            f"Key Skills: {', '.join(listing.required_skills or [])}. "
            f"Justification: {match.justification or 'N/A'}."
        )

    prompt = (
        "You are a professional career briefing presenter. "
        "Write a concise, energetic script for a 60-90 second audio briefing "
        "that summarises the user's top job matches. "
        "Use a warm, professional tone. Address the listener directly as 'you'. "
        "Structure: brief greeting, then cover each job with why it's a great fit, "
        "end with an encouraging call to action.\n\n"
        "TOP MATCHED JOBS:\n" + "\n".join(jobs_context) + "\n\n"
        "Write ONLY the narration script. No stage directions or timestamps."
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.6,
            max_output_tokens=600,
        ),
    )

    return (response.text or "Your career briefing could not be generated.").strip()


# ---------------------------------------------------------------------------
# 2a. Edge-TTS Audio Synthesis (Fallback -- Free, No API Key)
# ---------------------------------------------------------------------------
async def synthesize_audio_edge_tts(
    script: str,
    output_path: Path,
) -> Path:
    """Convert *script* to an MP3 file using Microsoft Edge-TTS.

    This is the fallback path when no HeyGen API key is configured.
    Returns the path to the generated MP3 file.
    """
    communicate = edge_tts.Communicate(
        text=script,
        voice="en-US-JennyNeural",  # natural-sounding female voice
        rate="+5%",
    )
    await communicate.save(str(output_path))
    logger.info("[briefing] Edge-TTS audio saved: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# 2b. HeyGen Video Synthesis (Primary -- Requires API Key)
# ---------------------------------------------------------------------------
async def synthesize_video_heygen(script: str) -> str | None:
    """Send the script to HeyGen's API and poll until the video is ready.

    Returns the video URL on success, or None on failure.
    """
    settings = get_settings()
    if not settings.heygen_api_key:
        return None

    api_key = settings.heygen_api_key
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    # Create the video
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": "Angela-inblackskirt-20220820",
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": "1bd001e7e50f421d891986aad48f90fd",
                },
            }
        ],
        "dimension": {"width": 1280, "height": 720},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Submit video generation
            resp = await client.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            video_id = data.get("data", {}).get("video_id")
            if not video_id:
                logger.error("[heygen] No video_id returned: %s", data)
                return None

            logger.info("[heygen] Video submitted: %s", video_id)

            # Poll for completion (up to 5 minutes)
            for _ in range(60):
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                    headers=headers,
                )
                status_data = status_resp.json()
                video_status = status_data.get("data", {}).get("status")

                if video_status == "completed":
                    video_url = status_data["data"].get("video_url")
                    logger.info("[heygen] Video ready: %s", video_url)
                    return video_url
                elif video_status == "failed":
                    error = status_data.get("data", {}).get("error")
                    logger.error("[heygen] Video failed: %s", error)
                    return None
                # else: still processing, continue polling

            logger.error("[heygen] Video generation timed out.")
            return None

    except Exception as exc:
        logger.error("[heygen] API error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 3. Background Pipeline
# ---------------------------------------------------------------------------
async def run_briefing_pipeline(job_id: uuid.UUID) -> None:
    """Background task: generate script, synthesise media, update DB.

    Creates its own DB session (not the request-scoped one) so it
    is safe to run after the HTTP response has already been sent.
    """
    logger.info("[briefing] Starting pipeline for job %s", job_id)

    # -- Load the job record --------------------------------------------------
    async with get_session() as session:
        result = await session.execute(
            select(BriefingJob).where(BriefingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.error("[briefing] Job %s not found.", job_id)
            return

        user_id = job.user_id
        job.status = "processing"

    try:
        # -- Step 1: Generate script ------------------------------------------
        script = await generate_briefing_script(user_id)

        # -- Step 2: Synthesise media -----------------------------------------
        settings = get_settings()
        media_url: str | None = None

        # Try HeyGen first
        if settings.heygen_api_key:
            media_url = await synthesize_video_heygen(script)

        # Fallback to Edge-TTS
        if media_url is None:
            output_dir = settings.upload_dir / str(user_id) / "briefings"
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / f"{job_id}.mp3"
            await synthesize_audio_edge_tts(script, audio_path)
            # Construct a URL relative to the static mount
            media_url = f"/uploads/{user_id}/briefings/{job_id}.mp3"

        # -- Step 3: Update DB ------------------------------------------------
        async with get_session() as session:
            result = await session.execute(
                select(BriefingJob).where(BriefingJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.script = script
                job.media_url = media_url
                job.status = "done"
                job.completed_at = datetime.now(timezone.utc)

        logger.info("[briefing] Pipeline complete for job %s", job_id)

    except Exception as exc:
        logger.error("[briefing] Pipeline failed for job %s: %s", job_id, exc, exc_info=True)
        async with get_session() as session:
            result = await session.execute(
                select(BriefingJob).where(BriefingJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
