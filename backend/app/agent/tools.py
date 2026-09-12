"""
NEXUS -- Career Intelligence Agent Tools.

Three database-backed tools that the Gemini function-calling agent can invoke.
Each tool receives the authenticated ``user_id`` and an async DB session,
queries only that user's data (multi-tenant isolation), and returns a
JSON-serializable dict for the agent to interpret.

Tools
-----
1. ``tool_query_saved_listings``  -- query saved/matched jobs with optional filters.
2. ``tool_get_top_skills_breakdown`` -- aggregate most-requested skills across matches.
3. ``tool_get_deadline_alerts``   -- find matches whose deadlines expire soon.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_listing import JobListing
from app.models.user_listing_match import UserListingMatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: Query Saved / Matched Listings
# ---------------------------------------------------------------------------
async def tool_query_saved_listings(
    user_id: uuid.UUID,
    session: AsyncSession,
    *,
    filter_remote: bool | None = None,
    max_deadline: str | None = None,
) -> dict[str, Any]:
    """Query the user's saved or matched job listings.

    Parameters
    ----------
    filter_remote : bool | None
        If True, return only remote-friendly jobs.
        If False, return only non-remote jobs.
        If None, return all.
    max_deadline : str | None
        If provided (ISO date string e.g. "2026-10-01"), only return
        listings whose deadline is on or before this date.

    Returns
    -------
    dict with keys: "count", "listings" (list of dicts).
    """
    stmt = (
        select(UserListingMatch, JobListing)
        .join(JobListing, UserListingMatch.listing_id == JobListing.id)
        .where(UserListingMatch.user_id == user_id)
        .order_by(UserListingMatch.match_score.desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    listings = []
    for match, listing in rows:
        # Apply optional filters
        if filter_remote is not None and listing.remote_ok != filter_remote:
            continue

        if max_deadline and listing.deadline:
            try:
                dl = datetime.fromisoformat(listing.deadline)
                cutoff = datetime.fromisoformat(max_deadline)
                if dl > cutoff:
                    continue
            except ValueError:
                pass  # unparseable deadline -- include it

        listings.append({
            "title": listing.title,
            "company": listing.company,
            "location": listing.location,
            "remote_ok": listing.remote_ok,
            "stipend": listing.stipend,
            "match_score": round(match.match_score, 3),
            "justification": match.justification,
            "saved": match.saved,
            "status": match.status,
            "deadline": listing.deadline,
            "source_url": listing.source_url,
        })

    return {"count": len(listings), "listings": listings[:20]}


# ---------------------------------------------------------------------------
# Tool 2: Top Skills Breakdown
# ---------------------------------------------------------------------------
async def tool_get_top_skills_breakdown(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Aggregate the most frequently required skills across the user's
    matched job listings.

    Returns
    -------
    dict with keys: "total_matches", "top_skills" (list of {skill, count}).
    """
    stmt = (
        select(JobListing.required_skills)
        .join(UserListingMatch, UserListingMatch.listing_id == JobListing.id)
        .where(UserListingMatch.user_id == user_id)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    counter: Counter[str] = Counter()
    for skills in rows:
        if isinstance(skills, list):
            for skill in skills:
                if isinstance(skill, str) and skill.strip():
                    counter[skill.strip().lower()] += 1

    top_skills = [
        {"skill": skill, "count": count}
        for skill, count in counter.most_common(20)
    ]

    return {"total_matches": len(rows), "top_skills": top_skills}


# ---------------------------------------------------------------------------
# Tool 3: Deadline Alerts
# ---------------------------------------------------------------------------
async def tool_get_deadline_alerts(
    user_id: uuid.UUID,
    session: AsyncSession,
    *,
    days_ahead: int = 7,
) -> dict[str, Any]:
    """Find matched listings whose application deadlines expire within
    *days_ahead* days from today.

    Returns
    -------
    dict with keys: "days_ahead", "urgent_count", "alerts" (list of dicts).
    """
    stmt = (
        select(UserListingMatch, JobListing)
        .join(JobListing, UserListingMatch.listing_id == JobListing.id)
        .where(
            UserListingMatch.user_id == user_id,
            JobListing.deadline.isnot(None),
        )
        .order_by(UserListingMatch.match_score.desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)

    alerts = []
    for match, listing in rows:
        try:
            dl = datetime.fromisoformat(listing.deadline)
            # Make timezone-aware if naive
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if dl <= cutoff:
                alerts.append({
                    "title": listing.title,
                    "company": listing.company,
                    "deadline": listing.deadline,
                    "days_remaining": max(0, (dl - now).days),
                    "match_score": round(match.match_score, 3),
                    "source_url": listing.source_url,
                })
        except (ValueError, TypeError):
            # Deadline is not a parseable date string -- skip
            continue

    # Sort by urgency (fewest days remaining first)
    alerts.sort(key=lambda a: a["days_remaining"])

    return {
        "days_ahead": days_ahead,
        "urgent_count": len(alerts),
        "alerts": alerts[:15],
    }
