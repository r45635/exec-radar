"""Rule-based ranker that scores jobs against an executive profile."""

from schemas import FitScore, NormalizedJobPosting
from schemas.normalized_job_posting import SeniorityLevel

from .base import BaseRanker, ExecutiveProfile

# Weights must sum to 1.0
_WEIGHTS = {
    "title": 0.35,
    "skills": 0.30,
    "location": 0.20,
    "compensation": 0.15,
}


def _score_title(job: NormalizedJobPosting, profile: ExecutiveProfile) -> float:
    """Return 0–100 based on title keyword and seniority matches."""
    score = 0.0

    # Seniority match (50 pts)
    if profile.desired_seniority:
        if job.seniority in profile.desired_seniority:
            score += 50.0
    else:
        # No seniority preference → give moderate credit
        if job.seniority not in (SeniorityLevel.UNKNOWN, SeniorityLevel.ENTRY):
            score += 30.0

    # Title keyword match (50 pts)
    if profile.desired_titles:
        job_title_lower = job.title.lower()
        for desired in profile.desired_titles:
            if desired.lower() in job_title_lower:
                score += 50.0
                break
    else:
        score += 25.0  # No preference → partial credit

    return min(score, 100.0)


def _score_skills(job: NormalizedJobPosting, profile: ExecutiveProfile) -> float:
    """Return 0–100 based on required and preferred skills overlap."""
    if not profile.required_skills and not profile.preferred_skills:
        return 50.0  # No skill preference → neutral score

    job_skills_lower = {s.lower() for s in job.skills}
    score = 0.0

    # Required skills: each match worth 60/n pts
    if profile.required_skills:
        matched = sum(
            1 for s in profile.required_skills if s.lower() in job_skills_lower
        )
        score += 60.0 * matched / len(profile.required_skills)

    # Preferred skills: each match worth 40/n pts
    if profile.preferred_skills:
        matched = sum(
            1 for s in profile.preferred_skills if s.lower() in job_skills_lower
        )
        score += 40.0 * matched / len(profile.preferred_skills)
    else:
        score += 20.0  # No preferred skills specified → partial credit

    return min(score, 100.0)


def _score_location(job: NormalizedJobPosting, profile: ExecutiveProfile) -> float:
    """Return 0–100 based on remote status and preferred locations."""
    if profile.remote_only:
        return 100.0 if job.remote else 0.0

    if not profile.preferred_locations:
        return 70.0  # No location preference → mostly neutral

    # Check location string match (partial, case-insensitive)
    job_location = (job.location or "").lower()
    for pref in profile.preferred_locations:
        if pref.lower() in job_location:
            return 100.0

    # Remote roles are acceptable even if location doesn't match
    if job.remote:
        return 60.0

    return 20.0


def _score_compensation(job: NormalizedJobPosting, profile: ExecutiveProfile) -> float:
    """Return 0–100 based on salary alignment."""
    if profile.min_salary is None:
        return 60.0  # No salary preference → neutral

    if job.salary_max is None and job.salary_min is None:
        return 40.0  # Salary not listed → slight penalty

    # Use salary_max if available, otherwise salary_min
    job_salary = job.salary_max or job.salary_min
    assert job_salary is not None  # narrowed above

    if job_salary >= profile.min_salary:
        # Bonus for postings significantly above minimum
        overage_ratio = (job_salary - profile.min_salary) / profile.min_salary
        return min(100.0, 80.0 + overage_ratio * 20.0)

    # Below minimum – scale linearly down
    ratio = job_salary / profile.min_salary
    return max(0.0, ratio * 60.0)


class RuleBasedRanker(BaseRanker):
    """Scores job postings against an executive profile using weighted rules.

    The scoring model has four dimensions:

    - **Title** (35 %): keyword and seniority match
    - **Skills** (30 %): required and preferred skill overlap
    - **Location** (20 %): remote / preferred location match
    - **Compensation** (15 %): salary alignment

    This is intentionally simple and transparent so it can be audited and
    extended.  Replace with an embedding-based ranker for semantic matching.
    """

    @property
    def ranker_id(self) -> str:
        return "rule_based_v1"

    def score(self, job: NormalizedJobPosting, profile: ExecutiveProfile) -> FitScore:
        """Score *job* against *profile* using weighted rules.

        Args:
            job: Normalized job posting.
            profile: Target executive profile.

        Returns:
            :class:`~schemas.FitScore` with overall and per-dimension scores.
        """
        title_score = _score_title(job, profile)
        skill_score = _score_skills(job, profile)
        location_score = _score_location(job, profile)
        compensation_score = _score_compensation(job, profile)

        overall = (
            title_score * _WEIGHTS["title"]
            + skill_score * _WEIGHTS["skills"]
            + location_score * _WEIGHTS["location"]
            + compensation_score * _WEIGHTS["compensation"]
        )

        explanation = (
            f"Title: {title_score:.0f}/100 · "
            f"Skills: {skill_score:.0f}/100 · "
            f"Location: {location_score:.0f}/100 · "
            f"Compensation: {compensation_score:.0f}/100"
        )

        return FitScore(
            job_id=job.id,
            ranker=self.ranker_id,
            score=round(overall, 2),
            title_score=round(title_score, 2),
            skill_score=round(skill_score, 2),
            location_score=round(location_score, 2),
            compensation_score=round(compensation_score, 2),
            explanation=explanation,
            details={"weights": _WEIGHTS},
        )
