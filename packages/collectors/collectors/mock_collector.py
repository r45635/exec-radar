"""Mock collector that returns hard-coded sample postings for testing and development."""

import logging
from datetime import datetime

from schemas import RawJobPosting

from .base import BaseCollector

logger = logging.getLogger(__name__)

_MOCK_POSTINGS = [
    {
        "source_id": "mock-001",
        "url": "https://example.com/jobs/cto-001",
        "title": "Chief Technology Officer",
        "company": "Acme Corp",
        "location": "San Francisco, CA (Remote OK)",
        "description": (
            "We are seeking an experienced CTO to lead our engineering organization. "
            "You will drive technical strategy, mentor senior engineers, and collaborate "
            "with the executive team on product vision. Requirements: 15+ years of software "
            "engineering experience, 5+ years in a VP/CTO role, strong Python and cloud skills."
        ),
        "salary_raw": "$280,000 - $320,000",
        "posted_at": "2024-01-15T10:00:00",
    },
    {
        "source_id": "mock-002",
        "url": "https://example.com/jobs/vp-eng-002",
        "title": "VP of Engineering",
        "company": "TechStartup Inc.",
        "location": "New York, NY",
        "description": (
            "Join us as VP of Engineering to scale our platform. "
            "You will manage multiple engineering teams and own our cloud infrastructure roadmap. "
            "5+ years managing distributed teams required."
        ),
        "salary_raw": "$200,000 - $250,000",
        "posted_at": "2024-01-16T08:30:00",
    },
    {
        "source_id": "mock-003",
        "url": "https://example.com/jobs/director-eng-003",
        "title": "Director of Engineering, Platform",
        "company": "ScaleUp LLC",
        "location": "Remote",
        "description": (
            "Lead the platform engineering team building core infrastructure services. "
            "Ideal candidate has experience with Kubernetes, Terraform, and Python microservices."
        ),
        "salary_raw": None,
        "posted_at": "2024-01-17T09:00:00",
    },
]


class MockCollector(BaseCollector):
    """Returns a fixed set of sample job postings without making any network calls.

    Use this collector for local development, testing, and CI pipelines.
    """

    @property
    def source_name(self) -> str:
        return "mock"

    async def collect(self) -> list[RawJobPosting]:
        """Return the pre-defined list of mock job postings."""
        logger.info("MockCollector returning %d sample postings", len(_MOCK_POSTINGS))
        return [
            RawJobPosting(
                source=self.source_name,
                source_id=item["source_id"],
                url=item["url"],  # type: ignore[arg-type]
                title=item["title"],
                company=item["company"],
                location=item.get("location"),
                description=item.get("description"),
                salary_raw=item.get("salary_raw"),
                posted_at=datetime.fromisoformat(item["posted_at"]) if item.get("posted_at") else None,
                raw_data=item,
            )
            for item in _MOCK_POSTINGS
        ]
