"""Base notifier abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import NormalizedJobPosting


class BaseNotifier(ABC):
    """Abstract base for notification delivery channels.

    Implementations might send emails, Slack messages, webhooks, etc.
    """

    @abstractmethod
    async def notify(
        self,
        job: NormalizedJobPosting,
        score: FitScore,
    ) -> None:
        """Send a notification about a scored job.

        Args:
            job: The normalized posting.
            score: The computed fit score.
        """
