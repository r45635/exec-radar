"""Tests for the simple normalizer."""

from __future__ import annotations

from datetime import datetime

import pytest

from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.schemas.normalized_job import RemotePolicy, SeniorityLevel
from packages.schemas.raw_job import RawJobPosting


@pytest.fixture()
def normalizer() -> SimpleNormalizer:
    """Return a fresh normalizer instance."""
    return SimpleNormalizer()


def _raw(
    title: str = "Software Engineer",
    location: str | None = None,
    description: str = "",
    salary_raw: str | None = None,
) -> RawJobPosting:
    """Helper to build a RawJobPosting with defaults."""
    return RawJobPosting(
        source="test",
        source_id="1",
        title=title,
        location=location,
        description=description,
        salary_raw=salary_raw,
        posted_at=datetime(2025, 6, 1),
    )


class TestSimpleNormalizer:
    """Tests for SimpleNormalizer transformation logic."""

    def test_seniority_coo(self, normalizer: SimpleNormalizer) -> None:
        """COO title should map to C_LEVEL."""
        result = normalizer.normalize(_raw(title="Chief Operating Officer"))
        assert result.seniority == SeniorityLevel.C_LEVEL

    def test_seniority_vp(self, normalizer: SimpleNormalizer) -> None:
        """VP title should map to VP."""
        result = normalizer.normalize(_raw(title="VP of Operations"))
        assert result.seniority == SeniorityLevel.VP

    def test_seniority_svp(self, normalizer: SimpleNormalizer) -> None:
        """SVP title should map to SVP."""
        result = normalizer.normalize(_raw(title="SVP, Supply Chain"))
        assert result.seniority == SeniorityLevel.SVP

    def test_seniority_director(self, normalizer: SimpleNormalizer) -> None:
        """Director title should map to DIRECTOR."""
        result = normalizer.normalize(_raw(title="Director of Strategy"))
        assert result.seniority == SeniorityLevel.DIRECTOR

    def test_seniority_head(self, normalizer: SimpleNormalizer) -> None:
        """Head of X should map to HEAD."""
        result = normalizer.normalize(_raw(title="Head of Transformation"))
        assert result.seniority == SeniorityLevel.HEAD

    def test_remote_policy_remote(self, normalizer: SimpleNormalizer) -> None:
        """Location containing 'remote' should yield REMOTE."""
        result = normalizer.normalize(_raw(location="Remote"))
        assert result.remote_policy == RemotePolicy.REMOTE

    def test_remote_policy_hybrid(self, normalizer: SimpleNormalizer) -> None:
        """Location containing 'hybrid' should yield HYBRID."""
        result = normalizer.normalize(_raw(location="NYC (Hybrid)"))
        assert result.remote_policy == RemotePolicy.HYBRID

    def test_salary_parsing_usd(self, normalizer: SimpleNormalizer) -> None:
        """USD salary range should be parsed correctly."""
        result = normalizer.normalize(_raw(salary_raw="$200,000 - $300,000"))
        assert result.salary_min == 200_000
        assert result.salary_max == 300_000
        assert result.salary_currency == "USD"

    def test_salary_parsing_gbp(self, normalizer: SimpleNormalizer) -> None:
        """GBP salary should be parsed correctly."""
        result = normalizer.normalize(_raw(salary_raw="£150,000"))
        assert result.salary_min == 150_000
        assert result.salary_currency == "GBP"

    def test_salary_none(self, normalizer: SimpleNormalizer) -> None:
        """Missing salary should remain None."""
        result = normalizer.normalize(_raw(salary_raw=None))
        assert result.salary_min is None
        assert result.salary_max is None

    def test_tag_extraction(self, normalizer: SimpleNormalizer) -> None:
        """Tags should be extracted from title and description."""
        result = normalizer.normalize(
            _raw(
                title="VP of Operations",
                description="Responsible for supply chain and logistics.",
            )
        )
        assert "operations" in result.tags
        assert "supply chain" in result.tags
        assert "logistics" in result.tags

    def test_scope_signal_tags(self, normalizer: SimpleNormalizer) -> None:
        """Scope signals should be extracted as tags."""
        result = normalizer.normalize(
            _raw(
                title="VP Global Operations",
                description=(
                    "Lead multi-site manufacturing across business unit. "
                    "Enterprise-wide transformation."
                ),
            )
        )
        assert "global" in result.tags
        assert "multi-site" in result.tags
        assert "business unit" in result.tags
        assert "enterprise-wide" in result.tags

    def test_site_scope_tag(self, normalizer: SimpleNormalizer) -> None:
        """Narrow site-level scope should be tagged."""
        result = normalizer.normalize(
            _raw(
                title="Plant Director",
                description="Manage single site operations at the plant.",
            )
        )
        assert "site" in result.tags
        assert "plant" in result.tags
        assert "single site" in result.tags

    def test_html_stripping(self, normalizer: SimpleNormalizer) -> None:
        """HTML tags should be removed from description."""
        result = normalizer.normalize(_raw(description="<p>Great <b>role</b> for leaders.</p>"))
        assert "<" not in result.description_plain
        assert "Great role for leaders." in result.description_plain

    def test_preserves_source_fields(self, normalizer: SimpleNormalizer) -> None:
        """Source and source_id should be passed through."""
        raw = _raw(title="CEO")
        result = normalizer.normalize(raw)
        assert result.source == raw.source
        assert result.source_id == raw.source_id


