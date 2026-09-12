from __future__ import annotations

import pytest

from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.utils import compute_canonical_hash


@pytest.mark.asyncio
async def test_remoteok_parses_structured_listing(monkeypatch):
    payload = [
        {"legal": "notice"},
        {"id": "42", "slug": "python-engineer", "position": "Python Engineer", "company": "Nexus", "tags": ["Python", "FastAPI"], "description": "Build APIs", "location": "Worldwide"},
    ]

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return payload

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def get(self, *_args, **_kwargs): return Response()

    monkeypatch.setattr("app.scrapers.remoteok.is_allowed_by_robots", lambda *_args: _true())
    monkeypatch.setattr("app.scrapers.remoteok.polite_delay", lambda: _none())
    monkeypatch.setattr("app.scrapers.remoteok.httpx.AsyncClient", lambda **_kwargs: Client())
    listings = await RemoteOKScraper().scrape()
    assert len(listings) == 1
    assert listings[0].title == "Python Engineer"
    assert listings[0].required_skills == ["Python", "FastAPI"]
    assert listings[0].remote_ok is True


async def _true(): return True
async def _none(): return None


def test_canonical_hash_normalizes_tracking_fragments_and_case():
    first = compute_canonical_hash("HTTPS://jobs.example.com/role/?utm_source=email&b=2#apply", " Engineer ", "NEXUS")
    second = compute_canonical_hash("https://jobs.example.com/role?b=2", "engineer", "nexus")
    assert first == second
    assert first != compute_canonical_hash("https://jobs.example.com/role?b=2", "designer", "nexus")
