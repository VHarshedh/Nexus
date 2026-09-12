"""
NEXUS — Embeddings & Semantic Search.

Provides:
- ``generate_embedding(text)`` — calls Gemini ``gemini-embedding-2`` to
  produce a 768-dimension vector.
- ``generate_embeddings_batch(texts)`` — batch variant for bulk operations.
- ``find_similar_listings(resume_embedding, session, top_k)`` — executes a
  pgvector **cosine distance** (``<=>``) query to find the closest job
  listings to a given resume vector.

All functions are async and production-ready with error handling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Sequence

from google import genai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job_listing import JobListing

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "gemini-embedding-2"
_EMBEDDING_DIM = 768
_MAX_TEXT_LENGTH = 2048  # Protects TPM (Tokens Per Minute) limit
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 5.0  # seconds


class AsyncRateLimiter:
    """
    Pacing rate limiter to strictly respect API quotas.
    Default: 20 requests per minute (1 request every 3.0s).
    """

    def __init__(self, requests_per_minute: float = 20.0):
        self.interval = 60.0 / requests_per_minute
        self.last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                sleep_needed = self.interval - elapsed
                await asyncio.sleep(sleep_needed)
            self.last_call = time.monotonic()


_rate_limiter = AsyncRateLimiter(requests_per_minute=20.0)


def _get_client() -> genai.Client:
    """Return a Gemini client (created on first call)."""
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


async def generate_embedding(input_text: str) -> list[float] | None:
    """
    Generate a 768-dimension embedding for *input_text* using Gemini
    ``gemini-embedding-2``.

    Includes:
    - Text truncation to 2048 chars to protect TPM quotas.
    - Proactive rate pacing (max 20 RPM).
    - Exponential backoff retry on 429 RESOURCE_EXHAUSTED.

    Returns ``None`` if all retries fail.
    """
    if not input_text or not input_text.strip():
        logger.warning("[embeddings] Empty text — returning None.")
        return None

    clean_text = input_text[:_MAX_TEXT_LENGTH].strip()
    client = _get_client()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            # Enforce smooth pacing (stays under 20 RPM)
            await _rate_limiter.acquire()

            response = await client.aio.models.embed_content(
                model=_EMBEDDING_MODEL,
                contents=clean_text,
                config=dict(output_dimensionality=_EMBEDDING_DIM),
            )

            if response.embeddings and len(response.embeddings) > 0:
                vector = response.embeddings[0].values
                if len(vector) != _EMBEDDING_DIM:
                    logger.warning(
                        "[embeddings] Expected %d dims, got %d.",
                        _EMBEDDING_DIM,
                        len(vector),
                    )
                return list(vector)

            logger.warning("[embeddings] No embeddings returned by API.")
            return None

        except Exception as exc:
            err_str = str(exc)
            is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

            if is_rate_limit and attempt < _MAX_RETRIES:
                backoff = _INITIAL_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "[embeddings] Rate limit reached (429). Backing off for %.1fs (attempt %d/%d)...",
                    backoff,
                    attempt,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(backoff)
                continue

            logger.error("[embeddings] Embedding generation failed: %s", exc)
            return None

    return None


async def generate_embeddings_batch(
    texts: Sequence[str],
    *,
    batch_size: int = 20,
) -> list[list[float] | None]:
    """
    Generate embeddings for a batch of texts.

    Processes in sub-batches of *batch_size* to respect API rate limits.
    Returns a list of the same length as *texts*; items are ``None`` on
    failure.
    """
    results: list[list[float] | None] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        for t in chunk:
            embedding = await generate_embedding(t)
            results.append(embedding)
    return results


async def find_similar_listings(
    resume_embedding: list[float],
    session: AsyncSession,
    *,
    top_k: int = 20,
) -> list[tuple[JobListing, float]]:
    """
    Find the *top_k* job listings most similar to *resume_embedding* using
    pgvector's cosine distance operator ``<=>``.

    Parameters
    ----------
    resume_embedding : list[float]
        768-dim vector representing the user's resume.
    session : AsyncSession
        Active SQLAlchemy async session.
    top_k : int
        Number of results to return (default 20).

    Returns
    -------
    list[tuple[JobListing, float]]
        Pairs of ``(listing, cosine_distance)`` ordered by ascending
        distance (i.e. most similar first).  The distance is in ``[0, 2]``
        where 0 = identical.
    """
    if not resume_embedding:
        logger.warning("[embeddings] Empty resume embedding — returning [].")
        return []

    # Build the pgvector cosine distance query.
    # We cast the parameter to ::vector inside raw SQL because SQLAlchemy
    # doesn't have native operator support for <=>.
    vector_str = "[" + ",".join(str(v) for v in resume_embedding) + "]"

    stmt = (
        select(
            JobListing,
            text(f"embedding <=> '{vector_str}'::vector AS cosine_dist"),
        )
        .where(JobListing.embedding.isnot(None))
        .order_by(text("cosine_dist"))
        .limit(top_k)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [(row[0], float(row[1])) for row in rows]
