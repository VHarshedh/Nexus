"""
NEXUS — RemoteOK Scraper (Source A: Structured JSON API).

RemoteOK exposes a public JSON endpoint at ``https://remoteok.com/api``
that returns all current listings in a single paginated response.  Because
the data is already structured, we can fill most ``RawListing`` fields
directly and only fall back to the LLM extractor for edge-cases where the
JSON payload is incomplete.

Pagination
----------
The API returns **all** listings at once (typically 200–400 results).  We
process them in a single batch — no infinite scroll handling is needed.

Rate Limiting
-------------
We add a polite delay before the API call and respect ``robots.txt``.
"""

from __future__ import annotations

import json
import logging
from typing import Sequence

import httpx

from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.utils import (
    USER_AGENT,
    is_allowed_by_robots,
    polite_delay,
)

logger = logging.getLogger(__name__)

_API_URL = "https://remoteok.com/api"
_BASE_URL = "https://remoteok.com"


class RemoteOKScraper(BaseScraper):
    """
    Scrape RemoteOK via its public JSON API.

    The first element of the JSON array is a metadata/legal notice object
    which we skip.  Every subsequent element is a job listing.
    """

    name = "remoteok"

    async def scrape(self) -> Sequence[RawListing]:
        # ── robots.txt check ─────────────────────────────────────────────
        if not await is_allowed_by_robots(_BASE_URL, "/api"):
            logger.warning("robots.txt disallows /api — aborting RemoteOK scrape.")
            return []

        await polite_delay()

        # ── Fetch JSON ───────────────────────────────────────────────────
        logger.info("[remoteok] Fetching %s …", _API_URL)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    _API_URL,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                    follow_redirects=True,
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("[remoteok] HTTP error: %s", exc)
            return []

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("[remoteok] JSON decode error: %s", exc)
            return []

        if not isinstance(data, list) or len(data) < 2:
            logger.warning("[remoteok] Unexpected payload shape — aborting.")
            return []

        # ── Parse listings (skip element 0 = legal notice) ───────────────
        listings: list[RawListing] = []
        for item in data[1:]:
            if not isinstance(item, dict):
                continue

            slug = item.get("slug", "")
            job_id = item.get("id", "")
            url = item.get("url") or f"{_BASE_URL}/remote-jobs/{slug}-{job_id}"
            title = item.get("position", "") or ""
            company = item.get("company", "") or ""

            if not title and not company:
                continue  # skip empty listings

            # Build a human-readable raw_text blob for the LLM / embedding
            tags = item.get("tags", []) or []
            description = item.get("description", "") or ""
            location = item.get("location", "") or "Remote"

            raw_parts = [
                f"Title: {title}",
                f"Company: {company}",
                f"Location: {location}",
                f"Tags: {', '.join(tags)}" if tags else "",
                f"Salary: {item.get('salary_min', '')} – {item.get('salary_max', '')}".strip(" –"),
                "",
                description,
            ]
            raw_text = "\n".join(p for p in raw_parts if p).strip()

            # Determine salary / stipend string
            sal_min = item.get("salary_min")
            sal_max = item.get("salary_max")
            stipend: str | None = None
            if sal_min or sal_max:
                stipend = f"${sal_min or '?'} – ${sal_max or '?'}"

            listings.append(
                RawListing(
                    source_url=url,
                    source_name="remoteok",
                    raw_text=raw_text,
                    title=title,
                    company=company,
                    location=location,
                    remote_ok=True,  # every listing on RemoteOK is remote
                    stipend=stipend,
                    required_skills=tags,
                    experience_level=None,  # not in the API payload
                    deadline=None,
                )
            )

        logger.info("[remoteok] Scraped %d listings.", len(listings))
        return listings
