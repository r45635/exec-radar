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
    description_plain: str = "",
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
        description_plain=description_plain,
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
        assert score.overall >= 0.45
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
            weight_industry=0.0,
            weight_scope=0.0,
            weight_geography=0.0,
            weight_keyword_clusters=0.0,
            weight_location=0.0,
            weight_skills=0.0,
        )
        ranker = RuleBasedRanker(profile=profile)
        job = _make_job(
            title="Chief Operating Officer",
            tags=["operations", "manufacturing", "supply chain"],
        )
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
            weight_industry=0.0,
            weight_scope=0.0,
            weight_geography=0.0,
            weight_keyword_clusters=0.0,
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
        profile = TargetProfile(
            target_locations=frozenset({"tokyo"}),
            target_geographies=frozenset(),
        )
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


# ====================================================================
# New structured-output tests
# ====================================================================


class TestStructuredOutput:
    """Tests for dimension_scores, why_matched, why_penalized, red_flags."""

    def test_dimension_scores_keys(self, ranker: RuleBasedRanker) -> None:
        """FitScore should contain all six dimension keys."""
        job = _make_job(title="COO")
        score = ranker.score(job)
        expected = {"title", "seniority", "industry", "scope", "geography", "keyword_clusters"}
        assert set(score.dimension_scores.keys()) == expected

    def test_why_matched_populated(self, ranker: RuleBasedRanker) -> None:
        """A strong match should populate why_matched."""
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            remote_policy=RemotePolicy.REMOTE,
        )
        score = ranker.score(job)
        assert len(score.why_matched) > 0

    def test_red_flags_on_junior(self, ranker: RuleBasedRanker) -> None:
        """A junior role should produce red flags."""
        job = _make_job(
            title="Junior Analyst",
            seniority=SeniorityLevel.OTHER,
        )
        score = ranker.score(job)
        assert len(score.red_flags) > 0


# ====================================================================
# Scenario-based tests (semiconductor executive profile)
# ====================================================================


def _semi_profile() -> TargetProfile:
    """A semiconductor operations executive profile."""
    return TargetProfile()  # defaults are now semi-focused


def _semi_ranker() -> RuleBasedRanker:
    return RuleBasedRanker(profile=_semi_profile())


class TestScenarioStrongSemiconductorFit:
    """A COO at a semiconductor fab — ideal match."""

    def test_high_overall(self) -> None:
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            remote_policy=RemotePolicy.HYBRID,
            tags=[
                "operations",
                "semiconductor",
                "manufacturing",
                "lean",
                "supply chain",
                "P&L",
                "continuous improvement",
            ],
            location="Dresden, Germany",
        )
        score = _semi_ranker().score(job)
        assert score.overall >= 0.50
        assert score.title_match == 1.0
        assert score.seniority_match == 1.0
        assert len(score.why_matched) >= 3
        assert len(score.red_flags) == 0

    def test_dimension_scores_strong(self) -> None:
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            remote_policy=RemotePolicy.HYBRID,
            tags=[
                "operations",
                "semiconductor",
                "manufacturing",
                "yield",
                "fab",
                "lean",
            ],
        )
        score = _semi_ranker().score(job)
        assert score.dimension_scores["title"] >= 0.5
        assert score.dimension_scores["seniority"] == 1.0
        assert score.dimension_scores["keyword_clusters"] > 0


class TestScenarioTooJunior:
    """A junior operations analyst — should score very low."""

    def test_low_overall(self) -> None:
        job = _make_job(
            title="Junior Operations Analyst",
            seniority=SeniorityLevel.OTHER,
            remote_policy=RemotePolicy.ONSITE,
            tags=["operations"],
        )
        score = _semi_ranker().score(job)
        assert score.overall < 0.30
        assert "Seniority mismatch" in score.red_flags

    def test_title_excluded(self) -> None:
        job = _make_job(
            title="Intern - Manufacturing",
            seniority=SeniorityLevel.OTHER,
        )
        score = _semi_ranker().score(job)
        assert score.title_match == 0.0


