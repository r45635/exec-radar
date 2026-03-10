"""Tests for the Greenhouse collector.

All tests mock the HTTP layer via a fake ``httpx.AsyncClient`` — no
real network requests are made.
"""

from __future__ import annotations

import httpx
import pytest

from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.schemas.raw_job import RawJobPosting

# ---------------------------------------------------------------------------
# Fixture data — realistic Greenhouse API response
# ---------------------------------------------------------------------------

_GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 12345,
            "title": "Chief Operating Officer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
            "updated_at": "2026-02-20T10:30:00-05:00",
            "location": {"name": "New York, NY"},
            "content": (
                "<p>Lead global operations for a growing tech company.</p>"
                "<p>Oversee supply chain, manufacturing, and strategy.</p>"
            ),
            "departments": [{"id": 1, "name": "Operations"}],
            "internal_job_id": 9876,
            "requisition_id": "REQ-001",
        },
        {
            "id": 67890,
            "title": "VP of Engineering",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/67890",
            "updated_at": "2026-03-01T14:00:00-05:00",
            "location": {"name": "Remote"},
            "content": "<p>Lead the engineering organisation.</p>",
            "departments": [
                {"id": 2, "name": "Engineering"},
                {"id": 3, "name": "Leadership"},
            ],
        },
        {
            "id": 11111,
            "title": "Director of Finance",
            "absolute_url": None,
            "updated_at": None,
            "location": {},
            "content": "",
            "departments": [],
        },
    ]
}

_EMPTY_RESPONSE = {"jobs": []}


# ---------------------------------------------------------------------------
# Helpers — mock HTTP transport
# ---------------------------------------------------------------------------


class _FakeTransport(httpx.AsyncBaseTransport):
    """A transport that returns a canned JSON response."""

    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json_data = json_data
        self._status_code = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        import json

        body = json.dumps(self._json_data).encode()
        return httpx.Response(
            status_code=self._status_code,
            headers={"content-type": "application/json"},
            content=body,
            request=request,
        )


def _make_client(json_data: dict, status_code: int = 200) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient with a fake transport."""
    return httpx.AsyncClient(transport=_FakeTransport(json_data, status_code))


# ===================================================================
# Tests
# ===================================================================


class TestGreenhouseCollectorParsing:
    """Test field mapping from Greenhouse JSON to RawJobPosting."""

    async def test_returns_raw_postings(self) -> None:
        """Should return a list of RawJobPosting instances."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert len(results) == 3
        assert all(isinstance(r, RawJobPosting) for r in results)

    async def test_source_name(self) -> None:
        """Source name should include the board token."""
        collector = GreenhouseCollector(board_token="acme")
        assert collector.source_name == "greenhouse:acme"

    async def test_source_id_from_job_id(self) -> None:
        """source_id should be the Greenhouse numeric job ID as string."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].source_id == "12345"
        assert results[1].source_id == "67890"

    async def test_title_mapped(self) -> None:
        """Title should come from the job object."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].title == "Chief Operating Officer"
        assert results[1].title == "VP of Engineering"

    async def test_location_mapped(self) -> None:
        """Location should come from location.name."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].location == "New York, NY"
        assert results[1].location == "Remote"

    async def test_location_empty_object(self) -> None:
        """Empty location object should yield None."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[2].location is None

    async def test_source_url_mapped(self) -> None:
        """source_url should be the absolute_url from Greenhouse."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].source_url == "https://boards.greenhouse.io/acme/jobs/12345"

    async def test_description_contains_html(self) -> None:
        """Description should be the raw HTML content."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert "<p>" in results[0].description

    async def test_posted_at_parsed(self) -> None:
        """posted_at should be parsed from ISO 8601 updated_at."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].posted_at is not None
        assert results[0].posted_at.year == 2026

    async def test_posted_at_none_when_missing(self) -> None:
        """posted_at should be None when updated_at is missing."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[2].posted_at is None

    async def test_departments_in_meta(self) -> None:
        """Departments should be stored in meta."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].meta["departments"] == "Operations"
        assert results[1].meta["departments"] == "Engineering, Leadership"

    async def test_internal_ids_in_meta(self) -> None:
        """Internal job ID and requisition ID should be in meta."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results[0].meta["internal_job_id"] == "9876"
        assert results[0].meta["requisition_id"] == "REQ-001"

    async def test_all_postings_have_source_set(self) -> None:
        """Every posting's source should match the collector's source_name."""
        client = _make_client(_GREENHOUSE_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        for posting in results:
            assert posting.source == "greenhouse:acme"


class TestGreenhouseCollectorEdgeCases:
    """Edge cases and error handling."""

    async def test_empty_response(self) -> None:
        """Empty jobs array should return an empty list."""
        client = _make_client(_EMPTY_RESPONSE)
        collector = GreenhouseCollector(board_token="acme", http_client=client)
        results = await collector.collect()
        assert results == []

    async def test_http_error_raises(self) -> None:
        """HTTP errors should propagate as httpx.HTTPStatusError."""
        client = _make_client({"error": "not found"}, status_code=404)
        collector = GreenhouseCollector(board_token="nonexistent", http_client=client)
        with pytest.raises(httpx.HTTPStatusError):
            await collector.collect()

    async def test_content_param_sent(self) -> None:
        """When content=True, the request should include ?content=true."""
        requests_made: list[httpx.Request] = []

        class _SpyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                import json

                requests_made.append(request)
                body = json.dumps(_EMPTY_RESPONSE).encode()
                return httpx.Response(200, content=body, request=request)

        client = httpx.AsyncClient(transport=_SpyTransport())
        collector = GreenhouseCollector(board_token="test", http_client=client, content=True)
        await collector.collect()

        assert len(requests_made) == 1
        assert "content=true" in str(requests_made[0].url)

    async def test_no_content_param(self) -> None:
        """When content=False, the request should NOT include ?content=true."""
        requests_made: list[httpx.Request] = []

        class _SpyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                import json

                requests_made.append(request)
                body = json.dumps(_EMPTY_RESPONSE).encode()
                return httpx.Response(200, content=body, request=request)

        client = httpx.AsyncClient(transport=_SpyTransport())
        collector = GreenhouseCollector(board_token="test", http_client=client, content=False)
        await collector.collect()

        assert len(requests_made) == 1
        assert "content=true" not in str(requests_made[0].url)
