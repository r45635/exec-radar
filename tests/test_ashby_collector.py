"""Tests for the Ashby collector.

All tests mock the HTTP layer via a fake ``httpx.AsyncClient`` — no
real network requests are made.  The transport returns HTML pages
with embedded ``window.__appData`` JSON.
"""

from __future__ import annotations

import json

import httpx
import pytest

from packages.collectors.ashby_collector import AshbyCollector
from packages.schemas.raw_job import RawJobPosting

# ---------------------------------------------------------------------------
# Fixture data — realistic window.__appData payload
# ---------------------------------------------------------------------------

_JOB_POSTINGS = [
    {
        "id": "aaaa-1111-bbbb-2222",
        "title": "VP of Manufacturing",
        "locationName": "Austin, TX",
        "employmentType": "FullTime",
        "departmentName": "Operations",
        "teamName": "Manufacturing",
        "descriptionPlain": (
            "Lead wafer fab operations across three sites. "
            "Oversee yield improvement programmes."
        ),
        "descriptionHtml": "<p>Lead wafer fab operations.</p>",
        "publishedDate": "2025-06-10",
        "updatedAt": "2025-06-10T14:30:00.000Z",
        "compensationTierSummary": "$250k - $350k",
        "secondaryLocations": [
            {"locationName": "San Jose, CA", "locationId": "loc-2"},
        ],
    },
    {
        "id": "cccc-3333-dddd-4444",
        "title": "Senior Process Engineer",
        "locationName": "Remote",
        "employmentType": "FullTime",
        "departmentName": "Engineering",
        "descriptionPlain": "Develop next-gen lithography processes.",
        "descriptionHtml": "<p>Develop next-gen lithography.</p>",
        "publishedDate": "2025-07-01",
        "updatedAt": "2025-07-01T09:00:00.000Z",
        "compensationTierSummary": None,
        "secondaryLocations": [],
    },
    {
        "id": "eeee-5555-ffff-6666",
        "title": "Director of Supply Chain",
        "locationName": None,
        "employmentType": None,
        "departmentName": None,
        "descriptionPlain": None,
        "descriptionHtml": None,
        "publishedDate": None,
        "updatedAt": None,
        "compensationTierSummary": None,
        "secondaryLocations": None,
    },
]

_APP_DATA = {
    "organization": {"name": "Acme Semiconductors"},
    "jobBoard": {"jobPostings": _JOB_POSTINGS},
}

# ---------------------------------------------------------------------------
# Helpers — mock HTTP transport returning HTML
# ---------------------------------------------------------------------------


def _build_html(app_data: dict) -> str:
    """Wrap an __appData dict in minimal HTML."""
    return (
        "<!DOCTYPE html><html><head></head><body>"
        "<script>"
        f"window.__appData = {json.dumps(app_data)};"
        "</script></body></html>"
    )


class _FakeTransport(httpx.AsyncBaseTransport):
    """A transport that returns canned HTML."""

    def __init__(self, html: str, status_code: int = 200) -> None:
        self._html = html
        self._status_code = status_code

    async def handle_async_request(
        self, request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=self._status_code,
            headers={"content-type": "text/html"},
            content=self._html.encode(),
            request=request,
        )


