"""
NEXUS — We Work Remotely (WWR) Scraper.

Scrapes premier global remote tech roles from We Work Remotely (WWR):
https://weworkremotely.com/categories/remote-programming-jobs

Utilizes:
- Full stealth Playwright browser context (anti-fingerprinting, masked WebGL/canvas).
- Human reading scroll simulation to load dynamic listings organically.
- Robots.txt compliance and polite jitter delay.
"""

from __future__ import annotations

import logging
from typing import Sequence
from urllib.parse import urljoin

from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.utils import is_allowed_by_robots, polite_delay

logger = logging.getLogger(__name__)

_BASE_URL = "https://weworkremotely.com"
_TARGET_CATEGORIES = [
    "/categories/remote-programming-jobs",
    "/categories/remote-devops-sysadmin-jobs",
]


class WeWorkRemotelyScraper(BaseScraper):
    """Scraper for We Work Remotely programming and DevOps job categories."""

    name = "weworkremotely"

    async def scrape(self) -> Sequence[RawListing]:
        """Navigate category pages, simulate human interaction, and collect job listings."""
        # 1. robots.txt check
        if not await is_allowed_by_robots(_BASE_URL, "/categories"):
            logger.warning("[weworkremotely] Disallowed by robots.txt — aborting.")
            return []

        listings: list[RawListing] = []
        page = await self.new_page()

        try:
            for category_path in _TARGET_CATEGORIES:
                target_url = urljoin(_BASE_URL, category_path)
                logger.info("[weworkremotely] Fetching %s ...", target_url)

                await polite_delay()
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)

                # Simulate human interaction: reading scroll
                await self.human.human_scroll(page, total_distance=900, pause_probability=0.3)

                # Extract job list items
                # WWR lists jobs inside `section.jobs li:not(.view-all)`
                job_elements = await page.locator("section.jobs li:not(.view-all):not(.ad)").all()
                logger.info("[weworkremotely] Found %d candidate items in %s.", len(job_elements), category_path)

                for el in job_elements:
                    try:
                        # 1. Find link (resilient fallbacks)
                        link_el = el.locator("a[href*='/remote-jobs/']").first
                        if await link_el.count() == 0:
                            link_el = el.locator("a[href*='/jobs/']").first
                        if await link_el.count() == 0:
                            link_el = el.locator("a[href^='/']").first
                        if await link_el.count() == 0:
                            link_el = el.locator("a").first

                        if await link_el.count() == 0:
                            continue

                        href = await link_el.get_attribute("href")
                        if not href or href == "#" or "javascript:" in href:
                            continue
                        job_url = urljoin(_BASE_URL, href)

                        # 2. Extract Title (adaptive across span, h3, h4, classes)
                        title = None
                        for sel in [".title", "span.title", "h3", "h4", ".listing-title"]:
                            t_el = el.locator(sel).first
                            if await t_el.count() > 0:
                                text = (await t_el.text_content() or "").strip()
                                if text and len(text) > 2:
                                    title = text
                                    break

                        if not title:
                            # Fallback to first line of link text
                            all_text = (await link_el.text_content() or "").strip()
                            lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
                            if lines:
                                title = lines[0]

                        if not title or len(title) < 2:
                            continue

                        # 3. Extract Company
                        company = None
                        for sel in [".company", "span.company", ".listing-company"]:
                            c_el = el.locator(sel).first
                            if await c_el.count() > 0:
                                text = (await c_el.text_content() or "").strip()
                                if text and text != title:
                                    company = text
                                    break
                        if not company:
                            company = "Undisclosed Company"

                        # 4. Extract Region / Location
                        region = None
                        for sel in [".region", "span.region", ".listing-region", ".location"]:
                            r_el = el.locator(sel).first
                            if await r_el.count() > 0:
                                text = (await r_el.text_content() or "").strip()
                                if text:
                                    region = text
                                    break
                        if not region:
                            region = "Remote / Worldwide"

                        # 5. Extract Tags
                        tag_elements = await el.locator(".listing-tag, .tag, .badge").all()
                        tags: list[str] = []
                        for t in tag_elements:
                            tag_text = (await t.text_content() or "").strip()
                            if tag_text and tag_text not in tags:
                                tags.append(tag_text)

                        raw_text = (
                            f"Title: {title}\n"
                            f"Company: {company}\n"
                            f"Location: {region}\n"
                            f"Tags: {', '.join(tags)}\n"
                            f"Source: We Work Remotely ({category_path})"
                        )

                        listing = RawListing(
                            source_name=self.name,
                            source_url=job_url,
                            raw_text=raw_text,
                            title=title,
                            company=company,
                            location=region,
                            remote_ok=True,
                            required_skills=tags,
                        )
                        listings.append(listing)

                    except Exception as item_err:
                        logger.debug("[weworkremotely] Error parsing card: %s", item_err)
                        continue

        except Exception as exc:
            logger.error("[weworkremotely] Error during scraping: %s", exc, exc_info=True)
        finally:
            await page.close()

        logger.info("[weworkremotely] Successfully scraped %d listings.", len(listings))
        return listings
