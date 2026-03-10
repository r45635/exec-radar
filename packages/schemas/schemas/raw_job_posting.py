"""Raw job posting schema – the unprocessed, source-faithful representation."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl


class RawJobPosting(BaseModel):
    """Represents a job posting as fetched from a source with minimal processing.

    This schema preserves the original data exactly as received so that the
    normalisation layer can apply transformations without losing source fidelity.
    """

    source: str = Field(..., description="Identifier for the data source (e.g. 'linkedin', 'mock')")
    source_id: str = Field(..., description="Unique identifier assigned by the source system")
    url: HttpUrl = Field(..., description="Canonical URL of the job posting")
    title: str = Field(..., description="Raw job title as shown by the source")
    company: str = Field(..., description="Company name as shown by the source")
    location: str | None = Field(None, description="Location string as shown by the source")
    description: str | None = Field(None, description="Full text of the job description")
    salary_raw: str | None = Field(None, description="Salary information in unparsed string form")
    posted_at: datetime | None = Field(None, description="When the posting was published (UTC)")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this record was collected (UTC)",
    )
    raw_data: dict | None = Field(None, description="Full raw payload from the source (for debugging)")

    model_config = {"json_schema_extra": {"example": {
        "source": "mock",
        "source_id": "mock-001",
        "url": "https://example.com/jobs/cto-001",
        "title": "Chief Technology Officer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "description": "We are looking for a CTO to lead our engineering team...",
        "salary_raw": "$250,000 - $300,000",
        "posted_at": "2024-01-15T10:00:00Z",
    }}}
