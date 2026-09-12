"""Shared fixtures for NEXUS backend tests.

Integration tests intentionally require ``NEXUS_TEST_DATABASE_URL``.  This
prevents a test run from ever pointing at a developer's production database.
Use a separate disposable PostgreSQL database with pgvector enabled.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import get_db_session
from app.main import app
from app.models import Base


TEST_DATABASE_URL = os.getenv("NEXUS_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
async def test_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("Set NEXUS_TEST_DATABASE_URL to run PostgreSQL integration tests.")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def client(session_factory) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
async def users(client):
    async def register(email: str) -> dict[str, str]:
        response = await client.post(
            "/api/auth/register", json={"email": email, "password": "secure-pass-123"}
        )
        assert response.status_code == 201, response.text
        return response.json()

    user_a = await register("user-a@example.test")
    user_b = await register("user-b@example.test")
    return user_a, user_b


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
