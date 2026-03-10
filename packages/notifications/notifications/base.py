"""Abstract base class and payload model for notifiers."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class NotificationPayload(BaseModel):
    """Data passed to a notifier when a high-scoring job is found."""

    subject: str = Field(..., description="Short subject line for the notification")
    body: str = Field(..., description="Full notification body (plain text)")
    job_url: str = Field(..., description="URL of the job posting")
    score: float = Field(..., description="Overall fit score (0–100)")
    metadata: dict | None = Field(None, description="Additional key/value pairs")


class BaseNotifier(ABC):
    """Interface that every notifier must implement.

    A notifier dispatches a :class:`NotificationPayload` via a specific channel
    (e.g. email, Slack, webhook).  Implementations should be stateless.
    """

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> None:
        """Send *payload* via the notifier's channel.

        Args:
            payload: The notification data to dispatch.

        Raises:
            NotificationError: if the notification could not be delivered.
        """


class NotificationError(Exception):
    """Raised when a notification cannot be delivered."""
