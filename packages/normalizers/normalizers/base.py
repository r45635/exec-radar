"""Abstract base class for all normalizers."""

from abc import ABC, abstractmethod

from schemas import NormalizedJobPosting, RawJobPosting


class BaseNormalizer(ABC):
    """Interface that every normalizer must implement.

    A normalizer receives a :class:`~schemas.RawJobPosting` and returns a
    :class:`~schemas.NormalizedJobPosting`.  Implementations may use heuristics,
    regular expressions, or machine-learning models – the interface stays the same.
    """

    @abstractmethod
    def normalize(self, raw: RawJobPosting) -> NormalizedJobPosting:
        """Normalize *raw* into a canonical :class:`~schemas.NormalizedJobPosting`.

        Args:
            raw: The source-faithful job posting to normalize.

        Returns:
            A normalized, enriched representation ready for scoring and storage.
        """
