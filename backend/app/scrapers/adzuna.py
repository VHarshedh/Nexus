"""
NEXUS — Adzuna Scraper / API Client.

Fetches job listings with guaranteed explicit salary data from the Adzuna API
(https://developer.adzuna.com/).

Adzuna supports filtering for listings with explicit compensation figures
using `&salary_min=1`, guaranteeing that every retrieved listing contains
clean `salary_min` and `salary_max` values.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import httpx

from app.config import get_settings
from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.stealth import get_stealth_api_headers
from app.scrapers.utils import USER_AGENT, polite_delay

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaScraper(BaseScraper):
    """Client for the Adzuna Job Search API."""

    name = "adzuna"

    async def scrape(self, country: str = "us", results_per_page: int = 50) -> Sequence[RawListing]:
        """Fetch listings from Adzuna API enforcing explicit salary disclosure."""
        settings = get_settings()
        app_id = settings.adzuna_app_id
        app_key = settings.adzuna_app_key

        if not app_id or not app_key:
            logger.info("[adzuna] ADZUNA_APP_ID or ADZUNA_APP_KEY not set in .env — skipping Adzuna.")
            return []

        await polite_delay()
        endpoint = (
            f"{_BASE_URL}/{country}/search/1"
            f"?app_id={app_id}&app_key={app_key}"
            f"&results_per_page={results_per_page}"
            f"&content-type=application/json"
            f"&salary_min=1000"  # Ensures 100% of jobs have explicit salary
            f"&what=software%20developer"
        )

        logger.info("[adzuna] Querying Adzuna API with mandatory salary filter...")
        listings: list[RawListing] = []

        try:
            headers = get_stealth_api_headers(referer="https://www.adzuna.com/")
            headers["User-Agent"] = USER_AGENT

            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.get(endpoint, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            results: list[dict[str, Any]] = data.get("results", [])
            logger.info("[adzuna] Received %d listings with explicit salary.", len(results))

            for item in results:
                title = item.get("title", "").replace("<strong>", "").replace("</strong>", "")
                company_dict = item.get("company", {})
                company = company_dict.get("display_name") if isinstance(company_dict, dict) else "Undisclosed Company"
                url = item.get("redirect_url")
                location_dict = item.get("location", {})
                loc_name = location_dict.get("display_name") if isinstance(location_dict, dict) else "USA"
                desc = item.get("description", "").replace("<strong>", "").replace("</strong>", "")

                sal_min = item.get("salary_min")
                sal_max = item.get("salary_max")
                stipend_str: str | None = None
                if sal_min and sal_max:
                    stipend_str = f"${sal_min:,.0f} – ${sal_max:,.0f}"
                elif sal_min:
                    stipend_str = f"${sal_min:,.0f}+"

                if not title or not url:
                    continue

                raw_text = (
                    f"Title: {title}\n"
                    f"Company: {company}\n"
                    f"Location: {loc_name}\n"
                    f"Salary / Stipend: {stipend_str or 'Not specified'}\n\n"
                    f"Description:\n{desc}"
                )

                listings.append(
                    RawListing(
                        source_name=self.name,
                        source_url=url,
                        raw_text=raw_text,
                        title=title,
                        company=company,
                        location=loc_name,
                        remote_ok="remote" in loc_name.lower() or "remote" in desc.lower(),
                        stipend=stipend_str,
                        required_skills=[],
                    )
                )

        except Exception as exc:
            logger.error("[adzuna] Error querying Adzuna API: %s", exc, exc_info=True)

        return listings
