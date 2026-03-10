"""Unit tests for the rule-based ranker."""


from rankers import ExecutiveProfile, RuleBasedRanker
from schemas import NormalizedJobPosting
from schemas.normalized_job_posting import EmploymentType, SeniorityLevel


def _make_job(**overrides) -> NormalizedJobPosting:
    """Helper to create a NormalizedJobPosting with sensible defaults."""
    defaults = dict(
        id="test-job-001",
        source="mock",
        source_id="mock-001",
        url="https://example.com/jobs/cto-001",
        title="Chief Technology Officer",
        seniority=SeniorityLevel.C_SUITE,
        employment_type=EmploymentType.FULL_TIME,
        company="Acme Corp",
        location="San Francisco, CA",
        remote=True,
        salary_min=250_000.0,
        salary_max=300_000.0,
        skills=["python", "aws", "leadership", "strategy"],
        keywords=["cto", "engineering"],
    )
    defaults.update(overrides)
    return NormalizedJobPosting(**defaults)


def _make_profile(**overrides) -> ExecutiveProfile:
    """Helper to create an ExecutiveProfile with sensible defaults."""
    defaults = dict(
        desired_titles=["CTO", "Chief Technology Officer"],
        desired_seniority=[SeniorityLevel.C_SUITE, SeniorityLevel.VP],
        required_skills=["python", "leadership"],
        preferred_skills=["aws", "strategy"],
        preferred_locations=["San Francisco"],
        remote_only=False,
        min_salary=200_000.0,
    )
    defaults.update(overrides)
    return ExecutiveProfile(**defaults)


class TestRuleBasedRanker:
    def setup_method(self) -> None:
        self.ranker = RuleBasedRanker()

    def test_ranker_id(self) -> None:
        assert self.ranker.ranker_id == "rule_based_v1"

    def test_score_returns_fit_score(self) -> None:
        """score() returns a FitScore object with the correct job_id and ranker."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert result.job_id == job.id
        assert result.ranker == self.ranker.ranker_id

    def test_score_within_bounds(self) -> None:
        """Overall score is always in [0, 100]."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert 0.0 <= result.score <= 100.0

    def test_high_score_for_strong_match(self) -> None:
        """A job that matches all profile criteria should score above 70."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert result.score >= 70.0

    def test_low_score_for_seniority_mismatch(self) -> None:
        """An entry-level job against a C-suite profile should score lower."""
        job = _make_job(
            title="Junior Engineer",
            seniority=SeniorityLevel.ENTRY,
            salary_min=70_000.0,
            salary_max=90_000.0,
            skills=["python"],
        )
        profile = _make_profile(min_salary=200_000.0)
        result = self.ranker.score(job, profile)
        assert result.score < 60.0

    def test_remote_only_profile_penalizes_non_remote(self) -> None:
        """remote_only=True should give location_score=0 for non-remote jobs."""
        job = _make_job(remote=False, location="Chicago, IL")
        profile = _make_profile(remote_only=True)
        result = self.ranker.score(job, profile)
        assert result.location_score == 0.0

    def test_remote_only_profile_rewards_remote(self) -> None:
        """remote_only=True should give location_score=100 for remote jobs."""
        job = _make_job(remote=True)
        profile = _make_profile(remote_only=True)
        result = self.ranker.score(job, profile)
        assert result.location_score == 100.0

    def test_dimension_scores_present(self) -> None:
        """All dimension scores should be populated."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert result.title_score is not None
        assert result.skill_score is not None
        assert result.location_score is not None
        assert result.compensation_score is not None

    def test_explanation_present(self) -> None:
        """Explanation string should be non-empty."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert result.explanation
        assert len(result.explanation) > 0

    def test_no_required_skills_gives_neutral_score(self) -> None:
        """When profile has no skills specified, skill_score should be neutral (50)."""
        job = _make_job(skills=[])
        profile = _make_profile(required_skills=[], preferred_skills=[])
        result = self.ranker.score(job, profile)
        assert result.skill_score == 50.0

    def test_missing_salary_penalizes_compensation(self) -> None:
        """Jobs without salary info should get a reduced compensation score."""
        job = _make_job(salary_min=None, salary_max=None)
        profile = _make_profile(min_salary=200_000.0)
        result = self.ranker.score(job, profile)
        assert result.compensation_score == 40.0

    def test_salary_above_minimum_scores_well(self) -> None:
        """Jobs with salary above the minimum should score >= 80."""
        job = _make_job(salary_min=220_000.0, salary_max=300_000.0)
        profile = _make_profile(min_salary=200_000.0)
        result = self.ranker.score(job, profile)
        assert result.compensation_score >= 80.0

    def test_salary_below_minimum_penalized(self) -> None:
        """Jobs with salary significantly below minimum should score < 60."""
        job = _make_job(salary_min=100_000.0, salary_max=120_000.0)
        profile = _make_profile(min_salary=250_000.0)
        result = self.ranker.score(job, profile)
        assert result.compensation_score < 60.0

    def test_empty_profile_no_crash(self) -> None:
        """A completely empty profile should not raise any exceptions."""
        job = _make_job()
        profile = ExecutiveProfile()
        result = self.ranker.score(job, profile)
        assert 0.0 <= result.score <= 100.0

    def test_details_contains_weights(self) -> None:
        """Score details should include the weight configuration."""
        job = _make_job()
        profile = _make_profile()
        result = self.ranker.score(job, profile)
        assert result.details is not None
        assert "weights" in result.details
