"""Base normalizer abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.schemas.normalized_job import NormalizedJobPosting
from packages.schemas.raw_job import RawJobPosting


class BaseNormalizer(ABC):
    """Abstract base for all normalizers.

    A normalizer converts a :class:`RawJobPosting` into a
    :class:`NormalizedJobPosting` by cleaning text, inferring seniority,
    parsing salary ranges, and extracting tags.
    """

    @abstractmethod
    def normalize(self, raw: RawJobPosting) -> NormalizedJobPosting:
        """Transform a raw posting into canonical form.

        Args:
            raw: The raw posting to normalize.

        Returns:
            A fully populated :class:`NormalizedJobPosting`.
        """