def _make_client(
    app_data: dict,
    status_code: int = 200,
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient with a fake transport."""
    html = _build_html(app_data)
    return httpx.AsyncClient(transport=_FakeTransport(html, status_code))


def _make_raw_html_client(
    html: str,
    status_code: int = 200,
) -> httpx.AsyncClient:
    """Build a client returning raw HTML (for edge-case tests)."""
    return httpx.AsyncClient(
        transport=_FakeTransport(html, status_code),
    )


# ===================================================================
# Tests — field mapping
# ===================================================================


class TestAshbyCollectorParsing:
    """Test field mapping from embedded Ashby JSON to RawJobPosting."""

    async def test_returns_raw_postings(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert len(results) == 3
        assert all(isinstance(r, RawJobPosting) for r in results)

    async def test_source_name(self) -> None:
        collector = AshbyCollector(company_slug="acme-semi")
        assert collector.source_name == "ashby:acme-semi"

    async def test_source_id_from_id(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].source_id == "aaaa-1111-bbbb-2222"
        assert results[1].source_id == "cccc-3333-dddd-4444"

    async def test_title_mapped(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].title == "VP of Manufacturing"
        assert results[1].title == "Senior Process Engineer"

    async def test_location_from_location_name(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].location == "Austin, TX"
        assert results[1].location == "Remote"

    async def test_location_none_when_missing(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[2].location is None

    async def test_source_url_constructed(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].source_url == (
            "https://jobs.ashbyhq.com/acme-semi/aaaa-1111-bbbb-2222"
        )

    async def test_description_prefers_plain(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert "Lead wafer fab operations" in results[0].description
        assert "<p>" not in results[0].description

    async def test_description_falls_back_to_html(self) -> None:
        posting = {
            "id": "test-1",
            "title": "Test Role",
            "descriptionPlain": None,
            "descriptionHtml": "<p>HTML only</p>",
        }
        data = {"jobBoard": {"jobPostings": [posting]}}
        client = _make_client(data)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].description == "<p>HTML only</p>"

    async def test_description_empty_when_both_none(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[2].description == ""

    async def test_posted_at_parsed(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].posted_at is not None
        assert results[0].posted_at.year == 2025

    async def test_posted_at_none_when_missing(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[2].posted_at is None

    async def test_metadata_fields(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].meta["employment_type"] == "FullTime"
        assert results[0].meta["department"] == "Operations"
        assert results[0].meta["team"] == "Manufacturing"
        assert results[0].meta["secondary_locations"] == "San Jose, CA"

    async def test_salary_raw_mapped(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results[0].salary_raw == "$250k - $350k"
        assert results[1].salary_raw is None

    async def test_company_from_org_name(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert all(r.company == "Acme Semiconductors" for r in results)

    async def test_company_fallback_to_slug(self) -> None:
        data = {"jobBoard": {"jobPostings": _JOB_POSTINGS}}
        client = _make_client(data)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert all(r.company == "Acme Semi" for r in results)

    async def test_all_postings_have_source(self) -> None:
        client = _make_client(_APP_DATA)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        for posting in results:
            assert posting.source == "ashby:acme-semi"


# ===================================================================
# Tests — edge cases & error handling
# ===================================================================


class TestAshbyCollectorEdgeCases:
    """Edge cases and error handling."""

    async def test_empty_postings(self) -> None:
        data = {"jobBoard": {"jobPostings": []}}
        client = _make_client(data)
        collector = AshbyCollector(
            company_slug="empty-co", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_http_error_raises(self) -> None:
        client = _make_raw_html_client("<html></html>", status_code=404)
        collector = AshbyCollector(
            company_slug="nonexistent", http_client=client,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await collector.collect()

    async def test_timeout_returns_empty(self) -> None:
        class _TimeoutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request,
            ) -> httpx.Response:
                raise httpx.TimeoutException("connect timed out")

        client = httpx.AsyncClient(transport=_TimeoutTransport())
        collector = AshbyCollector(
            company_slug="slow-company", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_no_app_data_returns_empty(self) -> None:
        client = _make_raw_html_client("<html><body>No data</body></html>")
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_invalid_json_returns_empty(self) -> None:
        html = (
            "<html><script>"
            "window.__appData = {bad json!!};"
            "</script></html>"
        )
        client = _make_raw_html_client(html)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_no_job_postings_key_returns_empty(self) -> None:
        data = {"jobBoard": {"teams": []}}
        client = _make_client(data)
        collector = AshbyCollector(
            company_slug="acme-semi", http_client=client,
        )
        results = await collector.collect()
        assert results == []

    async def test_url_contains_company_slug(self) -> None:
        requests_made: list[httpx.Request] = []

        class _SpyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request,
            ) -> httpx.Response:
                requests_made.append(request)
                html = _build_html(_APP_DATA)
                return httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    content=html.encode(),
                    request=request,
                )

        client = httpx.AsyncClient(transport=_SpyTransport())
        collector = AshbyCollector(
            company_slug="ramp", http_client=client,
        )
        await collector.collect()
        assert len(requests_made) == 1
        assert "ramp" in str(requests_made[0].url)
