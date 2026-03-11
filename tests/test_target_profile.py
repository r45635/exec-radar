"""Tests for the TargetProfile schema."""

from __future__ import annotations

import pytest

from packages.schemas.normalized_job import RemotePolicy, SeniorityLevel
from packages.schemas.target_profile import TargetProfile


class TestTargetProfileDefaults:
    """Verify sane defaults when no arguments are supplied."""

    def test_default_construction(self) -> None:
        """TargetProfile() should succeed without arguments."""
        profile = TargetProfile()
        assert len(profile.target_titles) > 0
        assert len(profile.required_keywords) > 0

    def test_default_weights_sum(self) -> None:
        """Default dimension weights should sum to 1.0."""
        p = TargetProfile()
        total = (
            p.weight_title
            + p.weight_seniority
            + p.weight_industry
            + p.weight_scope
            + p.weight_geography
            + p.weight_keyword_clusters
        )
        assert total == pytest.approx(1.0)

    def test_frozen(self) -> None:
        """Profile instances should be immutable."""
        p = TargetProfile()
        with pytest.raises(Exception):  # noqa: B017
            p.weight_title = 0.5  # type: ignore[misc]


class TestTargetProfileCustom:
    """Verify custom profile construction."""

    def test_custom_titles(self) -> None:
        """Custom target titles should be stored correctly."""
        p = TargetProfile(target_titles=frozenset({"cto", "vp engineering"}))
        assert "cto" in p.target_titles
        assert len(p.target_titles) == 2

    def test_custom_seniority(self) -> None:
        """Custom seniority levels should be stored correctly."""
        p = TargetProfile(target_seniority=frozenset({SeniorityLevel.DIRECTOR}))
        assert SeniorityLevel.DIRECTOR in p.target_seniority
        assert SeniorityLevel.C_LEVEL not in p.target_seniority

    def test_custom_remote_policies(self) -> None:
        """Custom remote policies should be stored correctly."""
        p = TargetProfile(preferred_remote_policies=frozenset({RemotePolicy.ONSITE}))
        assert RemotePolicy.ONSITE in p.preferred_remote_policies

    def test_weight_bounds(self) -> None:
        """Weights outside [0, 1] should fail validation."""
        with pytest.raises(Exception):  # noqa: B017
            TargetProfile(weight_title=1.5)

    def test_excluded_keywords(self) -> None:
        """Excluded keywords should be stored as frozenset."""
        p = TargetProfile(excluded_keywords=frozenset({"unpaid", "intern"}))
        assert "unpaid" in p.excluded_keywords
        assert isinstance(p.excluded_keywords, frozenset)

    def test_target_locations(self) -> None:
        """Target locations should be stored correctly."""
        p = TargetProfile(target_locations=frozenset({"london", "new york"}))
        assert "london" in p.target_locations

    def test_target_industries(self) -> None:
        """Target industries should be stored correctly."""
        p = TargetProfile(target_industries=frozenset({"fintech", "healthcare"}))
        assert "fintech" in p.target_industries

    def test_company_preferences(self) -> None:
        """Preferred and excluded companies should be stored correctly."""
        p = TargetProfile(
            preferred_companies=frozenset({"acme"}),
            excluded_companies=frozenset({"badcorp"}),
        )
        assert "acme" in p.preferred_companies
        assert "badcorp" in p.excluded_companies
