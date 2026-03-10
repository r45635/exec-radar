"""Simple rule-based ranker implementation."""

from __future__ import annotations

from packages.rankers.base import BaseRanker
from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import (
    NormalizedJobPosting,
    RemotePolicy,
    SeniorityLevel,
)
from packages.schemas.target_profile import TargetProfile


class RuleBasedRanker(BaseRanker):
    """A deterministic, rule-based ranker.

    Scores each posting against a configurable :class:`TargetProfile`.
    If no profile is supplied, the built-in defaults are used.

    Designed as an explainable baseline; future iterations will use
    embeddings and LLM-based evaluation.
    """

    def __init__(self, profile: TargetProfile | None = None) -> None:
        self._profile = profile or TargetProfile()

    @property
    def profile(self) -> TargetProfile:
        """The active target profile."""
        return self._profile

    def score(self, job: NormalizedJobPosting) -> FitScore:
        """Score a posting against the target executive profile.

        Args:
            job: The normalized posting to evaluate.

        Returns:
            A :class:`FitScore` with per-dimension and overall scores.
        """
        p = self._profile

        title_score = self._score_title(job.title, p.target_titles, p.excluded_titles)
        seniority_score = self._score_seniority(
            job.seniority, p.target_seniority, p.acceptable_seniority
        )
        location_score = self._score_location(
            job.remote_policy, p.preferred_remote_policies, job.location, p.target_locations
        )
        skills_score = self._score_skills(
            job.tags,
            p.required_keywords,
            p.preferred_keywords,
            p.excluded_keywords,
            p.target_industries,
        )

        overall = (
            p.weight_title * title_score
            + p.weight_seniority * seniority_score
            + p.weight_location * location_score
            + p.weight_skills * skills_score
        )

        explanations: list[str] = []
        if title_score >= 0.8:
            explanations.append("Strong title match")
        if title_score == 0.0 and p.excluded_titles:
            lower_title = job.title.lower().strip()
            if any(ex in lower_title for ex in p.excluded_titles):
                explanations.append("Title excluded by profile")
        if seniority_score >= 0.8:
            explanations.append("Seniority aligns")
        if skills_score >= 0.5:
            explanations.append(f"Skills overlap ({skills_score:.0%})")
        if skills_score < 0.0:
            explanations.append("Contains excluded keywords")

        # Company adjustments (simple bonus/penalty outside weighted dimensions)
        company_lower = (job.company or "").lower().strip()
        if company_lower and p.excluded_companies:
            if company_lower in {c.lower() for c in p.excluded_companies}:
                overall *= 0.1
                explanations.append("Excluded company")
        if company_lower and p.preferred_companies:
            if company_lower in {c.lower() for c in p.preferred_companies}:
                overall = overall + 0.1
                explanations.append("Preferred company")

        # Clamp overall to [0, 1]
        overall = max(0.0, min(1.0, overall))

        return FitScore(
            job_id=job.id,
            overall=round(overall, 4),
            title_match=round(max(0.0, title_score), 4),
            seniority_match=round(seniority_score, 4),
            location_match=round(max(0.0, min(1.0, location_score)), 4),
            skills_match=round(max(0.0, min(1.0, skills_score)), 4),
            explanation="; ".join(explanations) if explanations else "Low overall fit",
        )

    # ------------------------------------------------------------------
    # Dimension scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_title(
        title: str,
        target_titles: frozenset[str],
        excluded_titles: frozenset[str],
    ) -> float:
        """Return 1.0 for exact match, 0.5 for partial, 0.0 for excluded/miss."""
        lower = title.lower().strip()

        # Excluded titles always lose
        if excluded_titles:
            for ex in excluded_titles:
                if ex in lower or lower in ex:
                    return 0.0

        if lower in target_titles:
            return 1.0
        for target in target_titles:
            if target in lower or lower in target:
                return 0.5
        return 0.0

    @staticmethod
    def _score_seniority(
        level: SeniorityLevel,
        target: frozenset[SeniorityLevel],
        acceptable: frozenset[SeniorityLevel],
    ) -> float:
        """Return 1.0 for target-level, 0.6 for acceptable, 0.2 otherwise."""
        if level in target:
            return 1.0
        if level in acceptable:
            return 0.6
        return 0.2

    @staticmethod
    def _score_location(
        remote_policy: RemotePolicy,
        preferred: frozenset[RemotePolicy],
        location: str | None,
        target_locations: frozenset[str],
    ) -> float:
        """Prefer policies in the preferred set, then geographic matches."""
        if remote_policy in preferred:
            return 1.0
        if location and target_locations:
            loc_lower = location.lower()
            if any(tl.lower() in loc_lower for tl in target_locations):
                return 0.8
        if remote_policy == RemotePolicy.UNKNOWN:
            return 0.5
        return 0.3

    @staticmethod
    def _score_skills(
        tags: list[str],
        required: frozenset[str],
        preferred: frozenset[str],
        excluded: frozenset[str],
        industries: frozenset[str],
    ) -> float:
        """Compute keyword overlap with bonuses and penalties."""
        if not tags:
            return 0.0

        tag_set = {t.lower() for t in tags}
        required_lower = {s.lower() for s in required}
        preferred_lower = {s.lower() for s in preferred}
        excluded_lower = {s.lower() for s in excluded}
        industries_lower = {s.lower() for s in industries}

        # Base score: Jaccard-like overlap with required keywords
        if required_lower:
            overlap = tag_set & required_lower
            base = len(overlap) / len(required_lower)
        else:
            base = 0.0

        # Bonus for preferred keywords (up to +0.2)
        if preferred_lower:
            pref_overlap = tag_set & preferred_lower
            base += 0.2 * (len(pref_overlap) / len(preferred_lower))

        # Bonus for industry match (up to +0.15)
        if industries_lower:
            ind_overlap = tag_set & industries_lower
            base += 0.15 * (len(ind_overlap) / len(industries_lower))

        # Penalty for excluded keywords
        if excluded_lower and (tag_set & excluded_lower):
            base -= 0.3

        return base
