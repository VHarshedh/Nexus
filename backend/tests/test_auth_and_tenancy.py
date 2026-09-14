from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest
from jose import jwt

from app.config import get_settings
from app.models import BriefingJob, JobListing, Resume, UserListingMatch
from tests.conftest import authorization


@pytest.mark.integration
async def test_register_login_and_reject_invalid_or_expired_tokens(client, users):
    user_a, _ = users
    login = await client.post("/api/auth/login", json={"email": user_a["email"], "password": "secure-pass-123"})
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert (await client.get("/api/resume/", headers=authorization("invalid"))).status_code == 401
    settings = get_settings()
    expired = jwt.encode({"sub": user_a["user_id"], "exp": 0}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert (await client.get("/api/resume/", headers=authorization(expired))).status_code == 401


@pytest.mark.integration
async def test_tenant_routes_never_expose_or_mutate_another_users_records(client, session_factory, users):
    user_a, user_b = users
    a_id, b_id = uuid.UUID(user_a["user_id"]), uuid.UUID(user_b["user_id"])
    listing_id, match_id, briefing_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with session_factory() as session:
        session.add_all([
            Resume(id=uuid.uuid4(), user_id=b_id, raw_text="private resume", file_path=None, embedding=None),
            JobListing(id=listing_id, source_name="test", source_url=f"https://example.test/{listing_id}", canonical_hash="a" * 64, raw_text="job", title="Private role", company="Nexus", required_skills=[], embedding=None),
            UserListingMatch(id=match_id, user_id=b_id, listing_id=listing_id, match_score=0.9, saved=False, status="pending"),
            BriefingJob(id=briefing_id, user_id=b_id, status="queued"),
        ])
        await session.commit()

    headers = authorization(user_a["access_token"])
    assert (await client.get("/api/resume/", headers=headers)).json() == []
    assert (await client.get("/api/matches/", headers=headers)).json() == []
    assert (await client.patch(f"/api/matches/{match_id}/save", headers=headers)).status_code == 404
    assert (await client.get(f"/api/briefings/{briefing_id}", headers=headers)).status_code == 404

    async with session_factory() as session:
        match = await session.get(UserListingMatch, match_id)
        assert match is not None and match.saved is False


@pytest.mark.integration
async def test_unauthenticated_endpoints_strictly_rejected(client):
    """Verify that all user-scoped API endpoints require authenticated JWT Bearer tokens."""
    unauth_endpoints = [
        ("GET", "/api/resume/"),
        ("POST", "/api/matches/compute"),
        ("GET", "/api/matches/"),
        ("POST", "/api/briefings/generate"),
        ("GET", f"/api/briefings/{uuid.uuid4()}"),
        ("POST", "/api/agent/chat"),
    ]
    for method, path in unauth_endpoints:
        if method == "GET":
            res = await client.get(path)
        elif method == "POST":
            res = await client.post(path, json={})
        assert res.status_code == 401, f"{method} {path} returned {res.status_code}, expected 401"


@pytest.mark.integration
async def test_cross_tenant_url_id_tampering_always_returns_404(client, users):
    """Verify hostile client-provided UUIDs in URLs return 404 without leaking data or mutating state."""
    user_a, _ = users
    headers = authorization(user_a["access_token"])
    random_id = uuid.uuid4()

    # Tampered briefing ID
    res = await client.get(f"/api/briefings/{random_id}", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Briefing job not found."

    # Tampered match ID toggle
    res = await client.patch(f"/api/matches/{random_id}/save", headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Match not found."


@pytest.mark.integration
async def test_google_auth_flow(client, monkeypatch):
    """Verify Google OAuth registers and authenticates users seamlessly."""
    class FakeResponse:
        def __init__(self, status_code: int, data: dict):
            self.status_code = status_code
            self._data = data
            self.text = "mocked"

        def json(self):
            return self._data

    async def fake_get(self, url, params=None):
        if params and params.get("id_token") == "valid-google-jwt":
            return FakeResponse(200, {
                "email": "new.google.user@example.com",
                "email_verified": True,
                "aud": "",
            })
        return FakeResponse(401, {"error": "invalid_token"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    # 1. Invalid token should fail
    fail_res = await client.post("/api/auth/google", json={"credential": "bad-token"})
    assert fail_res.status_code == 401

    # 2. Valid token should register and return JWT
    success_res = await client.post("/api/auth/google", json={"credential": "valid-google-jwt"})
    assert success_res.status_code == 200
    data = success_res.json()
    assert data["email"] == "new.google.user@example.com"
    assert data["is_verified"] is True
    assert "access_token" in data

    # 3. Subsequent call should log in existing user
    login_res = await client.post("/api/auth/google", json={"credential": "valid-google-jwt"})
    assert login_res.status_code == 200
    assert login_res.json()["user_id"] == data["user_id"]

