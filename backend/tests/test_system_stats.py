from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.api.system import get_system_stats, live_command_center


class MockScalarResult:
    def __init__(self, val):
        self.val = val

    def scalar(self):
        return self.val

    def all(self):
        return self.val


class MockDbSession:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        sql = str(statement).lower()
        # 1. Check if group by source
        if "group by" in sql:
            return MockScalarResult([("remoteok", 5), ("levels_fyi", 5)])
        # 2. Check if scalar count query
        if "count(" in sql or "count " in sql:
            return MockScalarResult(10)
        # 3. Job listings rows query
        sample_row = SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            title="Senior Staff Engineer",
            company="Nexus AI Corp",
            location="Remote, Global",
            remote_ok=True,
            stipend="$150,000",
            required_skills=["Python", "FastAPI", "Next.js"],
            source_name="remoteok",
            source_url="https://example.com/job/1",
            scraped_at=None,
            has_embedding=True,
        )
        return MockScalarResult([sample_row])


@pytest.mark.asyncio
async def test_get_system_stats_filtering():
    db = MockDbSession()
    stats = await get_system_stats(
        db=db,
        source="remoteok",
        search="Staff",
        company="Nexus",
        location="Remote",
        remote_ok=True,
        has_stipend=True,
        has_embedding=True,
    )
    assert stats["status"] == "healthy"
    assert stats["counts"]["total_listings"] == 10
    assert len(stats["recent_listings"]) == 1
    assert stats["recent_listings"][0]["company"] == "Nexus AI Corp"

    # Verify that the generated query statements included the filter where clauses
    last_query_str = str(db.statements[-1]).lower()
    assert "source_name" in last_query_str
    assert "company" in last_query_str
    assert "location" in last_query_str
    assert "remote_ok" in last_query_str
    assert "embedding" in last_query_str


@pytest.mark.asyncio
async def test_stipend_currency_conversion_greater_than_searched():
    from app.api.system import matches_min_stipend, parse_stipend_to_usd

    # 1. USD listing compared to USD search
    assert matches_min_stipend("$150,000", "100k") is True
    assert matches_min_stipend("$70k", "100k") is False

    # 2. INR / Rupee listing compared to USD search:
    # 80000 rupees (~$941 USD) must be >= $800
    assert matches_min_stipend("80000 rupees", "> 800$") is True
    assert matches_min_stipend("80000 rupees", "800$") is True
    assert matches_min_stipend("80000 rupees", "800") is True

    # 3. USD listing compared to Rupee search:
    # $800 (< 80000 rupees) is False, but $1000 (>= 80000 rupees) is True
    assert matches_min_stipend("$800", "80000 rupees") is False
    assert matches_min_stipend("$1000", "80000 rupees") is True
    assert matches_min_stipend("$150,000", "80000 rupees") is True

    # 4. Range handling: upper bound taken into account
    assert matches_min_stipend("$100k - $150k", "120k") is True
    assert matches_min_stipend("$50k - $70k", "100k") is False


@pytest.mark.asyncio
async def test_get_system_stats_with_min_stipend_filter():
    db = MockDbSession()
    stats = await get_system_stats(db=db, min_stipend="100k")
    # Sample row has stipend "$150,000" which is >= 100k
    assert len(stats["recent_listings"]) == 1

    stats_too_high = await get_system_stats(db=db, min_stipend="200k")
    # Sample row has "$150,000" which is < 200k
    assert len(stats_too_high["recent_listings"]) == 0


@pytest.mark.asyncio
async def test_live_command_center_html_contains_all_filter_controls():
    db = MockDbSession()
    response = await live_command_center(db=db)
    html = response.body.decode("utf-8")

    # Assert new multi-attribute filter inputs exist
    assert 'id="companyInput"' in html
    assert 'id="locationInput"' in html
    assert 'id="stipendInput"' in html
    assert 'id="sortSelector"' in html
    assert 'id="resetFiltersBtn"' in html
    assert 'id="remoteToggleBtn"' in html
    assert 'id="vectorToggleBtn"' in html
    assert 'id="stipendToggleBtn"' in html
    assert 'Min Stipend (≥)' in html
