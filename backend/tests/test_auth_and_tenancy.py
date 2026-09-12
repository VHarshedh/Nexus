from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
