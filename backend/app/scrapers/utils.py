"""
NEXUS — Scraper Utilities.

Shared helpers used by every scraper implementation:

* **Canonical hashing** for deduplication (see docstring on
  ``compute_canonical_hash``).
* **robots.txt** compliance checker.
* **Polite delay** with random jitter.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Deduplication Hashing ───────────────────────────────────────────────────
def compute_canonical_hash(source_url: str, title: str, company: str) -> str:
    """
    Compute a deterministic SHA-256 hash for deduplication.

    Strategy
    --------
    We concatenate three normalised fields separated by ``||``:

        SHA-256( normalised_url || lower(title) || lower(company) )

    *Why these three?*
    - ``source_url`` uniquely identifies a listing on a given board.
    - ``title + company`` catches re-posts under a different URL on the
      same or a different board.

    The hash is stored in ``job_listings.canonical_hash`` (indexed) and is
    checked **before** running the expensive LLM extraction + embedding
    pipeline.  If a matching hash already exists we simply bump
    ``scraped_at`` to prove the listing is still live and skip re-processing.

    Parameters
    ----------
    source_url : str
        The original URL of the listing.
    title : str
        Job title (will be lowercased + stripped).
    company : str
        Company name (will be lowercased + stripped).

    Returns
    -------
    str
        64-character hex SHA-256 digest.
    """
    # A fragment is never sent to a server and common tracking parameters do
    # not identify a job.  Removing them prevents a board's campaign links
    # from charging us for duplicate extraction/embedding work.  Other query
    # parameters are preserved because some boards use them as a job ID.
    parsed = urlsplit(source_url.strip())
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}
        ),
        doseq=True,
    )
    normalised_url = urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/").lower(), query, "")
    )
    normalised_title = (title or "").strip().lower()
    normalised_company = (company or "").strip().lower()
    payload = f"{normalised_url}||{normalised_title}||{normalised_company}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ─── Robots.txt Compliance ───────────────────────────────────────────────────
async def is_allowed_by_robots(base_url: str, path: str = "/") -> bool:
    """
    Check whether our user-agent is allowed to fetch ``path`` according to
    the site's ``robots.txt``.

    Returns ``True`` (allow) if ``robots.txt`` cannot be fetched (404, timeout,
    parse error) — we err on the side of scraping but log a warning.
    """
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(robots_url, follow_redirects=True)
            if resp.status_code != 200:
                logger.warning(
                    "robots.txt returned %s for %s — assuming allowed.",
                    resp.status_code,
                    robots_url,
                )
                return True

        # Simple parser: look for Disallow lines under User-agent: *
        lines = resp.text.splitlines()
        in_wildcard_block = False
        for line in lines:
            line = line.strip()
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_wildcard_block = agent == "*"
            elif in_wildcard_block and line.lower().startswith("disallow:"):
                disallowed = line.split(":", 1)[1].strip()
                if disallowed and path.startswith(disallowed):
                    logger.info(
                        "robots.txt disallows %s on %s", path, parsed.netloc
                    )
                    return False
        return True
    except Exception as exc:
        logger.warning("Could not fetch robots.txt for %s: %s", base_url, exc)
        return True


# ─── Polite Delay ────────────────────────────────────────────────────────────
async def polite_delay() -> None:
    """
    Sleep for a random duration between ``SCRAPE_DELAY_MIN`` and
    ``SCRAPE_DELAY_MAX`` (from settings).  Adds ±15 % jitter on top to
    avoid deterministic request patterns.
    """
    settings = get_settings()
    base = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
    jitter = base * random.uniform(-0.15, 0.15)
    delay = max(0.5, base + jitter)
    logger.debug("Polite delay: %.2fs", delay)
    await asyncio.sleep(delay)


# ─── Constants ───────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 "
    "NexusCareerBot/1.0 (+https://github.com/nexus-career-agent)"
)
