"""Tests for the Lever collector.

All tests mock the HTTP layer via a fake ``httpx.AsyncClient`` — no
real network requests are made.
"""

from __future__ import annotations

import httpx
import pytest

from packages.collectors.lever_collector import LeverCollector
from packages.schemas.raw_job import RawJobPosting

# ---------------------------------------------------------------------------
# Fixture data — realistic Lever API response
# ---------------------------------------------------------------------------

_LEVER_RESPONSE = [
    {
        "id": "aaaa-bbbb-cccc-1111",
        "text": "VP of Operations",
        "hostedUrl": "https://jobs.lever.co/acme/aaaa-bbbb-cccc-1111",
        "createdAt": 1740000000000,  # ~2025-02-19
        "descriptionPlain": (
            "Lead global operations across multiple sites. "
            "Oversee supply chain, manufacturing, and strategy."
        ),
        "description": "<p>Lead global operations.</p>",
        "categories": {
            "location": "New York, NY",
            "team": "Operations",
            "department": "Executive",
            "commitment": "Full-time",
        },
        "workplaceType": "hybrid",
    },
    {
        "id": "dddd-eeee-ffff-2222",
        "text": "Senior Software Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/dddd-eeee-ffff-2222",
        "createdAt": 1741000000000,
        "descriptionPlain": "Build scalable distributed systems.",
        "description": "<p>Build scalable distributed systems.</p>",
        "categories": {
            "location": "Remote",
            "team": "Engineering",
        },
        "workplaceType": "remote",
    },
    {
        "id": "gggg-hhhh-iiii-3333",
        "text": "Director of Finance",
        "hostedUrl": None,
        "createdAt": None,
        "descriptionPlain": None,
        "description": None,
        "categories": None,
    },
]


# ---------------------------------------------------------------------------
# Helpers — mock HTTP transport
# ---------------------------------------------------------------------------


class _FakeTransport(httpx.AsyncBaseTransport):
    """A transport that returns a canned JSON response."""

    def __init__(
        self,
        json_data: list | dict,
        status_code: int = 200,
    ) -> None:
        self._json_data = json_data
        self._status_code = status_code

    async def handle_async_request(
        self, request: httpx.Request,
    ) -> httpx.Response:
        import json

        body = json.dumps(self._json_data).encode()
        return httpx.Response(
            status_code=self._status_code,
            headers={"content-type": "application/json"},
            content=body,
            request=request,
        )


