"""
NEXUS — Abstract Base Scraper.

Every concrete scraper inherits from ``BaseScraper`` and implements the
``scrape()`` coroutine.  The base class provides:

* A Playwright browser lifecycle (launch → close).
* Shared helpers for dedup checking, polite delays, and robots.txt.
* A ``RawListing`` dataclass for passing scraped data downstream.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence

from playwright.async_api import Browser, Playwright, async_playwright

from app.scrapers.utils import USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class RawListing:
    """
    Intermediate representation of a scraped listing **before** LLM
    extraction.  Only ``source_url``, ``source_name``, and ``raw_text``
    are required; optional pre-parsed fields can be supplied by scrapers
    that consume structured data (e.g., JSON APIs) to skip LLM extraction.
    """

    source_url: str
    source_name: str
    raw_text: str

    # Optional pre-parsed fields (scrapers with structured data may fill these
    # to skip the LLM extractor entirely).
    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote_ok: bool = False
    stipend: str | None = None
    required_skills: list[str] = field(default_factory=list)
    experience_level: str | None = None
    deadline: str | None = None


class BaseScraper(ABC):
    """
    Abstract scraper.  Subclasses implement ``scrape()`` which must return a
    list of ``RawListing`` objects.

    Usage::

        async with RemoteOKScraper() as scraper:
            listings = await scraper.scrape()
    """

    name: str = "base"

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BaseScraper":
        """Launch a headless Chromium browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.info("[%s] Browser launched.", self.name)
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close browser and Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[%s] Browser closed.", self.name)

    @property
    def browser(self) -> Browser:
        assert self._browser is not None, "Scraper must be used as async context manager"
        return self._browser

    async def new_page(self):
        """Create a new browser page with a realistic user-agent."""
        context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
        return await context.new_page()

    @abstractmethod
    async def scrape(self) -> Sequence[RawListing]:
        """
        Scrape the source and return raw listings.

        Subclasses must implement polite delays between page loads and
        respect robots.txt via the utility helpers.
        """
        ...
