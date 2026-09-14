"""
Tests for Scheduled Runs, Change Detection, and Takedown Health Checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models.job_listing import JobListing
from app.models.user import User
from app.models.user_listing_match import UserListingMatch
from app.pipeline.orchestrator import _process_listing
from app.scrapers.base import RawListing
from app.services.scheduler import check_saved_listings_health, run_scheduled_pipeline


@pytest.mark.asyncio
async def test_orchestrator_detects_field_changes_and_sets_alert(monkeypatch):
    """When a known listing changes compensation or remote status, update fields and alert saved users."""
    existing_id = uuid.uuid4()
    user_id = uuid.uuid4()
    canonical_hash = "test-hash-123"

    fake_listing = JobListing(
        id=existing_id,
        source_name="RemoteOK",
        source_url="https://remoteok.com/jobs/123",
        canonical_hash=canonical_hash,
        raw_text="Initial listing text",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Worldwide",
        remote_ok=True,
        stipend="$120k",
        deadline="2026-10-01",
        is_active=True,
    )

    fake_user = User(
        id=user_id,
        email="candidate@example.com",
        is_verified=True,
    )

    fake_match = UserListingMatch(
        id=uuid.uuid4(),
        user_id=user_id,
        listing_id=existing_id,
        match_score=0.92,
        saved=True,
        status="pending",
        change_alert=None,
    )

    email_sent = []

    async def mock_send_email(**kwargs):
        email_sent.append(kwargs)
        return True

    monkeypatch.setattr("app.pipeline.orchestrator.send_job_change_alert_email", mock_send_email)
    monkeypatch.setattr("app.pipeline.orchestrator.compute_canonical_hash", lambda *_: canonical_hash)

    # Mock DB session execution
    class MockResult:
        def __init__(self, item):
            self._item = item
        def scalar_one_or_none(self):
            return self._item
        def scalars(self):
            class S:
                def all(_):
                    return [fake_match] if self._item == fake_match else []
            return S()

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def execute(self, stmt):
            stmt_str = str(stmt)
            if "FROM job_listings" in stmt_str:
                return MockResult(fake_listing)
            elif "FROM user_listing_matches" in stmt_str:
                return MockResult(fake_match)
            elif "FROM users" in stmt_str:
                return MockResult(fake_user)
            return MockResult(None)
        async def commit(self):
            pass
        def add(self, _):
            pass

    monkeypatch.setattr("app.pipeline.orchestrator.get_session", lambda: MockSession())

    raw = RawListing(
        source_name="RemoteOK",
        source_url="https://remoteok.com/jobs/123",
        raw_text="Updated text",
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Worldwide",
        remote_ok=False,  # Changed from True -> False
        stipend="$150k",  # Changed from $120k -> $150k
        deadline="2026-11-01",  # Changed
    )

    stats = {"scraped": 1, "new": 0, "updated": 0, "failed": 0}
    await _process_listing(raw, extractor=None, skip_embeddings=True, stats=stats)

    # Verify listing fields updated
    assert fake_listing.stipend == "$150k"
    assert fake_listing.remote_ok is False
    assert fake_listing.deadline == "2026-11-01"

    # Verify match alert was populated
    assert fake_match.change_alert is not None
    assert "Compensation updated" in fake_match.change_alert
    assert "Remote policy updated" in fake_match.change_alert
    assert fake_match.change_alert_at is not None

    # Verify email dispatched
    assert len(email_sent) == 1
    assert email_sent[0]["to_email"] == "candidate@example.com"
    assert email_sent[0]["job_title"] == "Senior Backend Engineer"


@pytest.mark.asyncio
async def test_health_check_detects_takedown_and_marks_inactive(monkeypatch):
    """When a saved listing returns 404 on health check, mark is_active=False and alert candidate."""
    listing_id = uuid.uuid4()
    user_id = uuid.uuid4()

    fake_listing = JobListing(
        id=listing_id,
        source_name="RemoteOK",
        source_url="https://remoteok.com/jobs/404-role",
        canonical_hash="dead-hash",
        raw_text="Expired job",
        title="Staff Engineer",
        company="Gone Corp",
        is_active=True,
    )

    fake_user = User(
        id=user_id,
        email="shortlisted@example.com",
        is_verified=True,
    )

    fake_match = UserListingMatch(
        id=uuid.uuid4(),
        user_id=user_id,
        listing_id=listing_id,
        saved=True,
        user=fake_user,
    )

    takedown_emails = []

    async def mock_takedown_email(**kwargs):
        takedown_emails.append(kwargs)
        return True

    monkeypatch.setattr("app.services.scheduler.send_job_takedown_alert_email", mock_takedown_email)

    class MockResult:
        def __init__(self, items):
            self._items = items
        def scalars(self):
            class S:
                def all(_):
                    return self._items
            return S()

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def execute(self, stmt):
            stmt_str = str(stmt)
            if "FROM job_listings" in stmt_str:
                return MockResult([fake_listing])
            elif "FROM user_listing_matches" in stmt_str:
                return MockResult([fake_match])
            return MockResult([])

    monkeypatch.setattr("app.services.scheduler.get_session", lambda: MockSession())

    # Mock HTTP response to return 404
    class MockResponse:
        status_code = 404
        text = "404 Not Found"

    class MockHttpClient:
        async def get(self, url, **kwargs):
            return MockResponse()

    stats = await check_saved_listings_health(client=MockHttpClient())

    assert stats["checked"] == 1
    assert stats["taken_down"] == 1
    assert stats["alerts_dispatched"] == 1
    assert fake_listing.is_active is False
    assert fake_listing.taken_down_at is not None
    assert "Listing taken down or closed" in fake_match.change_alert
    assert len(takedown_emails) == 1
    assert takedown_emails[0]["to_email"] == "shortlisted@example.com"


@pytest.mark.asyncio
async def test_run_scheduled_pipeline_orchestrates_phases(monkeypatch):
    """Verify run_scheduled_pipeline coordinates health check, scrape, and match refresh."""
    phases_run = []

    async def mock_hc():
        phases_run.append("health_check")
        return {"checked": 5, "taken_down": 1}

    async def mock_scrape(**_kwargs):
        phases_run.append("scraper")
        return {"scraped": 20, "new": 5, "updated": 15, "failed": 0}

    async def mock_refresh():
        phases_run.append("match_refresh")
        return {"users_refreshed": 3, "total_matches": 15}

    monkeypatch.setattr("app.services.scheduler.check_saved_listings_health", mock_hc)
    monkeypatch.setattr("app.services.scheduler.run_scrape_pipeline", mock_scrape)
    monkeypatch.setattr("app.services.scheduler.refresh_all_user_matches", mock_refresh)

    report = await run_scheduled_pipeline(
        run_scraper=True,
        run_health_check=True,
        run_match_refresh=True,
        skip_embeddings=True,
    )

    assert phases_run == ["health_check", "scraper", "match_refresh"]
    assert report["health_check"]["taken_down"] == 1
    assert report["scraper"]["new"] == 5
    assert report["match_refresh"]["users_refreshed"] == 3


@pytest.mark.asyncio
async def test_cron_endpoint_auth_and_execution(monkeypatch):
    """Verify that /api/system/cron-run respects secret token authentication and triggers pipeline."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "cron_secret", "secret123")

    called = []
    async def mock_pipeline(**_kwargs):
        called.append(True)
        return {"status": "ok"}

    monkeypatch.setattr("app.api.system.run_scheduled_pipeline", mock_pipeline)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthorized without token
        unauth_resp = await ac.post("/api/system/cron-run")
        assert unauth_resp.status_code == 401

        # Authorized via query param
        auth_query_resp = await ac.get("/api/system/cron-run?token=secret123")
        assert auth_query_resp.status_code == 200
        assert auth_query_resp.json()["status"] == "accepted"

        # Authorized via header
        auth_hdr_resp = await ac.post(
            "/api/system/cron-run",
            headers={"X-Cron-Secret": "secret123"},
        )
        assert auth_hdr_resp.status_code == 200

