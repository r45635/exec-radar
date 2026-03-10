"""Tests for Pydantic schema validation."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import (
    NormalizedJobPosting,
    RemotePolicy,
    SeniorityLevel,
)
from packages.schemas.raw_job import RawJobPosting


class TestRawJobPosting:
    """Validation tests for RawJobPosting."""

    def test_minimal_valid(self) -> None:
        """A posting with only required fields should be valid."""
        posting = RawJobPosting(
            source="test",
            source_id="1",
            title="CEO",
        )
        assert posting.source == "test"
        assert posting.title == "CEO"
        assert posting.collected_at is not None

    def test_full_valid(self) -> None:
        """A posting with all fields populated should be valid."""
        posting = RawJobPosting(
            source="linkedin",
            source_id="abc-123",
            source_url="https://example.com/job/123",
            title="VP Operations",
            company="Acme",
            location="NYC",
            description="Great role",
            salary_raw="$300k",
            posted_at=datetime(2025, 1, 15),
            meta={"is_promoted": True},
        )
        assert posting.company == "Acme"
        assert posting.meta["is_promoted"] is True

    def test_missing_required_source(self) -> None:
        """Omitting ``source`` should raise a validation error."""
        with pytest.raises(ValidationError):
            RawJobPosting(source_id="1", title="CEO")  # type: ignore[call-arg]

    def test_missing_required_title(self) -> None:
        """Omitting ``title`` should raise a validation error."""
        with pytest.raises(ValidationError):
            RawJobPosting(source="test", source_id="1")  # type: ignore[call-arg]


class TestNormalizedJobPosting:
    """Validation tests for NormalizedJobPosting."""

    def test_defaults(self) -> None:
        """Default values should be applied correctly."""
        job = NormalizedJobPosting(
            source="mock",
            source_id="x",
            title="CTO",
        )
        assert job.seniority == SeniorityLevel.OTHER
        assert job.remote_policy == RemotePolicy.UNKNOWN
        assert job.tags == []
        assert len(job.id) == 32  # sha256 hex, truncated

    def test_id_is_deterministic(self) -> None:
        """Same source + source_id should always produce the same ID."""
        job1 = NormalizedJobPosting(source="mock", source_id="x", title="CTO")
        job2 = NormalizedJobPosting(source="mock", source_id="x", title="CEO")
        assert job1.id == job2.id

    def test_different_source_id_gives_different_id(self) -> None:
        """Different source_id should produce a different ID."""
        job1 = NormalizedJobPosting(source="mock", source_id="x", title="CTO")
        job2 = NormalizedJobPosting(source="mock", source_id="y", title="CTO")
        assert job1.id != job2.id

    def test_seniority_enum(self) -> None:
        """Seniority should accept valid enum values."""
        job = NormalizedJobPosting(
            source="mock",
            source_id="x",
            title="COO",
            seniority=SeniorityLevel.C_LEVEL,
        )
        assert job.seniority == SeniorityLevel.C_LEVEL

    def test_invalid_seniority(self) -> None:
        """An invalid seniority string should fail validation."""
        with pytest.raises(ValidationError):
            NormalizedJobPosting(
                source="mock",
                source_id="x",
                title="COO",
                seniority="emperor",  # type: ignore[arg-type]
            )


class TestFitScore:
    """Validation tests for FitScore."""

    def test_valid_score(self) -> None:
        """A score with all dimensions within bounds should be valid."""
        score = FitScore(
            job_id="abc",
            overall=0.85,
            title_match=0.9,
            seniority_match=1.0,
            location_match=0.5,
            skills_match=0.7,
            explanation="Good fit",
        )
        assert score.overall == 0.85

    def test_overall_out_of_range(self) -> None:
        """Overall score > 1.0 should fail validation."""
        with pytest.raises(ValidationError):
            FitScore(job_id="abc", overall=1.5)

    def test_negative_score(self) -> None:
        """Negative dimension score should fail validation."""
        with pytest.raises(ValidationError):
            FitScore(job_id="abc", overall=0.5, title_match=-0.1)


class TestNormalizedJobSalaryValidator:
    """Tests for the salary_min <= salary_max model validator."""

    def test_valid_salary_range(self) -> None:
        """salary_min < salary_max should pass."""
        job = NormalizedJobPosting(
            source="test",
            source_id="1",
            title="COO",
            salary_min=200_000,
            salary_max=300_000,
            salary_currency="USD",
        )
        assert job.salary_min == 200_000

    def test_equal_salary_bounds(self) -> None:
        """salary_min == salary_max should pass."""
        job = NormalizedJobPosting(
            source="test",
            source_id="1",
            title="COO",
            salary_min=250_000,
            salary_max=250_000,
        )
        assert job.salary_min == job.salary_max

    def test_inverted_salary_range_rejected(self) -> None:
        """salary_min > salary_max should fail validation."""
        with pytest.raises(ValidationError, match="salary_min"):
            NormalizedJobPosting(
                source="test",
                source_id="1",
                title="COO",
                salary_min=500_000,
                salary_max=200_000,
            )

    def test_partial_salary_allowed(self) -> None:
        """Only salary_min set (no max) should pass."""
        job = NormalizedJobPosting(
            source="test",
            source_id="1",
            title="COO",
            salary_min=200_000,
        )
        assert job.salary_max is None


class TestModelImmutability:
    """Verify that schema models are frozen."""

    def test_raw_job_is_frozen(self) -> None:
        """RawJobPosting should reject attribute assignment."""
        posting = RawJobPosting(source="test", source_id="1", title="CEO")
        with pytest.raises(ValidationError):
            posting.title = "CFO"  # type: ignore[misc]

    def test_normalized_job_is_frozen(self) -> None:
        """NormalizedJobPosting should reject attribute assignment."""
        job = NormalizedJobPosting(source="test", source_id="1", title="CEO")
        with pytest.raises(ValidationError):
            job.title = "CFO"  # type: ignore[misc]

    def test_fit_score_is_frozen(self) -> None:
        """FitScore should reject attribute assignment."""
        score = FitScore(job_id="x", overall=0.5)
        with pytest.raises(ValidationError):
            score.overall = 0.9  # type: ignore[misc]
