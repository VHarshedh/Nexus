from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.agent.tools import tool_get_deadline_alerts, tool_get_top_skills_breakdown, tool_query_saved_listings


class Result:
    def __init__(self, rows): self.rows = rows
    def all(self): return self.rows
    def scalars(self): return self


class Session:
    def __init__(self, rows): self.rows = rows; self.statements = []
    async def execute(self, statement):
        self.statements.append(statement)
        return Result(self.rows)


@pytest.mark.asyncio
async def test_agent_tools_filter_and_return_json_safe_structures():
    user_id = uuid.uuid4()
    deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    listing = SimpleNamespace(title="Engineer", company="Nexus", location="Remote", remote_ok=True, stipend=None, required_skills=["Python", "SQL"], deadline=deadline, source_url="https://example.test")
    match = SimpleNamespace(match_score=0.82, justification="Python fit", saved=True, status="pending")
    saved = await tool_query_saved_listings(user_id, Session([(match, listing)]), filter_remote=True)
    skills = await tool_get_top_skills_breakdown(user_id, Session([["Python", "SQL", "Python"]]))
    alerts = await tool_get_deadline_alerts(user_id, Session([(match, listing)]), days_ahead=7)
    assert saved["count"] == 1 and saved["listings"][0]["saved"] is True
    assert skills["top_skills"][0] == {"skill": "python", "count": 2}
    assert alerts["urgent_count"] == 1


@pytest.mark.asyncio
async def test_gemini_function_call_is_dispatched_and_returned_to_model(monkeypatch):
    """Exercise the agent loop without a network call to Gemini."""
    from app.agent import career_agent

    function_call = SimpleNamespace(name="get_top_skills_breakdown", args={})
    function_part = SimpleNamespace(function_call=function_call, text=None)
    text_part = SimpleNamespace(function_call=None, text="Python is your top skill.")
    responses = iter([
        SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[function_part]))]),
        SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[text_part]))]),
    ])

    class Models:
        async def generate_content(self, **_kwargs): return next(responses)

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    monkeypatch.setattr(career_agent.genai, "Client", lambda **_kwargs: client)
    dispatched = []

    async def fake_dispatch(name, args, user_id, session):
        dispatched.append((name, args, user_id, session))
        return {"total_matches": 1, "top_skills": [{"skill": "python", "count": 1}]}

    monkeypatch.setattr(career_agent, "_dispatch_tool", fake_dispatch)
    user_id = uuid.uuid4()
    reply, tool_calls = await career_agent.run_agent_turn(user_id, [], "What skills are in demand?", object())
    assert reply == "Python is your top skill."
    assert tool_calls == ["get_top_skills_breakdown"]
    assert dispatched[0][:3] == ("get_top_skills_breakdown", {}, user_id)


@pytest.mark.asyncio
async def test_agent_tools_enforce_user_id_in_sql_predicates():
    """Verify that every tool querying personal data enforces user_id in the SQL WHERE clause."""
    from app.agent.tools import (
        tool_get_deadline_alerts,
        tool_get_top_skills_breakdown,
        tool_query_saved_listings,
    )

    user_id = uuid.uuid4()
    session = Session([])

    await tool_query_saved_listings(user_id, session)
    stmt_sql = str(session.statements[0])
    assert "user_listing_matches.user_id = :user_id_1" in stmt_sql

    session = Session([])
    await tool_get_top_skills_breakdown(user_id, session)
    stmt_sql = str(session.statements[0])
    assert "user_listing_matches.user_id = :user_id_1" in stmt_sql

    session = Session([])
    await tool_get_deadline_alerts(user_id, session)
    stmt_sql = str(session.statements[0])
    assert "user_listing_matches.user_id = :user_id_1" in stmt_sql


@pytest.mark.asyncio
async def test_tool_search_all_listings_filtering():
    """Verify tool_search_all_listings handles query, remote filter, and high paying priority."""
    from app.agent.tools import tool_search_all_listings

    jobs = [
        SimpleNamespace(
            title="Senior Go Developer",
            company="CloudCorp",
            location="Remote",
            remote_ok=True,
            stipend="$150k - $180k",
            required_skills=["Go", "Kubernetes"],
            source_name="weworkremotely",
            source_url="https://example.test/1",
            deadline="2026-10-01",
        ),
        SimpleNamespace(
            title="Junior Analyst",
            company="DataInc",
            location="NYC",
            remote_ok=False,
            stipend="Not specified",
            required_skills=["Excel"],
            source_name="remoteok",
            source_url="https://example.test/2",
            deadline=None,
        ),
    ]

    session = Session(jobs)
    res = await tool_search_all_listings(session, query="Go", filter_remote=True, high_paying_only=True)
    assert res["count"] == 2
    assert res["listings"][0]["title"] == "Senior Go Developer"
    assert res["listings"][0]["stipend"] == "$150k - $180k"

