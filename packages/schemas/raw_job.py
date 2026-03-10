"""Raw job posting schema — represents data as received from a source."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class RawJobPosting(BaseModel):
    """A job posting exactly as ingested from an external source.

    No transformation is applied at this stage.  The ``source`` and
    ``source_id`` fields together form a natural key for deduplication.
    """

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="Origin platform or feed name")
    source_id: str = Field(..., description="Unique identifier within the source")
    source_url: str | None = Field(default=None, description="Direct URL to the posting")
    title: str = Field(..., description="Job title as listed")
    company: str | None = Field(default=None, description="Company name if available")
    location: str | None = Field(default=None, description="Raw location string")
    description: str = Field(default="", description="Full posting body / HTML")
    salary_raw: str | None = Field(default=None, description="Unparsed salary information")
    posted_at: datetime | None = Field(default=None, description="Publication timestamp")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the collector ingested this posting",
    )
    meta: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, description="Arbitrary extra metadata from the source"
    )
