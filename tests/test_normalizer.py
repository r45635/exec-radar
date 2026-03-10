"""Unit tests for the SimpleNormalizer."""


from normalizers import SimpleNormalizer
from schemas import RawJobPosting
from schemas.normalized_job_posting import EmploymentType, SeniorityLevel


def _make_raw(**overrides) -> RawJobPosting:
    """Helper to build a RawJobPosting with defaults."""
    defaults = dict(
        source="test",
        source_id="test-001",
        url="https://example.com/jobs/1",
        title="Chief Technology Officer",
        company="Acme Corp",
        location="San Francisco, CA (Remote OK)",
        description="We need a CTO with strong python and aws skills. Leadership required.",
        salary_raw="$250,000 - $300,000",
    )
    defaults.update(overrides)
    return RawJobPosting(**defaults)


class TestSimpleNormalizer:
    def setup_method(self) -> None:
        self.normalizer = SimpleNormalizer()

    def test_returns_normalized_posting(self) -> None:
        """normalize() returns a NormalizedJobPosting."""
        from schemas import NormalizedJobPosting
        result = self.normalizer.normalize(_make_raw())
        assert isinstance(result, NormalizedJobPosting)

    def test_id_is_generated(self) -> None:
        """Each call to normalize() generates a new UUID id."""
        r1 = self.normalizer.normalize(_make_raw())
        r2 = self.normalizer.normalize(_make_raw())
        assert r1.id != r2.id

    def test_source_and_source_id_preserved(self) -> None:
        """Source metadata is copied from the raw posting."""
        result = self.normalizer.normalize(_make_raw(source="linkedin", source_id="li-999"))
        assert result.source == "linkedin"
        assert result.source_id == "li-999"

    def test_infers_c_suite_seniority(self) -> None:
        """'Chief' in title → C_SUITE seniority."""
        result = self.normalizer.normalize(_make_raw(title="Chief Technology Officer"))
        assert result.seniority == SeniorityLevel.C_SUITE

    def test_infers_vp_seniority(self) -> None:
        """'VP of' in title → VP seniority."""
        result = self.normalizer.normalize(_make_raw(title="VP of Engineering"))
        assert result.seniority == SeniorityLevel.VP

    def test_infers_director_seniority(self) -> None:
        """'Director' in title → DIRECTOR seniority."""
        result = self.normalizer.normalize(_make_raw(title="Director of Engineering"))
        assert result.seniority == SeniorityLevel.DIRECTOR

    def test_unknown_seniority_for_ambiguous_title(self) -> None:
        """Titles with no recognised seniority keywords → UNKNOWN."""
        result = self.normalizer.normalize(_make_raw(title="Manager"))
        assert result.seniority == SeniorityLevel.UNKNOWN

    def test_detects_remote_from_location(self) -> None:
        """'Remote' in location → remote=True."""
        result = self.normalizer.normalize(_make_raw(location="Remote"))
        assert result.remote is True

    def test_detects_remote_from_description(self) -> None:
        """'remote' in description → remote=True."""
        result = self.normalizer.normalize(
            _make_raw(location="New York, NY", description="This is a fully remote position.")
        )
        assert result.remote is True

    def test_non_remote_job(self) -> None:
        """No remote keywords → remote=False."""
        result = self.normalizer.normalize(
            _make_raw(location="Chicago, IL", description="On-site required. No telecommuting.")
        )
        assert result.remote is False

    def test_parses_salary_range(self) -> None:
        """Salary range string is parsed into min/max floats."""
        result = self.normalizer.normalize(_make_raw(salary_raw="$250,000 - $300,000"))
        assert result.salary_min == 250_000.0
        assert result.salary_max == 300_000.0

    def test_no_salary_returns_none(self) -> None:
        """Missing salary → salary_min and salary_max are None."""
        result = self.normalizer.normalize(_make_raw(salary_raw=None))
        assert result.salary_min is None
        assert result.salary_max is None

    def test_extracts_skills_from_description(self) -> None:
        """Known skill keywords in description are extracted."""
        result = self.normalizer.normalize(
            _make_raw(description="Must have python, aws, and kubernetes experience.")
        )
        assert "python" in result.skills
        assert "aws" in result.skills
        assert "kubernetes" in result.skills

    def test_empty_description_gives_no_skills(self) -> None:
        """No description → empty skills list."""
        result = self.normalizer.normalize(_make_raw(description=None))
        assert result.skills == []

    def test_interim_employment_type(self) -> None:
        """'Interim' in title → INTERIM employment type."""
        result = self.normalizer.normalize(_make_raw(title="Interim CTO"))
        assert result.employment_type == EmploymentType.INTERIM

    def test_full_time_is_default(self) -> None:
        """No employment-type keywords → defaults to FULL_TIME."""
        result = self.normalizer.normalize(_make_raw())
        assert result.employment_type == EmploymentType.FULL_TIME
