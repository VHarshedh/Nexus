"""
Tests for Anti-Detection Stealth Engine and New Scrapers (WWR, Arbeitnow, Remotive).
"""

from __future__ import annotations

import pytest

from app.pipeline.orchestrator import SCRAPER_REGISTRY
from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.base import BaseScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.stealth import (
    DEFAULT_STEALTH_HEADERS,
    STEALTH_INIT_SCRIPT,
    STEALTH_LAUNCH_ARGS,
    HumanBehaviorSimulator,
    StealthEngine,
)
from app.scrapers.weworkremotely import WeWorkRemotelyScraper


def test_scraper_registry_contains_all_five_sources():
    """Verify all 5 scrapers are registered and inherit from BaseScraper."""
    expected_keys = {"remoteok", "github", "weworkremotely", "arbeitnow", "remotive"}
    assert expected_keys.issubset(SCRAPER_REGISTRY.keys())
    for key in expected_keys:
        cls = SCRAPER_REGISTRY[key]
        assert issubclass(cls, BaseScraper)


def test_stealth_engine_configuration():
    """Verify stealth launch args and headers are properly populated."""
    args = StealthEngine.get_launch_args()
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--no-sandbox" in args

    viewport = StealthEngine.get_random_viewport()
    assert "width" in viewport and "height" in viewport
    assert viewport["width"] >= 1366
    assert viewport["height"] >= 768

    assert "Sec-CH-UA" in DEFAULT_STEALTH_HEADERS
    assert DEFAULT_STEALTH_HEADERS["Sec-CH-UA-Platform"] == '"Windows"'


def test_stealth_init_script_contents():
    """Verify JS anti-fingerprint script contains critical evasion methods."""
    assert "navigator.webdriver" in STEALTH_INIT_SCRIPT
    assert "window.chrome" in STEALTH_INIT_SCRIPT
    assert "fakePlugins" in STEALTH_INIT_SCRIPT
    assert "hardwareConcurrency" in STEALTH_INIT_SCRIPT
    assert "UNMASKED_RENDERER_WEBGL" in STEALTH_INIT_SCRIPT
    assert "toDataURL" in STEALTH_INIT_SCRIPT


def test_bezier_curve_interpolation():
    """Verify human simulator's cubic Bézier curve calculation."""
    p0, p1, p2, p3 = 0.0, 33.3, 66.6, 100.0
    start = HumanBehaviorSimulator._cubic_bezier(p0, p1, p2, p3, 0.0)
    mid = HumanBehaviorSimulator._cubic_bezier(p0, p1, p2, p3, 0.5)
    end = HumanBehaviorSimulator._cubic_bezier(p0, p1, p2, p3, 1.0)

    assert pytest.approx(start, abs=1e-3) == 0.0
    assert 40.0 < mid < 60.0
    assert pytest.approx(end, abs=1e-3) == 100.0


@pytest.mark.asyncio
async def test_arbeitnow_scraper_parses_payload(monkeypatch):
    """Verify Arbeitnow scraper parses JSON API responses correctly."""
    mock_payload = {
        "data": [
            {
                "slug": "senior-python-dev-123",
                "title": "Senior Python Developer",
                "company_name": "CloudTech EU",
                "location": "Berlin, Germany",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/senior-python-dev-123",
                "tags": ["Python", "FastAPI", "PostgreSQL"],
                "description": "Building high throughput data pipelines.",
            }
        ]
    }

    class MockResponse:
        def raise_for_status(self): return None
        def json(self): return mock_payload

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, *args, **kwargs): return MockResponse()

    monkeypatch.setattr("app.scrapers.arbeitnow.is_allowed_by_robots", lambda *_: _true())
    monkeypatch.setattr("app.scrapers.arbeitnow.polite_delay", lambda: _none())
    monkeypatch.setattr("app.scrapers.arbeitnow.httpx.AsyncClient", lambda **_: MockClient())

    scraper = ArbeitnowScraper()
    listings = await scraper.scrape()

    assert len(listings) == 1
    assert listings[0].title == "Senior Python Developer"
    assert listings[0].company == "CloudTech EU"
    assert listings[0].remote_ok is True
    assert "FastAPI" in listings[0].required_skills
    assert listings[0].source_name == "arbeitnow"


@pytest.mark.asyncio
async def test_remotive_scraper_parses_payload(monkeypatch):
    """Verify Remotive scraper parses job API responses with stipend data."""
    mock_payload = {
        "jobs": [
            {
                "id": 999,
                "url": "https://remotive.com/remote-jobs/software-dev/full-stack-engineer-999",
                "title": "Staff Full Stack Engineer",
                "company_name": "Nexus Global",
                "candidate_required_location": "Worldwide",
                "salary": "$140,000 - $180,000",
                "tags": ["TypeScript", "Next.js", "Python"],
                "description": "Lead architecture for AI career agents.",
            }
        ]
    }

    class MockResponse:
        def raise_for_status(self): return None
        def json(self): return mock_payload

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, *args, **kwargs): return MockResponse()

    monkeypatch.setattr("app.scrapers.remotive.is_allowed_by_robots", lambda *_: _true())
    monkeypatch.setattr("app.scrapers.remotive.polite_delay", lambda: _none())
    monkeypatch.setattr("app.scrapers.remotive.httpx.AsyncClient", lambda **_: MockClient())

    scraper = RemotiveScraper()
    listings = await scraper.scrape()

    assert len(listings) == 1
    assert listings[0].title == "Staff Full Stack Engineer"
    assert listings[0].company == "Nexus Global"
    assert listings[0].stipend == "$140,000 - $180,000"
    assert listings[0].remote_ok is True
    assert "TypeScript" in listings[0].required_skills
    assert listings[0].source_name == "remotive"


async def _true(): return True
async def _none(): return None
