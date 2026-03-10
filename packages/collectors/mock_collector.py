"""Mock collector returning synthetic executive job postings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

_SAMPLE_POSTINGS: list[dict[str, str | None]] = [
    {
        "source_id": "mock-001",
        "title": "Chief Operating Officer",
        "company": "Acme Corp",
        "location": "New York, NY",
        "description": (
            "Lead global operations for a Fortune 500 company. "
            "Oversee supply chain, manufacturing, and strategic planning."
        ),
        "salary_raw": "$350,000 - $500,000",
    },
    {
        "source_id": "mock-002",
        "title": "VP of Operations",
        "company": "TechScale Inc.",
        "location": "Remote",
        "description": (
            "Drive operational excellence across engineering, support, and logistics. "
            "Report directly to the CEO."
        ),
        "salary_raw": "$250,000 - $350,000",
    },
    {
        "source_id": "mock-003",
        "title": "SVP, Supply Chain & Logistics",
        "company": "GlobalDistro",
        "location": "Chicago, IL",
        "description": (
            "Redesign end-to-end supply chain for a $2B distribution company. "
            "P&L responsibility for 1,200-person organization."
        ),
        "salary_raw": None,
    },
    {
        "source_id": "mock-004",
        "title": "Director of Strategic Initiatives",
        "company": "HealthFirst",
        "location": "Boston, MA (Hybrid)",
        "description": (
            "Lead cross-functional strategic projects for a healthcare platform. "
            "MBA or equivalent experience preferred."
        ),
        "salary_raw": "$200,000 - $275,000",
    },
    {
        "source_id": "mock-005",
        "title": "Head of Business Transformation",
        "company": "FinEdge Partners",
        "location": "London, UK",
        "description": (
            "Spearhead digital transformation for a mid-market PE portfolio company. "
            "Strong change-management background required."
        ),
        "salary_raw": "£180,000 - £250,000",
    },
]


class MockCollector(BaseCollector):
    """A collector that returns hard-coded sample postings.

    Useful for development, testing, and demo purposes.
    """

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "mock"

    async def collect(self) -> list[RawJobPosting]:
        """Return synthetic executive job postings.

        Returns:
            A list of five sample :class:`RawJobPosting` instances.
        """
        now = datetime.now(UTC)
        postings: list[RawJobPosting] = []
        for idx, data in enumerate(_SAMPLE_POSTINGS):
            postings.append(
                RawJobPosting(
                    source=self.source_name,
                    source_id=str(data["source_id"]),
                    title=str(data["title"]),
                    company=data.get("company"),
                    location=data.get("location"),
                    description=str(data.get("description", "")),
                    salary_raw=data.get("salary_raw"),
                    posted_at=now - timedelta(days=idx),
                    collected_at=now,
                )
            )
        return postings
