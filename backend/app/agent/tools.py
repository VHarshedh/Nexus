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

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_listing import JobListing
from app.models.user_listing_match import UserListingMatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: Query Saved / Matched Listings (with DB market fallback)
# ---------------------------------------------------------------------------
async def tool_query_saved_listings(
    user_id: uuid.UUID,
    session: AsyncSession,
    *,
    filter_remote: bool | None = None,
    max_deadline: str | None = None,
) -> dict[str, Any]:
    """Query the user's saved or matched job listings.

    If the user has not uploaded a resume or computed matches yet, falls back
    to returning live opportunities from the ingested database.
    """
    stmt = (
        select(UserListingMatch, JobListing)
        .join(JobListing, UserListingMatch.listing_id == JobListing.id)
        .where(UserListingMatch.user_id == user_id)
        .order_by(UserListingMatch.match_score.desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Fallback to general market listings if candidate has 0 matches
    if not rows:
        fallback_stmt = select(JobListing).order_by(JobListing.scraped_at.desc()).limit(100)
        if filter_remote is not None:
            fallback_stmt = fallback_stmt.where(JobListing.remote_ok == filter_remote)
        
        fallback_result = await session.execute(fallback_stmt)
        all_jobs = fallback_result.scalars().all()

        listings = []
        for j in all_jobs:
            listings.append({
                "title": j.title or "Untitled Role",
                "company": j.company or "Undisclosed",
                "location": j.location or "Remote",
                "remote_ok": j.remote_ok,
                "stipend": j.stipend or "Not specified",
                "match_score": None,
                "justification": "Live market listing from database (Upload resume to compute personal match score)",
                "saved": False,
                "status": "unmatched",
                "deadline": j.deadline,
                "source_url": j.source_url,
                "skills": j.required_skills or [],
            })

        # Sort jobs with disclosed salary first
        listings.sort(
            key=lambda x: (x["stipend"] != "Not specified", x["remote_ok"]),
            reverse=True,
        )

        return {
            "count": len(listings[:20]),
            "is_personal_match": False,
            "note": "Candidate has not uploaded a resume yet. Showing live listings from the 974 ingested jobs in database.",
            "listings": listings[:20],
        }

    listings = []
    for match, listing in rows:
        if filter_remote is not None and listing.remote_ok != filter_remote:
            continue

        if max_deadline and listing.deadline:
            try:
                dl = datetime.fromisoformat(listing.deadline)
                cutoff = datetime.fromisoformat(max_deadline)
                if dl > cutoff:
                    continue
            except ValueError:
                pass

        listings.append({
            "title": listing.title,
            "company": listing.company,
            "location": listing.location,
            "remote_ok": listing.remote_ok,
            "stipend": listing.stipend or "Not specified",
            "match_score": round(match.match_score, 3),
            "justification": match.justification,
            "saved": match.saved,
            "status": match.status,
            "deadline": listing.deadline,
            "source_url": listing.source_url,
        })

    return {"count": len(listings), "is_personal_match": True, "listings": listings[:20]}


# ---------------------------------------------------------------------------
# Tool 2: Search All 970+ Ingested Market Listings
# ---------------------------------------------------------------------------
async def tool_search_all_listings(
    session: AsyncSession,
    *,
    query: str | None = None,
    filter_remote: bool | None = None,
    high_paying_only: bool | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Search across all 970+ ingested job opportunities in PostgreSQL."""
    stmt = select(JobListing).order_by(JobListing.scraped_at.desc())

    if filter_remote is not None:
        stmt = stmt.where(JobListing.remote_ok == filter_remote)

    if query:
        stmt = stmt.where(
            or_(
                JobListing.title.ilike(f"%{query}%"),
                JobListing.company.ilike(f"%{query}%"),
                JobListing.raw_text.ilike(f"%{query}%"),
            )
        )

    result = await session.execute(stmt.limit(100))
    rows = result.scalars().all()

    listings = []
    for j in rows:
        listings.append({
            "title": j.title or "Untitled Role",
            "company": j.company or "Undisclosed",
            "location": j.location or "Remote",
            "remote_ok": j.remote_ok,
            "stipend": j.stipend or "Not specified",
            "skills": j.required_skills or [],
            "source_name": j.source_name,
            "source_url": j.source_url,
            "deadline": j.deadline,
        })

    # Prioritize listings with disclosed salary if high_paying_only or if query asks for salary/pay
    if high_paying_only or (query and any(w in query.lower() for w in ["pay", "salary", "stipend", "high"])):
        listings.sort(
            key=lambda x: (x["stipend"] != "Not specified", x["remote_ok"]),
            reverse=True,
        )

    return {
        "count": len(listings[:limit]),
        "total_in_pool": len(listings),
        "listings": listings[:limit],
    }


# ---------------------------------------------------------------------------
# Tool 3: Top Skills Breakdown
# ---------------------------------------------------------------------------
async def tool_get_top_skills_breakdown(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Aggregate the most frequently required skills across matches or market."""
    stmt = (
        select(JobListing.required_skills)
        .join(UserListingMatch, UserListingMatch.listing_id == JobListing.id)
        .where(UserListingMatch.user_id == user_id)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Fallback to general market skills if no personal matches exist yet
    if not rows:
        market_stmt = select(JobListing.required_skills).limit(300)
        market_res = await session.execute(market_stmt)
        rows = market_res.scalars().all()

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

    return {"total_analyzed": len(rows), "top_skills": top_skills}


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
