"""Abstract base class for all job collectors."""

from abc import ABC, abstractmethod

from schemas import RawJobPosting


class BaseCollector(ABC):
    """Interface that every collector must implement.

    A collector is responsible for fetching raw job postings from a single
    source.  It must be stateless between calls so that the worker can run
    multiple collectors concurrently.

    To add a new source, subclass :class:`BaseCollector` and implement
    :meth:`collect`.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable, URL-safe identifier for this source (e.g. ``'linkedin'``)."""

    @abstractmethod
    async def collect(self) -> list[RawJobPosting]:
        """Fetch job postings from the source.

        Returns:
            A list of :class:`~schemas.RawJobPosting` objects.  An empty list
            is a valid result (no new postings found).

        Raises:
            CollectorError: if a non-recoverable error occurs during collection.
        """


class CollectorError(Exception):
    """Raised when a collector encounters a non-recoverable error."""
