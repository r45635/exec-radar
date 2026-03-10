"""Abstract base class and supporting types for rankers."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field
from schemas import FitScore, NormalizedJobPosting
from schemas.normalized_job_posting import EmploymentType, SeniorityLevel


class ExecutiveProfile(BaseModel):
    """Target profile that jobs are ranked against.

    All fields are optional so callers can supply only the criteria they care
    about.  Rankers should treat absent fields as "no preference" rather than
    penalising a mismatch.
    """

    desired_titles: list[str] = Field(
        default_factory=list,
        description="Target job titles or title keywords (case-insensitive)",
    )
    desired_seniority: list[SeniorityLevel] = Field(
        default_factory=list,
        description="Acceptable seniority levels",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Skills the candidate requires to see in a posting",
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Skills that are nice-to-have",
    )
    preferred_locations: list[str] = Field(
        default_factory=list,
        description="Acceptable locations (partial match supported)",
    )
    remote_only: bool = Field(False, description="If True, only remote roles are acceptable")
    min_salary: float | None = Field(None, description="Minimum acceptable salary (USD / year)")
    preferred_employment_types: list[EmploymentType] = Field(
        default_factory=list,
        description="Acceptable employment types (empty = any)",
    )


class BaseRanker(ABC):
    """Interface that every ranker must implement.

    A ranker receives a :class:`~schemas.NormalizedJobPosting` and a
    :class:`ExecutiveProfile` and returns a :class:`~schemas.FitScore`.
    """

    @property
    @abstractmethod
    def ranker_id(self) -> str:
        """Unique, URL-safe identifier for this ranker (e.g. ``'rule_based_v1'``)."""

    @abstractmethod
    def score(self, job: NormalizedJobPosting, profile: ExecutiveProfile) -> FitScore:
        """Score *job* against *profile*.

        Args:
            job: The normalized job posting to evaluate.
            profile: The target executive profile to compare against.

        Returns:
            A :class:`~schemas.FitScore` with an overall score and per-dimension details.
        """
