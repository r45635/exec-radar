"""Composite collector — aggregates postings from multiple collectors."""

from __future__ import annotations

import asyncio
import logging

from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)


class CompositeCollector(BaseCollector):
    """Collector that fans out to multiple child collectors in parallel.

    Args:
        collectors: One or more :class:`BaseCollector` instances to aggregate.
    """

    def __init__(self, collectors: list[BaseCollector]) -> None:
        if not collectors:
            msg = "CompositeCollector requires at least one child collector."
            raise ValueError(msg)
        self._collectors = collectors

    @property
    def source_name(self) -> str:
        """Return a combined source name."""
        return "+".join(c.source_name for c in self._collectors)

    async def collect(self) -> list[RawJobPosting]:
        """Collect from all child collectors concurrently.

        Returns:
            A merged list of :class:`RawJobPosting` from all sources.
        """
        results = await asyncio.gather(
            *(c.collect() for c in self._collectors),
            return_exceptions=True,
        )
        postings: list[RawJobPosting] = []
        for collector, result in zip(self._collectors, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Collector %s failed: %s", collector.source_name, result,
                )
                continue
            postings.extend(result)
        logger.info(
            "CompositeCollector gathered %d postings from %d/%d sources",
            len(postings),
            sum(1 for r in results if not isinstance(r, Exception)),
            len(self._collectors),
        )
        return postings
