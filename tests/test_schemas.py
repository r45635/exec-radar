"""Unit tests for shared Pydantic schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError
from schemas import FitScore, NormalizedJobPosting, RawJobPosting
from schemas.normalized_job_posting import EmploymentType, SeniorityLevel

# ---------------------------------------------------------------------------
# RawJobPosting
# ---------------------------------------------------------------------------

class TestRawJobPosting:
    def test_minimal_valid(self) -> None:
        """RawJobPosting can be created with only required fields."""
        raw = RawJobPosting(
            source="test",
            source_id="test-001",
            url="https://example.com/jobs/1",
            title="CTO",
            company="Acme",
        )
        assert raw.source == "test"
        assert raw.location is None
        assert raw.description is None

    def test_full_valid(self) -> None:
        """RawJobPosting accepts all optional fields."""
        raw = RawJobPosting(
            source="linkedin",
            source_id="li-001",
            url="https://linkedin.com/jobs/1",
            title="VP of Engineering",
            company="BigCo",
            location="New York, NY",
            description="Lead engineering teams...",
            salary_raw="$200,000 - $250,000",
            posted_at=datetime(2024, 1, 15),
        )
        assert raw.salary_raw == "$200,000 - $250,000"
        assert raw.posted_at == datetime(2024, 1, 15)

    def test_fetched_at_defaults_to_now(self) -> None:
        """fetched_at is auto-populated when not provided."""
        raw = RawJobPosting(
            source="test",
            source_id="x",
            url="https://example.com/job",
            title="CTO",
            company="Co",
        )
        assert raw.fetched_at is not None
        assert isinstance(raw.fetched_at, datetime)

    def test_invalid_url_raises(self) -> None:
        """An invalid URL raises a ValidationError."""
        with pytest.raises(ValidationError):
            RawJobPosting(
                source="test",
                source_id="x",
                url="not-a-url",
                title="CTO",
                company="Co",
            )


# ---------------------------------------------------------------------------
# NormalizedJobPosting
# ---------------------------------------------------------------------------

class TestNormalizedJobPosting:
    def test_minimal_valid(self) -> None:
        """NormalizedJobPosting can be created with required fields only."""
        job = NormalizedJobPosting(
            id="abc-123",
            source="mock",
            source_id="mock-001",
            url="https://example.com/jobs/1",
            title="Chief Technology Officer",
            company="Acme Corp",
        )
        assert job.seniority == SeniorityLevel.UNKNOWN
        assert job.employment_type == EmploymentType.UNKNOWN
        assert job.remote is False
        assert job.skills == []

    def test_seniority_enum_values(self) -> None:
        """SeniorityLevel enum has the expected string values."""
        assert SeniorityLevel.C_SUITE == "c_suite"
        assert SeniorityLevel.VP == "vp"
        assert SeniorityLevel.DIRECTOR == "director"
        assert SeniorityLevel.SENIOR == "senior"
        assert SeniorityLevel.UNKNOWN == "unknown"

    def test_employment_type_enum_values(self) -> None:
        """EmploymentType enum has the expected string values."""
        assert EmploymentType.FULL_TIME == "full_time"
        assert EmploymentType.INTERIM == "interim"
        assert EmploymentType.BOARD == "board"

    def test_full_valid(self) -> None:
        """NormalizedJobPosting accepts all optional fields."""
        job = NormalizedJobPosting(
            id="xyz-999",
            source="mock",
            source_id="mock-999",
            url="https://example.com/jobs/999",
            title="VP of Engineering",
            seniority=SeniorityLevel.VP,
            employment_type=EmploymentType.FULL_TIME,
            company="StartupCo",
            location="San Francisco, CA",
            remote=True,
            salary_min=200_000.0,
            salary_max=250_000.0,
            skills=["python", "aws"],
            keywords=["vp", "engineering"],
        )
        assert job.salary_min == 200_000.0
        assert job.remote is True
        assert "python" in job.skills

    def test_normalized_at_defaults_to_now(self) -> None:
        """normalized_at is auto-populated when not provided."""
        job = NormalizedJobPosting(
            id="t",
            source="s",
            source_id="s-1",
            url="https://example.com/j",
            title="CTO",
            company="Co",
        )
        assert isinstance(job.normalized_at, datetime)


# ---------------------------------------------------------------------------
# FitScore
# ---------------------------------------------------------------------------

class TestFitScore:
    def test_valid_score(self) -> None:
        """FitScore is created with a valid score value."""
        fs = FitScore(job_id="job-1", ranker="rule_based_v1", score=75.5)
        assert fs.score == 75.5
        assert fs.ranker == "rule_based_v1"

    def test_score_bounds(self) -> None:
        """Score must be between 0 and 100 inclusive."""
        # Valid boundary values
        FitScore(job_id="j", ranker="r", score=0.0)
        FitScore(job_id="j", ranker="r", score=100.0)

    def test_score_below_zero_raises(self) -> None:
        """Score below 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            FitScore(job_id="j", ranker="r", score=-1.0)

    def test_score_above_100_raises(self) -> None:
        """Score above 100 raises ValidationError."""
        with pytest.raises(ValidationError):
            FitScore(job_id="j", ranker="r", score=100.1)

    def test_dimension_scores_optional(self) -> None:
        """Dimension scores are optional and default to None."""
        fs = FitScore(job_id="j", ranker="r", score=50.0)
        assert fs.title_score is None
        assert fs.skill_score is None
        assert fs.location_score is None
        assert fs.compensation_score is None

    def test_all_dimension_scores(self) -> None:
        """FitScore stores all dimension scores correctly."""
        fs = FitScore(
            job_id="j",
            ranker="r",
            score=82.5,
            title_score=90.0,
            skill_score=80.0,
            location_score=75.0,
            compensation_score=85.0,
            explanation="Great match",
        )
        assert fs.title_score == 90.0
        assert fs.explanation == "Great match"

    def test_scored_at_defaults_to_now(self) -> None:
        """scored_at is auto-populated when not provided."""
        fs = FitScore(job_id="j", ranker="r", score=50.0)
        assert isinstance(fs.scored_at, datetime)