class TestScenarioBusinessOnly:
    """A CFO / CMO — C-suite but wrong function."""

    def test_cfo_penalized(self) -> None:
        job = _make_job(
            title="Chief Financial Officer",
            seniority=SeniorityLevel.C_LEVEL,
            remote_policy=RemotePolicy.REMOTE,
            tags=["finance", "strategy"],
        )
        score = _semi_ranker().score(job)
        # Should still get seniority credit but low title / cluster
        assert score.title_match <= 0.2
        assert score.overall < 0.55

    def test_cmo_low_cluster(self) -> None:
        job = _make_job(
            title="Chief Marketing Officer",
            seniority=SeniorityLevel.C_LEVEL,
            tags=["marketing", "digital", "brand"],
        )
        score = _semi_ranker().score(job)
        assert score.dimension_scores["keyword_clusters"] < 0.15


class TestScenarioSoftwareHeavy:
    """A VP Engineering (software) — wrong domain."""

    def test_software_vp_low(self) -> None:
        job = _make_job(
            title="VP of Engineering",
            seniority=SeniorityLevel.VP,
            tags=["software", "agile", "devops", "cloud", "kubernetes"],
        )
        score = _semi_ranker().score(job)
        assert score.overall < 0.45
        assert score.dimension_scores["keyword_clusters"] < 0.10

    def test_software_director_low(self) -> None:
        job = _make_job(
            title="Director of Software Engineering",
            seniority=SeniorityLevel.DIRECTOR,
            tags=["python", "java", "microservices"],
        )
        score = _semi_ranker().score(job)
        assert score.overall < 0.35


class TestScenarioAdjacentInteresting:
    """A VP Supply Chain at an automotive OEM — adjacent but interesting."""

    def test_adjacent_decent_score(self) -> None:
        job = _make_job(
            title="VP Supply Chain",
            seniority=SeniorityLevel.VP,
            remote_policy=RemotePolicy.HYBRID,
            tags=[
                "supply chain",
                "automotive",
                "procurement",
                "logistics",
                "oem",
                "lean",
            ],
            location="Munich, Germany",
        )
        score = _semi_ranker().score(job)
        # Not a perfect match but clearly interesting
        assert 0.40 <= score.overall <= 0.85
        assert score.seniority_match == 1.0
        assert score.dimension_scores["keyword_clusters"] > 0

    def test_plant_director_adjacent(self) -> None:
        job = _make_job(
            title="Plant Director",
            seniority=SeniorityLevel.DIRECTOR,
            tags=["manufacturing", "production", "lean", "quality"],
            description_plain=(
                "Lead manufacturing operations across multiple sites "
                "with global supply chain coordination."
            ),
        )
        score = _semi_ranker().score(job)
        assert score.title_match >= 0.5
        assert score.overall >= 0.25


# ====================================================================
# Fabless / Foundry / OSAT cluster and stricter scoring tests
# ====================================================================


def _strict_semi_profile() -> TargetProfile:
    """A strict semiconductor operations executive profile."""
    return TargetProfile(
        target_titles=frozenset({
            "chief operating officer", "coo", "vp operations",
            "vp of operations", "vp manufacturing",
        }),
        adjacent_titles=frozenset({
            "senior director operations", "head of manufacturing",
            "vp supply chain", "vp quality",
        }),
        excluded_titles=frozenset({
            "intern", "junior", "entry level", "associate",
            "software engineer", "frontend developer",
        }),
        target_seniority=frozenset({
            SeniorityLevel.C_LEVEL, SeniorityLevel.SVP, SeniorityLevel.VP,
        }),
        acceptable_seniority=frozenset({
            SeniorityLevel.DIRECTOR, SeniorityLevel.HEAD,
        }),
        target_industries=frozenset({
            "semiconductor", "foundry", "osat", "fabless semiconductor",
        }),
        must_have_keywords=frozenset({
            "operations", "manufacturing", "supply chain",
        }),
        strong_keywords=frozenset({
            "semiconductor", "foundry", "osat", "fabless", "assembly",
            "test", "advanced packaging", "industrialization", "npi",
            "ramp", "quality", "operational excellence",
        }),
        excluded_keywords=frozenset({
            "saas", "customer success", "growth marketing",
            "revenue operations",
        }),
        preferred_scope_keywords=frozenset({
            "global operations", "multi-site", "international footprint",
            "cross-functional leadership", "p&l",
        }),
        weight_title=0.24,
        weight_seniority=0.14,
        weight_industry=0.18,
        weight_scope=0.14,
        weight_geography=0.10,
        weight_keyword_clusters=0.20,
    )


