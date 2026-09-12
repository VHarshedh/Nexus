"""
NEXUS — Arbeitnow Scraper.

Scrapes high-quality tech and engineering jobs from Arbeitnow:
https://www.arbeitnow.com/

Captures:
- Remote and EU/Global engineering roles.
- Pre-parsed skills, tags, and company metadata.
- Clean job descriptions for semantic embedding.
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

_BASE_URL = "https://www.arbeitnow.com"
_API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowScraper(BaseScraper):
    """Scraper for Arbeitnow tech and engineering jobs."""

    name = "arbeitnow"

    async def scrape(self) -> Sequence[RawListing]:
        """Fetch listings from Arbeitnow API with fallback handling."""
        if not await is_allowed_by_robots(_BASE_URL, "/"):
            logger.warning("[arbeitnow] Disallowed by robots.txt — aborting.")
            return []

        await polite_delay()
        logger.info("[arbeitnow] Fetching %s ...", _API_URL)

        listings: list[RawListing] = []

        try:
            headers = get_stealth_api_headers(referer=f"{_BASE_URL}/")
            headers["User-Agent"] = USER_AGENT
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(_API_URL, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            items: list[dict[str, Any]] = data.get("data", [])
            logger.info("[arbeitnow] Received %d raw items from API.", len(items))

            for item in items:
                slug = item.get("slug")
                url = item.get("url") or f"{_BASE_URL}/jobs/{slug}"
                title = item.get("title")
                company = item.get("company_name") or "Undisclosed Company"
                location = item.get("location") or "Remote / Europe"
                remote = bool(item.get("remote", False))
                tags = item.get("tags") or []
                desc = item.get("description") or f"{title} at {company}"

                if not title:
                    continue

                raw_text = (
                    f"Title: {title}\n"
                    f"Company: {company}\n"
                    f"Location: {location}\n"
                    f"Remote: {remote}\n"
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
                    remote_ok=remote,
                    required_skills=tags,
                )
                listings.append(listing)

        except Exception as exc:
            logger.error("[arbeitnow] Error during Arbeitnow scrape: %s", exc, exc_info=True)

        logger.info("[arbeitnow] Successfully scraped %d listings.", len(listings))
        return listings
