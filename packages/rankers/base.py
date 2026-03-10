"""Base ranker abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting


class BaseRanker(ABC):
    """Abstract base for all rankers.

    A ranker evaluates a :class:`NormalizedJobPosting` against a target
    executive profile and produces a :class:`FitScore`.
    """

    @abstractmethod
    def score(self, job: NormalizedJobPosting) -> FitScore:
        """Score a single normalized posting.

        Args:
            job: The posting to evaluate.

        Returns:
            A :class:`FitScore` instance with dimension scores.
        """

    def score_batch(self, jobs: list[NormalizedJobPosting]) -> list[FitScore]:
        """Score multiple postings and return results sorted by overall score.

        Args:
            jobs: Postings to evaluate.

        Returns:
            Scores sorted descending by ``overall``.
        """
        scores = [self.score(job) for job in jobs]
        scores.sort(key=lambda s: s.overall, reverse=True)
        return scores
