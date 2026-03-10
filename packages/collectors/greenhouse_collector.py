"""Greenhouse collector — fetches job postings from the Greenhouse Boards API.

The Greenhouse Boards API is a public, unauthenticated JSON endpoint
used by many companies to power their careers pages.  Each company has
a ``board_token`` (e.g. ``"discord"``, ``"cloudflare"``, ``"figma"``).

API docs: https://developers.greenhouse.io/job-board.html

Usage::

    collector = GreenhouseCollector(board_token="discord")
    postings = await collector.collect()
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
_REQUEST_TIMEOUT = 30.0


class GreenhouseCollector(BaseCollector):
    """Collector for the Greenhouse public job board API.

    Args:
        board_token: The company's Greenhouse board identifier
            (e.g. ``"discord"``).
        http_client: Optional pre-configured :class:`httpx.AsyncClient`.
            If ``None``, a new client is created per ``collect()`` call.
            Inject a custom client for testing or proxy configuration.
        content: When ``True``, fetch full job descriptions (one extra
            request per job).  ``False`` fetches the listing only.
    """

    def __init__(
        self,
        board_token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        content: bool = True,
    ) -> None:
        self._board_token = board_token
        self._http_client = http_client
        self._content = content

    @property
    def source_name(self) -> str:
        """Return a source identifier that includes the board token."""
        return f"greenhouse:{self._board_token}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect(self) -> list[RawJobPosting]:
        """Fetch all jobs from the configured Greenhouse board.

        Returns:
            A list of :class:`RawJobPosting` mapped from the API JSON.
        """
        if self._http_client is not None:
            return await self._fetch(self._http_client)

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            return await self._fetch(client)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch(self, client: httpx.AsyncClient) -> list[RawJobPosting]:
        """Execute the HTTP request and map results."""
        url = f"{_BASE_URL}/{self._board_token}/jobs"
        params: dict[str, str] = {}
        if self._content:
            params["content"] = "true"

        logger.info("Fetching jobs from %s", url)
        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        jobs: list[dict] = data.get("jobs", [])
        logger.info("Received %d jobs from Greenhouse board '%s'", len(jobs), self._board_token)

        now = datetime.now(UTC)
        return [self._map_job(job, now) for job in jobs]

    def _map_job(self, job: dict, collected_at: datetime) -> RawJobPosting:
        """Map a single Greenhouse job JSON object to :class:`RawJobPosting`."""
        # Location: Greenhouse returns a location object with a "name" field
        location = job.get("location", {})
        location_name: str | None = location.get("name") if isinstance(location, dict) else None

        # Posted date: ISO 8601 string like "2024-01-15T12:00:00-05:00"
        updated_at_raw = job.get("updated_at")
        posted_at: datetime | None = None
        if updated_at_raw:
            try:
                posted_at = datetime.fromisoformat(updated_at_raw)
            except (ValueError, TypeError):
                pass

        # Description: HTML content string
        content_str = job.get("content", "")

        # Departments / metadata
        departments: list[str] = [
            d.get("name", "") for d in job.get("departments", []) if isinstance(d, dict)
        ]

        # Company metadata from the board
        metadata: dict[str, str | int | float | bool | None] = {}
        if departments:
            metadata["departments"] = ", ".join(departments)
        if job.get("internal_job_id"):
            metadata["internal_job_id"] = str(job["internal_job_id"])
        if job.get("requisition_id"):
            metadata["requisition_id"] = str(job["requisition_id"])

        return RawJobPosting(
            source=self.source_name,
            source_id=str(job["id"]),
            source_url=job.get("absolute_url"),
            title=job.get("title", "Untitled"),
            company=None,  # Greenhouse board-level — company is implicit
            location=location_name,
            description=content_str or "",
            salary_raw=None,  # Greenhouse rarely exposes salary in the API
            posted_at=posted_at,
            collected_at=collected_at,
            meta=metadata,
        )