class TestExtendedNormalization:
    """Tests for newly added normalization fields."""

    def test_title_family_coo(self, normalizer: SimpleNormalizer) -> None:
        """COO should resolve to COO title family."""
        result = normalizer.normalize(_raw(title="Chief Operating Officer"))
        assert result.title_family == "COO"

    def test_title_family_vp_operations(self, normalizer: SimpleNormalizer) -> None:
        """VP Operations should resolve to VP_OPERATIONS family."""
        result = normalizer.normalize(_raw(title="VP of Operations"))
        assert result.title_family == "VP_OPERATIONS"

    def test_title_family_none_for_unknown(self, normalizer: SimpleNormalizer) -> None:
        """Unknown title should have no family."""
        result = normalizer.normalize(_raw(title="Software Engineer"))
        assert result.title_family is None

    def test_industry_family_semiconductor(self, normalizer: SimpleNormalizer) -> None:
        """Descriptions with semiconductor signals should be classified."""
        result = normalizer.normalize(
            _raw(description="Manage wafer fab and foundry operations for semiconductor devices.")
        )
        assert result.industry_family == "semiconductor"

    def test_industry_family_automotive(self, normalizer: SimpleNormalizer) -> None:
        """Descriptions with automotive signals should be classified."""
        result = normalizer.normalize(
            _raw(description="Lead IATF 16949 compliance and APQP processes for automotive OEM.")
        )
        assert result.industry_family == "automotive"

    def test_industry_family_other(self, normalizer: SimpleNormalizer) -> None:
        """Vague descriptions should classify as other."""
        result = normalizer.normalize(_raw(description="Lead team."))
        assert result.industry_family == "other"

    def test_job_function_family_from_title_family(self, normalizer: SimpleNormalizer) -> None:
        """Job function should be derived from title family."""
        result = normalizer.normalize(_raw(title="VP of Supply Chain"))
        assert result.job_function_family == "supply_chain"

    def test_job_function_family_from_title_text(self, normalizer: SimpleNormalizer) -> None:
        """Job function should be derived from title text when no family."""
        result = normalizer.normalize(_raw(title="Senior Manufacturing Manager"))
        assert result.job_function_family == "manufacturing"

    def test_scope_level_global(self, normalizer: SimpleNormalizer) -> None:
        """Global scope markers should classify as global."""
        result = normalizer.normalize(
            _raw(
                title="VP Global Operations",
                description="Lead multi-site manufacturing across international footprint.",
            )
        )
        assert result.scope_level == "global"

    def test_scope_level_site(self, normalizer: SimpleNormalizer) -> None:
        """Narrow scope markers should classify as site."""
        result = normalizer.normalize(
            _raw(
                title="Plant Director",
                description="Manage single site production at local plant.",
            )
        )
        assert result.scope_level == "site"

    def test_is_software_heavy(self, normalizer: SimpleNormalizer) -> None:
        """Software-dominated roles should be flagged."""
        result = normalizer.normalize(
            _raw(
                title="VP Engineering",
                description=(
                    "Lead software development using kubernetes, docker, "
                    "and microservices architecture. Focus on CI/CD."
                ),
            )
        )
        assert result.is_software_heavy is True

    def test_is_not_software_heavy(self, normalizer: SimpleNormalizer) -> None:
        """Non-software roles should not be flagged."""
        result = normalizer.normalize(
            _raw(title="VP Operations", description="Lead manufacturing operations.")
        )
        assert result.is_software_heavy is False

    def test_is_gtm_heavy(self, normalizer: SimpleNormalizer) -> None:
        """GTM-dominated roles should be flagged."""
        result = normalizer.normalize(
            _raw(
                title="VP Revenue",
                description=(
                    "Own demand generation and revenue operations. "
                    "Build go-to-market strategy."
                ),
            )
        )
        assert result.is_gtm_heavy is True

    def test_is_semiconductor_like(self, normalizer: SimpleNormalizer) -> None:
        """Semiconductor roles should be flagged."""
        result = normalizer.normalize(
            _raw(description="Manage wafer fab and foundry backend operations.")
        )
        assert result.is_semiconductor_like is True

    def test_not_semiconductor_like(self, normalizer: SimpleNormalizer) -> None:
        """Non-semi roles should not be flagged."""
        result = normalizer.normalize(
            _raw(description="Lead marketing team for B2B SaaS product.")
        )
        assert result.is_semiconductor_like is False
