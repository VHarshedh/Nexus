"""
NEXUS — GitHub "Who is Hiring?" Scraper (Source B: Raw Markdown).

Scrapes monthly "Who is Hiring?" threads from Hacker News (rendered via the
HN Algolia API / web).  Each top-level comment in these threads is typically a
single job posting in **unstructured, free-form text** — an ideal candidate
for LLM-powered structured extraction.

This scraper uses Playwright to:
1. Navigate to the latest "Ask HN: Who is hiring?" thread.
2. Load all comments (pagination / "More" button handling).
3. Extract each top-level comment body as a ``RawListing``.

Because the comment text is unstructured, the ``RawListing.title`` and
``RawListing.company`` fields are left ``None`` — the LLM extractor
(``pipeline/extractor.py``) is responsible for parsing them.

Pagination
----------
HN threads paginate with a "More" link at the bottom.  We follow it up to
a configurable maximum number of pages (default: 5) to avoid unbounded
crawls.

Rate Limiting
-------------
A polite delay is inserted between every page load.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence
from urllib.parse import urljoin

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, RawListing
from app.scrapers.utils import is_allowed_by_robots, polite_delay

logger = logging.getLogger(__name__)

# HN search for the latest "Who is hiring?" thread (sorted by date)
_SEARCH_URL = (
    "https://hn.algolia.com/api/v1/search?"
    "query=%22Ask%20HN%3A%20Who%20is%20hiring%22&tags=ask_hn"
    "&hitsPerPage=1"
)
_HN_ITEM_BASE = "https://news.ycombinator.com/item?id="
_MAX_PAGES = 5  # max "More" pages to follow


class GitHubHiringScraper(BaseScraper):
    """
    Scrape the latest Hacker News "Who is hiring?" thread.

    Despite the class name referencing "GitHub Hiring" (matching the
    original spec), HN "Who is hiring?" threads are the canonical
    structured-text hiring board on the open web.
    """

    name = "github_hiring"

    async def _find_latest_thread_url(self) -> str | None:
        """Use Algolia API to find the latest 'Who is hiring?' thread ID."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_SEARCH_URL)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("[github_hiring] Algolia search failed: %s", exc)
            return None

        hits = data.get("hits", [])
        if not hits:
            logger.warning("[github_hiring] No 'Who is hiring?' threads found.")
            return None

        thread_id = hits[0].get("objectID")
        if not thread_id:
            return None

        url = f"{_HN_ITEM_BASE}{thread_id}"
        logger.info("[github_hiring] Latest thread: %s", url)
        return url

    async def _load_all_comments(self, page: Page) -> None:
        """Click the 'More' link repeatedly to load additional comment pages."""
        for page_num in range(1, _MAX_PAGES):
            try:
                more_link = page.locator("a.morelink")
                if await more_link.count() == 0:
                    break
                logger.debug("[github_hiring] Loading page %d …", page_num + 1)
                await polite_delay()
                await more_link.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except PlaywrightTimeout:
                logger.debug("[github_hiring] No more pages to load.")
                break
            except Exception as exc:
                logger.warning("[github_hiring] Pagination error: %s", exc)
                break

    async def scrape(self) -> Sequence[RawListing]:
        # ── robots.txt ───────────────────────────────────────────────────
        if not await is_allowed_by_robots("https://news.ycombinator.com", "/item"):
            logger.warning("robots.txt disallows /item — aborting.")
            return []

        # ── Find latest thread ───────────────────────────────────────────
        thread_url = await self._find_latest_thread_url()
        if not thread_url:
            return []

        await polite_delay()

        # ── Load thread in Playwright ────────────────────────────────────
        page = await self.new_page()
        try:
            await page.goto(thread_url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeout:
            logger.error("[github_hiring] Timeout loading thread page.")
            return []

        # ── Paginate ─────────────────────────────────────────────────────
        await self._load_all_comments(page)

        # ── Extract top-level comments ───────────────────────────────────
        # Top-level comments on HN have indent level 0 (class "ind" with
        # width=0). Each comment row has class "athing comtr".
        comments = await page.locator(".athing.comtr").all()
        logger.info("[github_hiring] Found %d total comments.", len(comments))

        listings: list[RawListing] = []
        for comment in comments:
            try:
                # Check indent — top-level comments have indent img width == 0
                indent_el = comment.locator("td.ind img")
                if await indent_el.count() > 0:
                    width = await indent_el.get_attribute("width")
                    if width and int(width) > 0:
                        continue  # skip replies

                # Extract comment text
                comment_span = comment.locator(".commtext")
                if await comment_span.count() == 0:
                    continue

                text = await comment_span.inner_text()
                text = text.strip()
                if len(text) < 30:
                    continue  # skip very short / empty comments

                # Build a permalink
                comment_id_attr = await comment.get_attribute("id")
                permalink = f"{_HN_ITEM_BASE}{comment_id_attr}" if comment_id_attr else thread_url

                listings.append(
                    RawListing(
                        source_url=permalink,
                        source_name="hn_who_is_hiring",
                        raw_text=text,
                        # title / company / etc. are unknown — LLM extractor
                        # will parse them from the raw text.
                    )
                )

            except Exception as exc:
                logger.debug("[github_hiring] Skipping comment: %s", exc)
                continue

        await page.close()
        logger.info("[github_hiring] Scraped %d top-level job postings.", len(listings))
        return listings
