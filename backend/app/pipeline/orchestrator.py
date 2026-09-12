"""
NEXUS — Pipeline Orchestrator.

Glues together the scraping engine, LLM extraction, embedding generation,
and database persistence into a single ``run_scrape_pipeline()`` coroutine.

Flow
----
1. Instantiate the selected scraper(s).
2. For each ``RawListing`` yielded by a scraper:
   a. Compute ``canonical_hash``.
   b. Check if the hash already exists in ``job_listings``.
      - If **yes** → update ``scraped_at`` and skip extraction.
      - If **no** → continue to step (c).
   c. If the listing already has pre-parsed fields (e.g. RemoteOK), use
      them directly.  Otherwise, run the LLM extractor.
   d. Generate an embedding for the listing text.
   e. Insert a new ``JobListing`` row.
3. Commit in batches and log summary statistics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update

from app.db import get_session
from app.models.job_listing import JobListing
from app.pipeline.embeddings import generate_embedding
from app.pipeline.extractor import ListingExtractor
from app.scrapers.adzuna import AdzunaScraper
from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.github_hiring import GitHubHiringScraper
from app.scrapers.levels_fyi import LevelsFyiScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.utils import compute_canonical_hash
from app.scrapers.weworkremotely import WeWorkRemotelyScraper

logger = logging.getLogger(__name__)

# Registry of available scrapers
SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "levels_fyi": LevelsFyiScraper,
    "remoteok": RemoteOKScraper,
    "adzuna": AdzunaScraper,
    "github": GitHubHiringScraper,
    "weworkremotely": WeWorkRemotelyScraper,
    "arbeitnow": ArbeitnowScraper,
    "remotive": RemotiveScraper,
}


async def run_scrape_pipeline(
    sources: Sequence[str] | None = None,
    *,
    skip_embeddings: bool = False,
) -> dict[str, int]:
    """
    Run the full scrape → extract → embed → store pipeline.

    Parameters
    ----------
    sources : list[str] | None
        Scraper names to run (keys from ``SCRAPER_REGISTRY``).
        If ``None``, all registered scrapers are run.
    skip_embeddings : bool
        If ``True``, skip the embedding generation step (useful for testing
        without a Gemini API key).

    Returns
    -------
    dict[str, int]
        Summary statistics: ``{"scraped": n, "new": n, "updated": n, "failed": n}``
    """
    if sources is None:
        sources = list(SCRAPER_REGISTRY.keys())

    stats = {"scraped": 0, "new": 0, "updated": 0, "failed": 0}
    extractor = ListingExtractor()

    for source_name in sources:
        scraper_cls = SCRAPER_REGISTRY.get(source_name)
        if scraper_cls is None:
            logger.error("Unknown scraper: %s (available: %s)", source_name, list(SCRAPER_REGISTRY))
            continue

        logger.info("═══ Starting scraper: %s ═══", source_name)

        # ── Scrape ───────────────────────────────────────────────────────
        raw_listings: Sequence[RawListing] = []
        try:
            async with scraper_cls() as scraper:
                raw_listings = await scraper.scrape()
        except Exception as exc:
            logger.error("[%s] Scraper crashed: %s", source_name, exc, exc_info=True)
            continue

        stats["scraped"] += len(raw_listings)
        logger.info("[%s] Got %d raw listings.", source_name, len(raw_listings))

        # ── Process each listing ─────────────────────────────────────────
        for raw in raw_listings:
            try:
                await _process_listing(raw, extractor, skip_embeddings, stats)
            except Exception as exc:
                logger.error(
                    "[%s] Error processing listing %s: %s",
                    source_name, raw.source_url, exc, exc_info=True,
                )
                stats["failed"] += 1

    logger.info(
        "═══ Pipeline complete ═══  scraped=%d  new=%d  updated=%d  failed=%d",
        stats["scraped"], stats["new"], stats["updated"], stats["failed"],
    )
    return stats


async def _process_listing(
    raw: RawListing,
    extractor: ListingExtractor,
    skip_embeddings: bool,
    stats: dict[str, int],
) -> None:
    """Process a single raw listing: dedup → extract → embed → store."""

    # ── Compute dedup hash ───────────────────────────────────────────────
    # For listings without pre-parsed fields, use URL-only hash initially;
    # the full hash is computed after extraction.
    title = raw.title or ""
    company = raw.company or ""
    canonical_hash = compute_canonical_hash(raw.source_url, title, company)

    async with get_session() as session:
        # ── Check for existing listing ───────────────────────────────────
        existing_stmt = select(JobListing).where(
            (JobListing.source_url == raw.source_url)
            | (JobListing.canonical_hash == canonical_hash)
        )
        result = await session.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Listing already in DB — update scraped_at
            existing.scraped_at = datetime.now(timezone.utc)
            if existing.embedding is None and not skip_embeddings:
                existing.embedding = await generate_embedding(raw.raw_text)
                if existing.embedding:
                    logger.info("[*] Backfilled embedding for: %s", raw.source_url)
            logger.debug("Dedup hit: %s — updated scraped_at.", raw.source_url)
            stats["updated"] += 1
            return

        # ── LLM Extraction (if needed) ───────────────────────────────────
        if raw.title and raw.company:
            # Scraper already provided structured data (e.g. RemoteOK)
            extracted_title = raw.title
            extracted_company = raw.company
            extracted_location = raw.location
            extracted_remote = raw.remote_ok
            extracted_stipend = raw.stipend
            extracted_skills = raw.required_skills
            extracted_level = raw.experience_level
            extracted_deadline = raw.deadline
        else:
            # Need LLM extraction (e.g. HN comments)
            extracted = await extractor.extract(raw.raw_text)
            if extracted is None:
                logger.warning("Extraction failed for %s — skipping.", raw.source_url)
                stats["failed"] += 1
                return
            extracted_title = extracted.title
            extracted_company = extracted.company
            extracted_location = extracted.location
            extracted_remote = extracted.remote_ok
            extracted_stipend = extracted.stipend
            extracted_skills = extracted.required_skills
            extracted_level = extracted.experience_level
            extracted_deadline = extracted.deadline

        # Recompute hash with extracted fields (may differ from initial)
        canonical_hash = compute_canonical_hash(
            raw.source_url, extracted_title, extracted_company
        )

        # ── Generate embedding ───────────────────────────────────────────
        embedding: list[float] | None = None
        if not skip_embeddings:
            embedding = await generate_embedding(raw.raw_text)
            if embedding is None:
                logger.warning("Embedding failed for %s — storing without vector.", raw.source_url)

        # ── Insert new listing ───────────────────────────────────────────
        listing = JobListing(
            source_name=raw.source_name,
            source_url=raw.source_url,
            canonical_hash=canonical_hash,
            raw_text=raw.raw_text,
            title=extracted_title,
            company=extracted_company,
            location=extracted_location,
            remote_ok=extracted_remote,
            stipend=extracted_stipend,
            required_skills=extracted_skills,
            experience_level=extracted_level,
            deadline=extracted_deadline,
            embedding=embedding,
        )
        session.add(listing)
        stats["new"] += 1
        logger.info(
            "[+] New listing: %s @ %s [%s]",
            extracted_title, extracted_company, raw.source_name,
        )
