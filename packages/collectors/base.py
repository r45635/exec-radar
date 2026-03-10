"""Base collector abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.schemas.raw_job import RawJobPosting


class BaseCollector(ABC):
    """Abstract base for all job-posting collectors.

    Each concrete collector is responsible for a single source (e.g. a
    job board, an RSS feed, a company careers page).  Implementations
    must override :meth:`collect` to return a list of raw postings.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return a short, unique identifier for this source."""

    @abstractmethod
    async def collect(self) -> list[RawJobPosting]:
        """Fetch raw postings from the source.

        Returns:
            A list of :class:`RawJobPosting` instances.
        """