def _make_client(
    json_data: list | dict,
    status_code: int = 200,
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient with a fake transport."""
    return httpx.AsyncClient(
        transport=_FakeTransport(json_data, status_code),
    )


# ===================================================================
# Tests
# ===================================================================


class TestLeverCollectorParsing:
    """Test field mapping from Lever JSON to RawJobPosting."""

    async def test_returns_raw_postings(self) -> None:
        """Should return a list of RawJobPosting instances."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert len(results) == 3
        assert all(isinstance(r, RawJobPosting) for r in results)

    async def test_source_name(self) -> None:
        """Source name should include the company slug."""
        collector = LeverCollector(company_slug="acme")
        assert collector.source_name == "lever:acme"

    async def test_source_id_from_id(self) -> None:
        """source_id should be the Lever posting ID as string."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].source_id == "aaaa-bbbb-cccc-1111"
        assert results[1].source_id == "dddd-eeee-ffff-2222"

    async def test_title_mapped(self) -> None:
        """Title should come from the 'text' field."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].title == "VP of Operations"
        assert results[1].title == "Senior Software Engineer"

    async def test_location_from_categories(self) -> None:
        """Location should come from categories.location."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].location == "New York, NY"
        assert results[1].location == "Remote"

    async def test_location_none_when_categories_null(self) -> None:
        """Null categories should yield None location."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[2].location is None

    async def test_source_url_from_hosted_url(self) -> None:
        """source_url should be the hostedUrl from Lever."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].source_url == (
            "https://jobs.lever.co/acme/aaaa-bbbb-cccc-1111"
        )

    async def test_description_prefers_plain(self) -> None:
        """Description should prefer descriptionPlain over HTML."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert "Lead global operations" in results[0].description
        assert "<p>" not in results[0].description

    async def test_description_falls_back_to_html(self) -> None:
        """When descriptionPlain is None, description (HTML) is used."""
        posting = {
            "id": "test-1",
            "text": "Test Role",
            "hostedUrl": None,
            "createdAt": None,
            "descriptionPlain": None,
            "description": "<p>HTML description</p>",
            "categories": {},
        }
        client = _make_client([posting])
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].description == "<p>HTML description</p>"

    async def test_description_empty_when_both_none(self) -> None:
        """When both description fields are None, use empty string."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[2].description == ""

    async def test_posted_at_parsed(self) -> None:
        """posted_at should be parsed from epoch ms createdAt."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].posted_at is not None
        assert results[0].posted_at.year == 2025

    async def test_posted_at_none_when_missing(self) -> None:
        """posted_at should be None when createdAt is missing."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[2].posted_at is None

    async def test_metadata_fields(self) -> None:
        """Team, department, commitment, workplace_type in meta."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results[0].meta["team"] == "Operations"
        assert results[0].meta["department"] == "Executive"
        assert results[0].meta["commitment"] == "Full-time"
        assert results[0].meta["workplace_type"] == "hybrid"

    async def test_all_postings_have_source_set(self) -> None:
        """Every posting's source should match the collector's name."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        for posting in results:
            assert posting.source == "lever:acme"

    async def test_company_name_from_slug(self) -> None:
        """Company name should be title-cased from slug."""
        client = _make_client(_LEVER_RESPONSE)
        collector = LeverCollector(
            company_slug="data-dog", http_client=client,
        )
        results = await collector.collect()
        assert all(r.company == "Data Dog" for r in results)


class TestLeverCollectorEdgeCases:
    """Edge cases and error handling."""

    async def test_empty_response(self) -> None:
        """Empty list should return an empty list."""
        client = _make_client([])
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_http_error_raises(self) -> None:
        """HTTP errors should propagate as httpx.HTTPStatusError."""
        client = _make_client(
            {"error": "not found"}, status_code=404,
        )
        collector = LeverCollector(
            company_slug="nonexistent", http_client=client,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await collector.collect()

    async def test_unexpected_dict_response(self) -> None:
        """A dict response (instead of list) returns empty list."""
        client = _make_client({"unexpected": "format"})
        collector = LeverCollector(
            company_slug="acme", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_timeout_returns_empty(self) -> None:
        """Network timeout should return empty list, not crash."""

        class _TimeoutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request,
            ) -> httpx.Response:
                raise httpx.TimeoutException("connect timed out")

        client = httpx.AsyncClient(transport=_TimeoutTransport())
        collector = LeverCollector(
            company_slug="slow-company", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_mode_json_param_sent(self) -> None:
        """Request should include ?mode=json."""
        requests_made: list[httpx.Request] = []

        class _SpyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request,
            ) -> httpx.Response:
                import json

                requests_made.append(request)
                body = json.dumps([]).encode()
                return httpx.Response(
                    200, content=body, request=request,
                )

        client = httpx.AsyncClient(transport=_SpyTransport())
        collector = LeverCollector(
            company_slug="test", http_client=client,
        )
        await collector.collect()

        assert len(requests_made) == 1
        assert "mode=json" in str(requests_made[0].url)

    async def test_url_contains_company_slug(self) -> None:
        """Request URL should contain the company slug."""
        requests_made: list[httpx.Request] = []

        class _SpyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request,
            ) -> httpx.Response:
                import json

                requests_made.append(request)
                body = json.dumps([]).encode()
                return httpx.Response(
                    200, content=body, request=request,
                )

        client = httpx.AsyncClient(transport=_SpyTransport())
        collector = LeverCollector(
            company_slug="netflix", http_client=client,
        )
        await collector.collect()

        assert "netflix" in str(requests_made[0].url)
