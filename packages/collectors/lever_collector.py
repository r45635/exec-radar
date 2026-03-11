"""Lever collector — fetches job postings from the Lever public API.

The Lever Postings API is a public, unauthenticated JSON endpoint
used by companies to power their careers pages.  Each company has
a ``company_slug`` (e.g. ``"lever"``, ``"netflix"``, ``"twitch"``).

API docs: https://github.com/lever/postings-api

Usage::

    collector = LeverCollector(company_slug="netflix")
    postings = await collector.collect()
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.lever.co/v0/postings"
_REQUEST_TIMEOUT = 30.0


class LeverCollector(BaseCollector):
    """Collector for the Lever public postings API.

    Args:
        company_slug: The company's Lever identifier
            (e.g. ``"netflix"``).
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
        return f"lever:{self._company_slug}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect(self) -> list[RawJobPosting]:
        """Fetch all jobs from the configured Lever company.

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
        url = f"{_BASE_URL}/{self._company_slug}"
        params = {"mode": "json"}

        logger.info("Fetching jobs from %s", url)
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error(
                "Timeout fetching Lever postings for '%s'",
                self._company_slug,
            )
            return []
        except httpx.HTTPStatusError:
            logger.error(
                "HTTP %s fetching Lever postings for '%s'",
                response.status_code,
                self._company_slug,
            )
            raise

        data = response.json()
        if not isinstance(data, list):
            logger.warning(
                "Unexpected response format from Lever for '%s' "
                "(expected list, got %s)",
                self._company_slug,
                type(data).__name__,
            )
            return []

        logger.info(
            "Received %d jobs from Lever company '%s'",
            len(data),
            self._company_slug,
        )

        now = datetime.now(UTC)
        return [self._map_job(job, now) for job in data]

    def _map_job(self, job: dict, collected_at: datetime) -> RawJobPosting:
        """Map a single Lever posting JSON object to :class:`RawJobPosting`."""
        # Location comes from categories.location
        categories = job.get("categories", {}) or {}
        location: str | None = categories.get("location") if isinstance(
            categories, dict
        ) else None

        # Description: prefer descriptionPlain, fall back to description
        description = (
            job.get("descriptionPlain")
            or job.get("description")
            or ""
        )

        # Posted date: Lever uses millisecond epoch timestamps
        created_at_ms = job.get("createdAt")
        posted_at: datetime | None = None
        if created_at_ms and isinstance(created_at_ms, (int, float)):
            try:
                posted_at = datetime.fromtimestamp(
                    created_at_ms / 1000, tz=UTC,
                )
            except (ValueError, OSError):
                pass

        # Metadata
        metadata: dict[str, str | int | float | bool | None] = {}
        if categories.get("team"):
            metadata["team"] = categories["team"]
        if categories.get("department"):
            metadata["department"] = categories["department"]
        if categories.get("commitment"):
            metadata["commitment"] = categories["commitment"]
        if job.get("workplaceType"):
            metadata["workplace_type"] = job["workplaceType"]

        return RawJobPosting(
            source=self.source_name,
            source_id=str(job["id"]),
            source_url=job.get("hostedUrl"),
            title=job.get("text", "Untitled"),
            company=self._company_slug.replace("-", " ").title(),
            location=location,
            description=description,
            salary_raw=None,
            posted_at=posted_at,
            collected_at=collected_at,
            meta=metadata,
        )
