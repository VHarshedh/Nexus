from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import briefing


@pytest.mark.asyncio
async def test_pipeline_uses_independent_sessions_and_edge_tts_fallback(monkeypatch):
    job = SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), status="queued", script=None,
        media_url=None, error_message=None, completed_at=None,
    )
    sessions = []

    class Result:
        def scalar_one_or_none(self): return job

    class Session:
        async def execute(self, _statement): return Result()

    @asynccontextmanager
    async def fake_get_session():
        sessions.append(Session())
        yield sessions[-1]

    output = Path("briefing.mp3")
    async def fake_script(_user_id): return "Your NEXUS update."
    async def fake_tts(_script, path):
        assert path.name == f"{job.id}.mp3"
        return output

    monkeypatch.setattr(briefing, "get_session", fake_get_session)
    monkeypatch.setattr(briefing, "generate_briefing_script", fake_script)
    monkeypatch.setattr(briefing, "synthesize_audio_edge_tts", fake_tts)
    monkeypatch.setattr(briefing, "get_settings", lambda: SimpleNamespace(heygen_api_key="", upload_dir=Path(".")))
    await briefing.run_briefing_pipeline(job.id)
    assert len(sessions) >= 3
    assert job.status == "done"
    assert job.media_url and job.media_url.endswith(".mp3")


@pytest.mark.integration
async def test_generate_returns_accepted_without_running_work_inline(client, users, monkeypatch):
    # BackgroundTasks are awaited by ASGI test transports, so replace only the
    # thread wrapper; this asserts queuing semantics without network calls.
    from app.api import briefings
    monkeypatch.setattr(briefings, "_run_async_pipeline", lambda _job_id: None)
    user_a, _ = users
    response = await client.post("/api/briefings/generate", headers={"Authorization": f"Bearer {user_a['access_token']}"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
