"""
NEXUS — Scheduled Pipeline & Change Detection Service.

Provides automated workflows designed to run as cron tasks or background workers:
1. ``check_saved_listings_health()``: Validates that saved job listings remain active on remote sources.
   Detects takedowns/404s/closures, marks listings as inactive, and triggers user alerts.
2. ``refresh_all_user_matches()``: Re-runs vector similarity matches against new listings for all verified users.
3. ``run_scheduled_pipeline()``: Orchestrates health checking, web scraping, and match refresh.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.resumes import refresh_user_matches
from app.config import get_settings
from app.db import get_session
from app.models.job_listing import JobListing
from app.models.resume import Resume
from app.models.user import User
from app.models.user_listing_match import UserListingMatch
from app.pipeline.orchestrator import run_scrape_pipeline
from app.services.email import send_job_takedown_alert_email

logger = logging.getLogger(__name__)

# Realistic User-Agent for polite health checks
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 NEXUS-CareerBot/1.0"
    )
}

# Signatures in page text that indicate a job posting is expired/closed
CLOSED_SIGNATURES = [
    "this job has expired",
    "position has been filled",
    "no longer accepting applications",
    "job posting is no longer available",
    "this listing has expired",
    "this job is closed",
    "job is no longer active",
]


async def check_saved_listings_health(client: httpx.AsyncClient | None = None) -> dict[str, int]:
    """Check availability of all saved active listings via remote HTTP requests.

    If a listing returns 404, 410, or contains closed signatures:
    - Mark ``is_active = False`` and ``taken_down_at = now()``
    - Set ``change_alert`` on all saved matches for that listing
    - Dispatch transactional alert emails to shortlisted users
    """
    stats = {"checked": 0, "taken_down": 0, "alerts_dispatched": 0}
    settings = get_settings()
    shortlist_url = f"{settings.frontend_url}/shortlist"

    async with get_session() as session:
        # Find active listings that are currently saved by at least one user
        query = (
            select(JobListing)
            .join(UserListingMatch, UserListingMatch.listing_id == JobListing.id)
            .where(
                JobListing.is_active.is_(True),
                UserListingMatch.saved.is_(True),
            )
            .distinct()
        )
        res = await session.execute(query)
        active_saved_listings = res.scalars().all()

        if not active_saved_listings:
            logger.info("[health-check] No active saved listings to inspect.")
            return stats

        stats["checked"] = len(active_saved_listings)
        logger.info("[health-check] Verifying %d saved listings...", len(active_saved_listings))

        owns_client = client is None
        http = client or httpx.AsyncClient(
            headers=HTTP_HEADERS,
            timeout=12.0,
            follow_redirects=True,
            verify=False,  # tolerate self-signed or incomplete remote cert chains
        )

        try:
            for listing in active_saved_listings:
                is_dead = False
                reason = ""

                # Skip non-http URLs (e.g. mock test URLs)
                if not listing.source_url.startswith(("http://", "https://")):
                    continue

                try:
                    # Polite jitter before inspection
                    await asyncio.sleep(0.5)
                    response = await http.get(listing.source_url)

                    if response.status_code in (404, 410):
                        is_dead = True
                        reason = f"HTTP {response.status_code} Not Found"
                    elif response.status_code == 200:
                        body_lower = response.text.lower()
                        for sig in CLOSED_SIGNATURES:
                            if sig in body_lower:
                                is_dead = True
                                reason = f"Listing expired on page ('{sig}')"
                                break
                except httpx.HTTPError as err:
                    logger.debug("[health-check] Network check failed for %s: %s", listing.source_url, err)
                    # Do not eagerly flag as dead on transient network timeouts
                    continue
                except Exception as exc:
                    logger.debug("[health-check] Unexpected check error for %s: %s", listing.source_url, exc)
                    continue

                if is_dead:
                    logger.warning("[health-check] Listing taken down: %s (%s) - %s", listing.title, listing.source_url, reason)
                    stats["taken_down"] += 1
                    listing.is_active = False
                    listing.taken_down_at = datetime.now(timezone.utc)

                    # Update matches and notify users
                    matches_stmt = (
                        select(UserListingMatch)
                        .options(selectinload(UserListingMatch.user))
                        .where(
                            UserListingMatch.listing_id == listing.id,
                            UserListingMatch.saved.is_(True),
                        )
                    )
                    matches_res = await session.execute(matches_stmt)
                    matches = matches_res.scalars().all()

                    for m in matches:
                        m.change_alert = f"Listing taken down or closed on source site ({reason})"
                        m.change_alert_at = datetime.now(timezone.utc)

                        if m.user and m.user.email and m.user.is_verified:
                            try:
                                await send_job_takedown_alert_email(
                                    to_email=m.user.email,
                                    job_title=listing.title or "Saved Role",
                                    company=listing.company or "Company",
                                    source_url=listing.source_url,
                                    shortlist_url=shortlist_url,
                                )
                                stats["alerts_dispatched"] += 1
                            except Exception as email_err:
                                logger.error(
                                    "Failed sending takedown alert to %s: %s",
                                    m.user.email,
                                    email_err,
                                )

        finally:
            if owns_client:
                await http.aclose()

    logger.info(
        "[health-check] Finished: %d checked, %d taken down, %d alerts dispatched.",
        stats["checked"],
        stats["taken_down"],
        stats["alerts_dispatched"],
    )
    return stats


async def refresh_all_user_matches(top_k: int = 20) -> dict[str, int]:
    """Compute / update top matching listings for all verified users with an uploaded resume."""
    stats = {"users_refreshed": 0, "total_matches": 0}

    async with get_session() as session:
        # Find verified users who have at least one resume with embedding
        stmt = (
            select(User.id)
            .join(Resume, Resume.user_id == User.id)
            .where(
                User.is_verified.is_(True),
                Resume.embedding.isnot(None),
            )
            .distinct()
        )
        res = await session.execute(stmt)
        user_ids = res.scalars().all()

        if not user_ids:
            logger.info("[match-refresh] No verified users with resumes found.")
            return stats

        logger.info("[match-refresh] Refreshing matches for %d verified user(s)...", len(user_ids))

        for uid in user_ids:
            try:
                matches = await refresh_user_matches(uid, session, top_k=top_k)
                stats["users_refreshed"] += 1
                stats["total_matches"] += len(matches)
                logger.info("[match-refresh] User %s: %d matches refreshed.", uid, len(matches))
            except Exception as exc:
                logger.error("[match-refresh] Error refreshing matches for user %s: %s", uid, exc, exc_info=True)

    logger.info(
        "[match-refresh] Finished: %d users refreshed, %d total matches.",
        stats["users_refreshed"],
        stats["total_matches"],
    )
    return stats


async def run_scheduled_pipeline(
    run_scraper: bool = True,
    run_health_check: bool = True,
    run_match_refresh: bool = True,
    scraper_names: list[str] | None = None,
    skip_embeddings: bool = False,
) -> dict[str, Any]:
    """Top-level scheduled cron pipeline entry point.

    Execution phases:
    1. Health Check & Takedown Detection on saved listings.
    2. Scraping ingestion + LLM extraction + Change detection on existing listings.
    3. Automated semantic matching refresh for all verified users.
    """
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "health_check": None,
        "scraper": None,
        "match_refresh": None,
    }

    # Phase 1: Check health of saved jobs
    if run_health_check:
        logger.info("═══ Phase 1: Running Saved Listing Health Check ═══")
        try:
            report["health_check"] = await check_saved_listings_health()
        except Exception as exc:
            logger.error("Health check phase failed: %s", exc, exc_info=True)
            report["health_check"] = {"error": str(exc)}

    # Phase 2: Scrape new listings and detect modifications
    if run_scraper:
        logger.info("═══ Phase 2: Running Scraper Pipeline ═══")
        try:
            report["scraper"] = await run_scrape_pipeline(
                sources=scraper_names,
                skip_embeddings=skip_embeddings,
            )
        except Exception as exc:
            logger.error("Scraper pipeline phase failed: %s", exc, exc_info=True)
            report["scraper"] = {"error": str(exc)}

    # Phase 3: Refresh candidate matches
    if run_match_refresh:
        logger.info("═══ Phase 3: Refreshing Candidate Matches ═══")
        try:
            report["match_refresh"] = await refresh_all_user_matches()
        except Exception as exc:
            logger.error("Match refresh phase failed: %s", exc, exc_info=True)
            report["match_refresh"] = {"error": str(exc)}

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("═══ Scheduled Pipeline Run Complete ═══")
    return report
