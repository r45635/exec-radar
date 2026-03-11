"""Ashby collector — fetches job postings from Ashby-hosted career pages.

Ashby career pages at ``https://jobs.ashbyhq.com/<company>`` embed
structured job data inside a ``window.__appData`` JavaScript object.
The collector fetches the HTML, extracts the embedded JSON, and maps
each job posting to :class:`RawJobPosting`.

Usage::

    collector = AshbyCollector(company_slug="ramp")
    postings = await collector.collect()
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx

from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)

_BASE_URL = "https://jobs.ashbyhq.com"
_REQUEST_TIMEOUT = 30.0


class AshbyCollector(BaseCollector):
    """Collector for Ashby-hosted job boards.

    Args:
        company_slug: The company's Ashby identifier
            (e.g. ``"ramp"``, ``"notion"``).
        http_client: Optional pre-configured :class:`httpx.AsyncClient`.
            If ``None``, a new client is created per ``collect()`` call.
            Inject a custom client for testing or proxy configuration.
    """

    def __init__(
        self,
        company_slug: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._company_slug = company_slug
        self._http_client = http_client

    @property
    def source_name(self) -> str:
        """Return a source identifier that includes the company slug."""
        return f"ashby:{self._company_slug}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect(self) -> list[RawJobPosting]:
        """Fetch all jobs from the configured Ashby board.

        Returns:
            A list of :class:`RawJobPosting` mapped from the embedded JSON.
        """
        if self._http_client is not None:
            return await self._fetch(self._http_client)

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            return await self._fetch(client)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch(self, client: httpx.AsyncClient) -> list[RawJobPosting]:
        """Fetch the HTML page, extract embedded data, and map results."""
        url = f"{_BASE_URL}/{self._company_slug}"
        logger.info("Fetching Ashby job board from %s", url)

        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error(
                "Timeout fetching Ashby board for '%s'",
                self._company_slug,
            )
            return []
        except httpx.HTTPStatusError:
            logger.error(
                "HTTP %s fetching Ashby board for '%s'",
                response.status_code,
                self._company_slug,
            )
            raise

        html = response.text
        app_data = self._parse_app_data(html)
        if app_data is None:
            return []

        job_board = app_data.get("jobBoard") or {}
        postings = job_board.get("jobPostings") or []
        if not postings:
            logger.warning(
                "No jobPostings found in Ashby data for '%s'",
                self._company_slug,
            )
            return []

        org = app_data.get("organization") or {}
        company = org.get("name") or self._company_slug.replace("-", " ").title()
        now = datetime.now(UTC)

        logger.info(
            "Extracted %d jobs from Ashby board '%s'",
            len(postings),
            self._company_slug,
        )

        return [self._map_job(job, company, now) for job in postings]

    # ------------------------------------------------------------------
    # HTML / JSON extraction
    # ------------------------------------------------------------------

    def _parse_app_data(self, html: str) -> dict | None:
        """Extract and parse the ``window.__appData`` JSON from HTML."""
        marker = "window.__appData"
        idx = html.find(marker)
        if idx < 0:
            logger.warning(
                "No window.__appData found in Ashby page for '%s'",
                self._company_slug,
            )
            return None

        # Find the start of the JSON object after '='
        eq_idx = html.index("=", idx)
        start = eq_idx + 1

        # Walk the string to find the matching closing brace
        depth = 0
        end = start
        in_string = False
        escape_next = False
        for i in range(start, min(start + 500_000, len(html))):
            c = html[i]
            if escape_next:
                escape_next = False
                continue
            if c == "\\" and in_string:
                escape_next = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        raw = html[start:end].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse window.__appData JSON for '%s'",
                self._company_slug,
            )
            return None

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    def _map_job(
        self,
        job: dict,
        company: str,
        collected_at: datetime,
    ) -> RawJobPosting:
        """Map a single Ashby job dict to :class:`RawJobPosting`."""
        job_id = str(job.get("id", ""))
        source_url = (
            f"{_BASE_URL}/{self._company_slug}/{job_id}" if job_id else None
        )

        # Location
        location = job.get("locationName") or None

        # Description: prefer plain text, fall back to HTML
        description = (
            job.get("descriptionPlain")
            or job.get("descriptionHtml")
            or ""
        )

        # Posted date
        date_str = job.get("publishedDate") or job.get("updatedAt")
        posted_at: datetime | None = None
        if date_str:
            try:
                posted_at = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass

        # Metadata
        metadata: dict[str, str | int | float | bool | None] = {}
        if job.get("employmentType"):
            metadata["employment_type"] = job["employmentType"]
        if job.get("departmentName"):
            metadata["department"] = job["departmentName"]
        if job.get("teamName"):
            metadata["team"] = job["teamName"]

        secondary = job.get("secondaryLocations")
        if secondary and isinstance(secondary, list):
            names = [
                loc.get("locationName", "")
                for loc in secondary
                if isinstance(loc, dict) and loc.get("locationName")
            ]
            if names:
                metadata["secondary_locations"] = ", ".join(names)

        return RawJobPosting(
            source=self.source_name,
            source_id=job_id,
            source_url=source_url,
            title=job.get("title", "Untitled"),
            company=company,
            location=location,
            description=description,
            salary_raw=job.get("compensationTierSummary"),
            posted_at=posted_at,
            collected_at=collected_at,
            meta=metadata,
        )
