"""Tests for the rule-based ranker."""

from __future__ import annotations

import itertools

import pytest

from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.normalized_job import (
    NormalizedJobPosting,
    RemotePolicy,
    SeniorityLevel,
)
from packages.schemas.target_profile import TargetProfile

_counter = itertools.count(1)


@pytest.fixture()
def profile() -> TargetProfile:
    """Return the default target profile."""
    return TargetProfile()


@pytest.fixture()
def ranker(profile: TargetProfile) -> RuleBasedRanker:
    """Return a ranker configured with the default profile."""
    return RuleBasedRanker(profile=profile)


def _make_job(
    title: str = "Software Engineer",
    seniority: SeniorityLevel = SeniorityLevel.OTHER,
    remote_policy: RemotePolicy = RemotePolicy.UNKNOWN,
    tags: list[str] | None = None,
    company: str | None = None,
    location: str | None = None,
) -> NormalizedJobPosting:
    """Helper to construct a NormalizedJobPosting with a unique source_id."""
    return NormalizedJobPosting(
        source="test",
        source_id=str(next(_counter)),
        title=title,
        seniority=seniority,
        remote_policy=remote_policy,
        tags=tags or [],
        company=company,
        location=location,
    )


class TestRuleBasedRanker:
    """Tests for RuleBasedRanker scoring logic."""

    def test_perfect_match(self, ranker: RuleBasedRanker) -> None:
        """A COO role with matching profile should score high."""
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            remote_policy=RemotePolicy.REMOTE,
            tags=["operations", "supply chain", "strategy", "P&L"],
        )
        score = ranker.score(job)
        assert score.overall >= 0.7
        assert score.title_match == 1.0
        assert score.seniority_match == 1.0

    def test_low_match(self, ranker: RuleBasedRanker) -> None:
        """An unrelated role should score low."""
        job = _make_job(
            title="Junior Frontend Developer",
            seniority=SeniorityLevel.OTHER,
            remote_policy=RemotePolicy.ONSITE,
            tags=[],
        )
        score = ranker.score(job)
        assert score.overall < 0.3

    def test_partial_title_match(self, ranker: RuleBasedRanker) -> None:
        """A title containing a target keyword should score 0.5."""
        job = _make_job(title="VP of Operations & Strategy")
        score = ranker.score(job)
        assert score.title_match >= 0.5

    def test_seniority_director(self, ranker: RuleBasedRanker) -> None:
        """Director-level should get a moderate seniority score."""
        job = _make_job(seniority=SeniorityLevel.DIRECTOR)
        score = ranker.score(job)
        assert score.seniority_match == 0.6

    def test_remote_preference(self, ranker: RuleBasedRanker) -> None:
        """Remote / hybrid roles should score higher on location."""
        remote_job = _make_job(remote_policy=RemotePolicy.REMOTE)
        onsite_job = _make_job(remote_policy=RemotePolicy.ONSITE)
        assert ranker.score(remote_job).location_match > ranker.score(onsite_job).location_match

    def test_batch_sorted_descending(self, ranker: RuleBasedRanker) -> None:
        """score_batch should return results sorted by overall, descending."""
        jobs = [
            _make_job(title="Intern"),
            _make_job(
                title="Chief Operating Officer",
                seniority=SeniorityLevel.C_LEVEL,
                tags=["operations"],
            ),
            _make_job(title="VP of Operations", seniority=SeniorityLevel.VP),
        ]
        scores = ranker.score_batch(jobs)
        assert scores[0].overall >= scores[1].overall >= scores[2].overall

    def test_skills_overlap(self, ranker: RuleBasedRanker) -> None:
        """Skills score should increase with more target-skill overlap."""
        job_few = _make_job(tags=["operations"])
        job_many = _make_job(tags=["operations", "supply chain", "logistics", "strategy"])
        assert ranker.score(job_many).skills_match > ranker.score(job_few).skills_match


class TestRankerDefaultProfile:
    """Verify the ranker works with no explicit profile (backwards compat)."""

    def test_no_profile_uses_defaults(self) -> None:
        """RuleBasedRanker() without a profile should use built-in defaults."""
        ranker = RuleBasedRanker()
        assert ranker.profile == TargetProfile()

    def test_profile_property_exposed(self, ranker: RuleBasedRanker) -> None:
        """The active profile should be accessible via property."""
        assert isinstance(ranker.profile, TargetProfile)


