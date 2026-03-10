"""Fit-score schema — result of ranking a normalized posting."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FitScore(BaseModel):
    """Quantified match between a ``NormalizedJobPosting`` and the target profile.

    Produced by a ranker.  ``overall`` is the weighted aggregate;
    individual dimension scores provide explainability.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(..., description="ID of the scored NormalizedJobPosting")
    overall: float = Field(..., ge=0.0, le=1.0, description="Aggregate fit score 0-1")
    title_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Title relevance")
    seniority_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Seniority fit")
    location_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Location fit")
    skills_match: float = Field(default=0.0, ge=0.0, le=1.0, description="Skills overlap")
    explanation: str = Field(default="", description="Human-readable reasoning")
