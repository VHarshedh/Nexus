"""
NEXUS — Remotive Scraper.

Scrapes high-quality remote software development, DevOps, and cloud roles
from Remotive: https://remotive.com/

Captures:
- Real-time global tech job listings.
- Salary and stipend compensation data where available.
- Technical skills, candidate location constraints, and job descriptions.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import httpx

from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.stealth import get_stealth_api_headers
from app.scrapers.utils import (
    USER_AGENT,
    is_allowed_by_robots,
    polite_delay,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://remotive.com"
_API_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=60"


class RemotiveScraper(BaseScraper):
    """Scraper for Remotive software engineering and cloud positions."""

    name = "remotive"

    async def scrape(self) -> Sequence[RawListing]:
        """Fetch listings from Remotive API and parse into RawListing objects."""
        if not await is_allowed_by_robots(_BASE_URL, "/"):
            logger.warning("[remotive] Disallowed by robots.txt — aborting.")
            return []

        await polite_delay()
        logger.info("[remotive] Fetching %s ...", _API_URL)

        listings: list[RawListing] = []

        try:
            headers = get_stealth_api_headers(referer=f"{_BASE_URL}/")
            headers["User-Agent"] = USER_AGENT
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(_API_URL, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            jobs: list[dict[str, Any]] = data.get("jobs", [])
            logger.info("[remotive] Received %d raw jobs from API.", len(jobs))

            for job in jobs:
                title = job.get("title")
                company = job.get("company_name") or "Undisclosed Company"
                url = job.get("url")
                location = job.get("candidate_required_location") or "Worldwide / Remote"
                salary = job.get("salary") or None
                tags = job.get("tags") or []
                desc = job.get("description") or f"{title} at {company}"

                if not title or not url:
                    continue

                raw_text = (
                    f"Title: {title}\n"
                    f"Company: {company}\n"
                    f"Location: {location}\n"
                    f"Salary: {salary or 'Not specified'}\n"
                    f"Tags: {', '.join(tags)}\n\n"
                    f"Description:\n{desc[:3000]}"
                )

                listing = RawListing(
                    source_name=self.name,
                    source_url=url,
                    raw_text=raw_text,
                    title=title,
                    company=company,
                    location=location,
                    remote_ok=True,
                    stipend=salary,
                    required_skills=tags,
                )
                listings.append(listing)

        except Exception as exc:
            logger.error("[remotive] Error during Remotive scrape: %s", exc, exc_info=True)

        logger.info("[remotive] Successfully scraped %d listings.", len(listings))
        return listings