def _strict_ranker() -> RuleBasedRanker:
    return RuleBasedRanker(profile=_strict_semi_profile())


class TestFablessFoundryOsatClusterStrong:
    """Strong matches for fabless/foundry/OSAT exec ops roles."""

    def test_coo_at_foundry(self) -> None:
        """COO at a foundry with full manufacturing evidence → high score."""
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            remote_policy=RemotePolicy.HYBRID,
            tags=[
                "operations", "semiconductor", "foundry",
                "manufacturing", "supply chain", "yield",
                "advanced packaging", "quality",
            ],
            description_plain=(
                "Lead global operations for a leading semiconductor "
                "foundry. Multi-site responsibility including wafer "
                "fab and OSAT management. P&L ownership."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall >= 0.55
        assert score.title_match == 1.0
        assert score.dimension_scores["keyword_clusters"] > 0.10
        assert any("Fabless/foundry/OSAT" in m for m in score.why_matched)
        assert len(score.red_flags) == 0

    def test_vp_ops_osat(self) -> None:
        """VP Ops at an OSAT company → strong match."""
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            tags=[
                "operations", "osat", "assembly", "test",
                "manufacturing", "supply chain", "packaging",
            ],
            description_plain=(
                "Oversee outsourced semiconductor assembly and test "
                "operations across multiple OSAT partners. Manage "
                "supplier quality and advanced packaging programs."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall >= 0.45
        assert score.seniority_match == 1.0
        assert any("Fabless/foundry/OSAT" in m for m in score.why_matched)


class TestBackendSemiManufacturingStrong:
    """Strong matches for backend semiconductor manufacturing leadership."""

    def test_vp_manufacturing_backend(self) -> None:
        """VP Manufacturing for backend semi → strong match."""
        job = _make_job(
            title="VP Manufacturing",
            seniority=SeniorityLevel.VP,
            tags=[
                "semiconductor", "manufacturing", "backend",
                "assembly", "test", "wafer sort", "final test",
                "quality", "operations",
            ],
            description_plain=(
                "Lead backend semiconductor manufacturing including "
                "assembly, wafer sort, and final test. Multi-site "
                "global operations with P&L responsibility."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall >= 0.45
        assert score.dimension_scores["keyword_clusters"] > 0.10
        assert len(score.red_flags) == 0


class TestSoftwareHeavyPenalty:
    """Penalty for software-heavy roles with misleading ops titles."""

    def test_vp_ops_software_company(self) -> None:
        """VP Operations at a SaaS company → penalized."""
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            tags=[
                "software", "devops", "kubernetes", "cloud",
                "agile", "ci/cd",
            ],
            description_plain=(
                "Lead engineering operations for our cloud-native "
                "SaaS platform. Manage devops, kubernetes clusters, "
                "and microservices deployment infrastructure."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.30
        assert any("Software-heavy" in p for p in score.why_penalized)
        assert "Software-heavy role" in score.red_flags

    def test_director_ops_pure_software(self) -> None:
        """Director of Operations at a pure software shop → low."""
        job = _make_job(
            title="Director of Operations",
            seniority=SeniorityLevel.DIRECTOR,
            tags=["software", "agile", "devops", "docker", "react"],
            description_plain="Manage software delivery operations.",
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.25


class TestBusinessOnlyPenalty:
    """Penalty for business-only/GTM roles."""

    def test_vp_revenue_ops(self) -> None:
        """VP Revenue Operations → penalized as GTM role."""
        job = _make_job(
            title="VP Revenue Operations",
            seniority=SeniorityLevel.VP,
            tags=[
                "revenue operations", "sales enablement",
                "demand generation", "pipeline generation",
            ],
            description_plain=(
                "Drive go-to-market operations including demand "
                "generation, sales enablement, and pipeline management."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.25
        assert any("GTM" in p for p in score.why_penalized)

    def test_coo_gtm_company(self) -> None:
        """COO at a GTM-heavy company → penalized."""
        job = _make_job(
            title="Chief Operating Officer",
            seniority=SeniorityLevel.C_LEVEL,
            tags=["go-to-market", "customer success", "growth marketing"],
            description_plain=(
                "Lead GTM operations, customer success, and growth "
                "marketing for our B2B SaaS platform."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.35
        assert len(score.red_flags) > 0


class TestTooJuniorPenalty:
    """Penalty for too-junior roles."""

    def test_intern_manufacturing(self) -> None:
        """Manufacturing intern → hard penalty."""
        job = _make_job(
            title="Intern - Manufacturing Operations",
            seniority=SeniorityLevel.OTHER,
            tags=["manufacturing", "operations"],
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.10
        assert "Too junior" in score.red_flags

    def test_junior_analyst(self) -> None:
        """Junior operations analyst → hard penalty."""
        job = _make_job(
            title="Junior Operations Analyst",
            seniority=SeniorityLevel.OTHER,
            tags=["operations", "supply chain"],
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.10
        assert "Too junior" in score.red_flags


class TestNarrowPlantPenalty:
    """Penalty for narrow plant/site roles when exec scope is expected."""

    def test_plant_director_single_site(self) -> None:
        """Plant Director at a single site → penalized vs. exec profile."""
        job = _make_job(
            title="Plant Director",
            seniority=SeniorityLevel.DIRECTOR,
            tags=["manufacturing", "production", "lean", "quality"],
            description_plain=(
                "Manage a single plant of 200 employees. Local plant "
                "operations and production scheduling."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.30
        assert any("Narrow scope" in p for p in score.why_penalized)

    def test_plant_director_no_global(self) -> None:
        """Plant Director without global/multi-site evidence → penalized."""
        job = _make_job(
            title="Plant Director",
            seniority=SeniorityLevel.DIRECTOR,
            tags=["manufacturing", "production"],
            description_plain="Oversee daily production.",
        )
        score = _strict_ranker().score(job)
        assert any("Narrow scope" in p for p in score.why_penalized)


class TestWeakScopeOpsTitlePenalty:
    """Ops title but no real industrial/manufacturing evidence."""

    def test_ops_title_generic_description(self) -> None:
        """'VP Operations' with no industrial evidence → penalized."""
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            tags=[],
            description_plain=(
                "Lead cross-functional teams and drive strategy."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall < 0.25
        assert any("Misleading operations title" in rf for rf in score.red_flags)

    def test_ops_title_with_evidence(self) -> None:
        """'VP Operations' with industrial evidence → no misleading penalty."""
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            tags=["manufacturing", "supply chain", "lean", "quality"],
            description_plain=(
                "Lead manufacturing operations across multiple sites. "
                "P&L responsibility and supply chain management."
            ),
        )
        score = _strict_ranker().score(job)
        assert score.overall >= 0.35
        assert "Misleading operations title" not in score.red_flags


class TestFablessFoundryOsatExplainability:
    """Verify explainability fields mention the new cluster."""

    def test_cluster_in_why_matched(self) -> None:
        """Fabless/foundry/OSAT should appear in why_matched."""
        job = _make_job(
            title="VP Manufacturing",
            seniority=SeniorityLevel.VP,
            tags=["foundry", "osat", "semiconductor", "manufacturing",
                  "assembly", "test", "operations"],
            description_plain=(
                "Manage fabless semiconductor supply chain including "
                "foundry and OSAT partner relationships. Advanced "
                "packaging and contract manufacturing oversight."
            ),
        )
        score = _strict_ranker().score(job)
        matched_text = " ".join(score.why_matched)
        assert "Fabless/foundry/OSAT" in matched_text

    def test_cluster_not_mentioned_when_absent(self) -> None:
        """No fabless/OSAT signals → cluster not in why_matched."""
        job = _make_job(
            title="VP of Operations",
            seniority=SeniorityLevel.VP,
            tags=["operations", "lean", "quality", "manufacturing"],
            description_plain="General manufacturing leadership.",
        )
        score = _strict_ranker().score(job)
        matched_text = " ".join(score.why_matched)
        assert "Fabless/foundry/OSAT" not in matched_text
