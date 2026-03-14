"""Greenhouse collector — fetches job postings from the Greenhouse Boards API.

The Greenhouse Boards API is a public, unauthenticated JSON endpoint
used by many companies to power their careers pages.  Each company has
a ``board_token`` (e.g. ``"discord"``, ``"cloudflare"``, ``"figma"``).

Two-phase fetching is used when ``content=True`` (default):

1. **Light listing** — fetch title + location for every job *without*
   descriptions.  Apply the executive title pre-filter to discard
   obviously irrelevant postings.
2. **Detail fetch** — fetch full descriptions only for the postings
   that passed the filter (batched by individual ``/jobs/{id}`` calls).

This avoids downloading megabytes of HTML descriptions for coordinator
/ analyst / intern roles that will never be ranked.

API docs: https://developers.greenhouse.io/job-board.html

Usage::

    collector = GreenhouseCollector(board_token="discord")
    postings = await collector.collect()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from packages.collectors.base import BaseCollector
from packages.filters import is_executive_title
from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
_REQUEST_TIMEOUT = 30.0
_DETAIL_CONCURRENCY = 10  # max parallel detail fetches


class GreenhouseCollector(BaseCollector):
    """Collector for the Greenhouse public job board API.

    Args:
        board_token: The company's Greenhouse board identifier
            (e.g. ``"discord"``).
        company_name: Human-readable company name to attach to postings.
            If ``None``, the board token is title-cased.
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
        company_name: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        content: bool = True,
    ) -> None:
        self._board_token = board_token
        self._company_name = company_name or board_token.replace("_", " ").title()
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
        """Execute the HTTP request(s) and map results.

        When ``content=True`` this uses two-phase fetching:
        1. Light listing (no descriptions) → title pre-filter
        2. Individual ``/jobs/{id}`` calls for descriptions (parallel)
        """
        url = f"{_BASE_URL}/{self._board_token}/jobs"

        # Phase 1: fetch lightweight listing (always without content)
        logger.info("Fetching job listing from %s", url)
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()
        all_jobs: list[dict] = data.get("jobs", [])
        logger.info(
            "Received %d jobs from Greenhouse board '%s'",
            len(all_jobs),
            self._board_token,
        )

        if not self._content:
            # No descriptions requested — return as-is
            now = datetime.now(UTC)
            return [self._map_job(job, now) for job in all_jobs]

        # Phase 1b: pre-filter by title before fetching heavy content
        exec_jobs = [
            j for j in all_jobs if is_executive_title(j.get("title", ""))
        ]
        discarded = len(all_jobs) - len(exec_jobs)
        if discarded:
            logger.info(
                "Greenhouse '%s': title pre-filter kept %d / %d (skipping %d descriptions)",
                self._board_token,
                len(exec_jobs),
                len(all_jobs),
                discarded,
            )

        if not exec_jobs:
            return []

        # Phase 2: fetch descriptions only for pre-filtered jobs
        sem = asyncio.Semaphore(_DETAIL_CONCURRENCY)

        async def _fetch_detail(job: dict) -> dict:
            job_id = job["id"]
            detail_url = f"{url}/{job_id}"
            async with sem:
                try:
                    resp = await client.get(detail_url)
                    resp.raise_for_status()
                    return resp.json()
                except Exception:
                    logger.warning(
                        "Failed to fetch detail for job %s on '%s'",
                        job_id,
                        self._board_token,
                    )
                    # Fall back to the listing data (no description)
                    return job

        detailed_jobs = await asyncio.gather(
            *(_fetch_detail(j) for j in exec_jobs)
        )

        now = datetime.now(UTC)
        return [self._map_job(job, now) for job in detailed_jobs]

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
            company=self._company_name,
            location=location_name,
            description=content_str or "",
            salary_raw=None,  # Greenhouse rarely exposes salary in the API
            posted_at=posted_at,
            collected_at=collected_at,
            meta=metadata,
        )
