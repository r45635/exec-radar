"""HTTP-based job collector that fetches postings from a JSON endpoint.

This sample implementation demonstrates how to integrate any REST API that
returns a list of job objects.  Replace ``ENDPOINT_URL`` with the real URL
and adjust ``_parse_item`` to match the source's schema.
"""

import contextlib
import logging
from datetime import datetime

import httpx
from schemas import RawJobPosting

from .base import BaseCollector, CollectorError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample endpoint – replace with a real source URL via configuration.
# The mock server returns objects that match the shape handled by _parse_item.
# ---------------------------------------------------------------------------
_DEFAULT_ENDPOINT = "https://example.com/api/jobs"


class HttpCollector(BaseCollector):
    """Collects job postings from a configurable HTTP/JSON endpoint.

    Args:
        endpoint_url: URL that returns a JSON array of job objects.
        timeout: HTTP request timeout in seconds.
        source: Source identifier string stored on each :class:`~schemas.RawJobPosting`.
    """

    def __init__(
        self,
        endpoint_url: str = _DEFAULT_ENDPOINT,
        timeout: float = 10.0,
        source: str = "http",
    ) -> None:
        self._endpoint_url = endpoint_url
        self._timeout = timeout
        self._source = source

    @property
    def source_name(self) -> str:
        return self._source

    async def collect(self) -> list[RawJobPosting]:
        """Fetch jobs from the configured endpoint.

        Returns:
            Parsed list of :class:`~schemas.RawJobPosting` objects.

        Raises:
            CollectorError: on HTTP or parsing failures.
        """
        logger.info("Collecting jobs from %s", self._endpoint_url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._endpoint_url)
                response.raise_for_status()
                items: list[dict] = response.json()
        except httpx.HTTPError as exc:
            raise CollectorError(f"HTTP error while collecting from {self._endpoint_url}: {exc}") from exc
        except Exception as exc:
            raise CollectorError(f"Unexpected error during collection: {exc}") from exc

        postings: list[RawJobPosting] = []
        for item in items:
            try:
                postings.append(self._parse_item(item))
            except Exception:
                logger.warning("Failed to parse item: %s", item, exc_info=True)

        logger.info("Collected %d postings from %s", len(postings), self._endpoint_url)
        return postings

    def _parse_item(self, item: dict) -> RawJobPosting:
        """Convert a raw API response dict into a :class:`~schemas.RawJobPosting`.

        Override this method when subclassing to handle source-specific shapes.
        """
        posted_at: datetime | None = None
        if raw_date := item.get("posted_at") or item.get("date"):
            with contextlib.suppress(ValueError, TypeError):
                posted_at = datetime.fromisoformat(raw_date)

        return RawJobPosting(
            source=self._source,
            source_id=str(item.get("id", "")),
            url=item["url"],
            title=item.get("title", ""),
            company=item.get("company", ""),
            location=item.get("location"),
            description=item.get("description"),
            salary_raw=item.get("salary") or item.get("salary_raw"),
            posted_at=posted_at,
            raw_data=item,
        )
