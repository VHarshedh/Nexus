from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline.extractor import ListingExtractor, MAX_RETRIES


class Responses:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def generate_content(self, **_kwargs):
        self.calls += 1
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(text=value)


def extractor_with(responses: list[object]) -> tuple[ListingExtractor, Responses]:
    extractor = ListingExtractor()
    fake = Responses(responses)
    extractor._client = SimpleNamespace(aio=SimpleNamespace(models=fake))
    return extractor, fake


@pytest.mark.asyncio
async def test_extracts_valid_json_and_caches_result():
    extractor, fake = extractor_with([
        '{"title":"Engineer","company":"Nexus","remote_ok":true,"required_skills":["Python"]}'
    ])
    result = await extractor.extract("Nexus wants a Python engineer")
    cached = await extractor.extract("Nexus wants a Python engineer")
    assert result is not None
    assert result.title == "Engineer"
    assert cached == result
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_repairs_malformed_json_then_returns_valid_result():
    extractor, fake = extractor_with([
        "not json",
        '{"title":"Engineer","company":"Nexus"}',
    ])
    result = await extractor.extract("listing")
    assert result is not None
    assert result.company == "Nexus"
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_empty_and_retry_exhaustion_are_safe():
    extractor, fake = extractor_with(["", "", ""])
    assert await extractor.extract("   ") is None
    assert fake.calls == 0
    assert await extractor.extract("listing") is None
    assert fake.calls == MAX_RETRIES


@pytest.mark.asyncio
async def test_provider_errors_never_escape_pipeline():
    extractor, fake = extractor_with([RuntimeError("rate limited")] * MAX_RETRIES)
    assert await extractor.extract("listing") is None
    assert fake.calls == MAX_RETRIES