class TestExcludedTitles:
    """Tests for excluded-title filtering."""

    def test_excluded_title_scores_zero(self) -> None:
        """A posting whose title matches an excluded title gets title_match=0."""
        profile = TargetProfile(excluded_titles=frozenset({"intern", "junior"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(title="Junior Operations Analyst")
        score = ranker.score(job)
        assert score.title_match == 0.0

    def test_non_excluded_title_unaffected(self) -> None:
        """A non-excluded title should not be penalized."""
        profile = TargetProfile(excluded_titles=frozenset({"intern"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(title="Chief Operating Officer")
        score = ranker.score(job)
        assert score.title_match == 1.0


class TestExcludedKeywords:
    """Tests for excluded-keyword penalty."""

    def test_excluded_keyword_reduces_skills_score(self) -> None:
        """Tags containing an excluded keyword should reduce skills score."""
        profile = TargetProfile(excluded_keywords=frozenset({"unpaid"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(tags=["operations", "unpaid"])
        score = ranker.score(job)
        # Should be lower than without the penalty
        clean_job = _make_job(tags=["operations"])
        clean_score = ranker.score(clean_job)
        assert score.skills_match < clean_score.skills_match


class TestPreferredKeywords:
    """Tests for preferred-keyword bonus."""

    def test_preferred_keywords_boost(self) -> None:
        """Preferred keywords should increase skills score."""
        profile = TargetProfile(preferred_keywords=frozenset({"lean", "six sigma"}))
        ranker = RuleBasedRanker(profile=profile)
        job_base = _make_job(tags=["operations"])
        job_boost = _make_job(tags=["operations", "lean"])
        assert ranker.score(job_boost).skills_match > ranker.score(job_base).skills_match


class TestCustomProfile:
    """Tests for fully custom profile configurations."""

    def test_custom_titles(self) -> None:
        """A custom profile with different target titles should score accordingly."""
        profile = TargetProfile(
            target_titles=frozenset({"data engineer", "ml engineer"}),
            required_keywords=frozenset({"python", "spark"}),
        )
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(title="Data Engineer", tags=["python", "spark"])
        score = ranker.score(job)
        assert score.title_match == 1.0
        assert score.skills_match == 1.0

    def test_custom_weights(self) -> None:
        """Custom scoring weights should redistribute dimension importance."""
        profile = TargetProfile(
            weight_title=1.0,
            weight_seniority=0.0,
            weight_location=0.0,
            weight_skills=0.0,
        )
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(title="Chief Operating Officer")
        score = ranker.score(job)
        assert score.overall == 1.0

    def test_custom_seniority(self) -> None:
        """A profile targeting DIRECTOR should give it full score."""
        profile = TargetProfile(
            target_seniority=frozenset({SeniorityLevel.DIRECTOR}),
            acceptable_seniority=frozenset(),
        )
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(seniority=SeniorityLevel.DIRECTOR)
        score = ranker.score(job)
        assert score.seniority_match == 1.0

    def test_overall_clamped_to_zero_one(self) -> None:
        """Even with heavy penalties the overall score stays in [0, 1]."""
        profile = TargetProfile(
            excluded_keywords=frozenset({"bad"}),
            weight_skills=1.0,
            weight_title=0.0,
            weight_seniority=0.0,
            weight_location=0.0,
        )
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(tags=["bad"])
        score = ranker.score(job)
        assert 0.0 <= score.overall <= 1.0


class TestTargetLocations:
    """Tests for target_locations in the profile."""

    def test_location_match_boosts_score(self) -> None:
        """A job in a target location should get a higher location score."""
        profile = TargetProfile(target_locations=frozenset({"new york", "london"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(location="New York, NY", remote_policy=RemotePolicy.ONSITE)
        score = ranker.score(job)
        assert score.location_match >= 0.8

    def test_no_location_match(self) -> None:
        """A job NOT in target locations should fall back to remote-policy scoring."""
        profile = TargetProfile(target_locations=frozenset({"tokyo"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(location="Paris, France", remote_policy=RemotePolicy.ONSITE)
        score = ranker.score(job)
        assert score.location_match == 0.3

    def test_remote_policy_still_preferred(self) -> None:
        """Remote-policy match should still score 1.0 even without target locations."""
        profile = TargetProfile(target_locations=frozenset({"berlin"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(location="Paris, France", remote_policy=RemotePolicy.REMOTE)
        score = ranker.score(job)
        assert score.location_match == 1.0


class TestCompanyPreferences:
    """Tests for preferred/excluded companies."""

    def test_preferred_company_boosts_overall(self) -> None:
        """A preferred company should add a bonus to the overall score."""
        profile = TargetProfile(preferred_companies=frozenset({"acme corp"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(company="Acme Corp")
        score_with = ranker.score(job)
        job_other = _make_job(company="Other Inc")
        score_other = ranker.score(job_other)
        assert score_with.overall > score_other.overall

    def test_excluded_company_penalizes_overall(self) -> None:
        """An excluded company should heavily penalize the overall score."""
        profile = TargetProfile(excluded_companies=frozenset({"badcorp"}))
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            company="BadCorp",
        )
        score = ranker.score(job)
        # Even a perfect title/seniority match should be crushed
        assert score.overall < 0.2


class TestIndustryPreferences:
    """Tests for target_industries in the profile."""

    def test_industry_match_boosts_skills(self) -> None:
        """Tags matching target industries should boost skills_match."""
        profile = TargetProfile(target_industries=frozenset({"healthcare", "fintech"}))
        ranker = RuleBasedRanker(profile=profile)
        job_with = _make_job(tags=["operations", "healthcare"])
        job_without = _make_job(tags=["operations"])
        assert ranker.score(job_with).skills_match > ranker.score(job_without).skills_match
