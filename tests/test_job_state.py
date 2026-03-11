"""Tests for job state tracking (new, seen, updated)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.db.job_state import (
    JOB_STATE_NEW,
    JOB_STATE_SEEN,
    JOB_STATE_UPDATED,
    classify_job_state,
    compute_content_hash,
)
from packages.schemas.normalized_job import NormalizedJobPosting, RemotePolicy, SeniorityLevel


@pytest.fixture
def sample_job() -> NormalizedJobPosting:
    """Create a sample normalized job posting."""
    return NormalizedJobPosting(
        id="abc123",
        source="greenhouse:discord",
        source_id="12345",
        source_url="https://example.com/jobs/12345",
        title="VP of Operations",
        company="Example Corp",
        location="New York, NY",
        remote_policy=RemotePolicy.HYBRID,
        seniority=SeniorityLevel.VP,
        description_plain="Lead the operations team.",
        salary_min=200000.0,
        salary_max=300000.0,
        salary_currency="USD",
        tags=["operations", "leadership"],
        posted_at=None,
        normalized_at=datetime.now(UTC),
    )


class TestComputeContentHash:
    """Test content hash computation."""

    def test_hash_is_deterministic(self, sample_job: NormalizedJobPosting) -> None:
        """Same job should produce same hash."""
        hash1 = compute_content_hash(sample_job)
        hash2 = compute_content_hash(sample_job)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_hash_changes_on_title_change(self, sample_job: NormalizedJobPosting) -> None:
        """Hash should change when title changes."""
        hash1 = compute_content_hash(sample_job)

        modified = sample_job.model_copy(update={"title": "Chief Operating Officer"})
        hash2 = compute_content_hash(modified)

        assert hash1 != hash2

    def test_hash_changes_on_description_change(self, sample_job: NormalizedJobPosting) -> None:
        """Hash should change when description changes."""
        hash1 = compute_content_hash(sample_job)

        modified = sample_job.model_copy(update={"description_plain": "New description"})
        hash2 = compute_content_hash(modified)

        assert hash1 != hash2

    def test_hash_changes_on_salary_change(self, sample_job: NormalizedJobPosting) -> None:
        """Hash should change when salary changes."""
        hash1 = compute_content_hash(sample_job)

        modified = sample_job.model_copy(update={"salary_min": 250000.0})
        hash2 = compute_content_hash(modified)

        assert hash1 != hash2

    def test_hash_changes_on_tags_change(self, sample_job: NormalizedJobPosting) -> None:
        """Hash should change when tags change."""
        hash1 = compute_content_hash(sample_job)

        modified = sample_job.model_copy(update={"tags": ["operations", "leadership", "strategy"]})
        hash2 = compute_content_hash(modified)

        assert hash1 != hash2

    def test_hash_ignores_metadata(self, sample_job: NormalizedJobPosting) -> None:
        """Hash should not change for metadata like source_url, location, remote_policy."""
        hash1 = compute_content_hash(sample_job)

        modified = sample_job.model_copy(
            update={
                "source_url": "https://different.url.com",
                "location": "Remote",
                "remote_policy": RemotePolicy.REMOTE,
                "seniority": SeniorityLevel.DIRECTOR,
            }
        )
        hash2 = compute_content_hash(modified)

        assert hash1 == hash2


class TestClassifyJobState:
    """Test job state classification."""

    def test_new_job(self) -> None:
        """First-time job should be classified as new."""
        hash1 = "abc123"
        state = classify_job_state(is_new=True, previous_hash=None, current_hash=hash1)
        assert state == JOB_STATE_NEW

    def test_seen_job_unchanged(self) -> None:
        """Job seen before with unchanged content should be 'seen'."""
        hash_value = "abc123"
        state = classify_job_state(
            is_new=False, previous_hash=hash_value, current_hash=hash_value
        )
        assert state == JOB_STATE_SEEN

    def test_updated_job(self) -> None:
        """Job with different content should be 'updated'."""
        state = classify_job_state(
            is_new=False, previous_hash="old_hash", current_hash="new_hash"
        )
        assert state == JOB_STATE_UPDATED

    def test_empty_previous_hash_treated_as_new(self) -> None:
        """Empty previous hash should be treated as new."""
        state = classify_job_state(is_new=False, previous_hash="", current_hash="abc123")
        assert state == JOB_STATE_NEW

    def test_none_previous_hash_treated_as_new(self) -> None:
        """None previous hash should be treated as new."""
        state = classify_job_state(is_new=False, previous_hash=None, current_hash="abc123")
        assert state == JOB_STATE_NEW


class TestJobStateIntegration:
    """Integration tests for job state workflow."""

    def test_job_lifecycle(self, sample_job: NormalizedJobPosting) -> None:
        """Test typical job lifecycle: new → seen → updated → seen."""
        hash1 = compute_content_hash(sample_job)

        # First run: new
        state1 = classify_job_state(is_new=True, previous_hash=None, current_hash=hash1)
        assert state1 == JOB_STATE_NEW

        # Second run: same job, unchanged
        state2 = classify_job_state(is_new=False, previous_hash=hash1, current_hash=hash1)
        assert state2 == JOB_STATE_SEEN

        # Third run: job content updated
        modified = sample_job.model_copy(update={"description_plain": "Updated description"})
        hash2 = compute_content_hash(modified)
        state3 = classify_job_state(is_new=False, previous_hash=hash1, current_hash=hash2)
        assert state3 == JOB_STATE_UPDATED

        # Fourth run: no further changes (after update)
        state4 = classify_job_state(is_new=False, previous_hash=hash2, current_hash=hash2)
        assert state4 == JOB_STATE_SEEN
