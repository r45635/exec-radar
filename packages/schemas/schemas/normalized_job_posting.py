"""Normalized job posting schema – the canonical, enriched representation."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class SeniorityLevel(StrEnum):
    """Standardised seniority levels used across the platform."""

    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    DIRECTOR = "director"
    VP = "vp"
    C_SUITE = "c_suite"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Standardised employment types."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERIM = "interim"
    BOARD = "board"
    UNKNOWN = "unknown"


class NormalizedJobPosting(BaseModel):
    """Canonical representation of a job posting after normalization.

    Fields are normalized to consistent formats regardless of source.
    This is the model used for scoring, storage, and API responses.
    """

    id: str = Field(..., description="Platform-assigned unique identifier (e.g. UUID)")
    source: str = Field(..., description="Original data source identifier")
    source_id: str = Field(..., description="Unique identifier from the source system")
    url: HttpUrl = Field(..., description="Canonical URL of the job posting")

    # Normalized title and classification
    title: str = Field(..., description="Cleaned, normalized job title")
    seniority: SeniorityLevel = Field(
        SeniorityLevel.UNKNOWN, description="Inferred seniority level"
    )
    employment_type: EmploymentType = Field(
        EmploymentType.UNKNOWN, description="Inferred employment type"
    )

    # Company and location
    company: str = Field(..., description="Normalized company name")
    location: str | None = Field(None, description="Normalized location string")
    remote: bool = Field(False, description="Whether the role is remote-friendly")

    # Compensation
    salary_min: float | None = Field(None, description="Lower salary bound (USD per year)")
    salary_max: float | None = Field(None, description="Upper salary bound (USD per year)")

    # Content
    description: str | None = Field(None, description="Cleaned job description text")
    skills: list[str] = Field(default_factory=list, description="Extracted required skills")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")

    # Timestamps
    posted_at: datetime | None = Field(None, description="Original posting date (UTC)")
    normalized_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this record was normalized (UTC)",
    )

    model_config = {"json_schema_extra": {"example": {
        "id": "00000000-0000-0000-0000-000000000001",
        "source": "mock",
        "source_id": "mock-001",
        "url": "https://example.com/jobs/cto-001",
        "title": "Chief Technology Officer",
        "seniority": "c_suite",
        "employment_type": "full_time",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "remote": True,
        "salary_min": 250000.0,
        "salary_max": 300000.0,
        "skills": ["Python", "AWS", "Leadership"],
        "keywords": ["CTO", "engineering", "technology"],
    }}}
